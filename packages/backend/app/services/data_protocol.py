from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.orm import Session as DbSession

from ..db.models import Session as SessionModel
from ..services.skills import SkillManifest, SkillsRegistry
from ..utils.product_doc import (
    build_data_client_script,
    build_data_store_script,
    inject_data_scripts,
)

_FLOW_PRODUCT_TYPES = {"ecommerce", "travel", "manual", "kanban", "booking", "dashboard"}
_STATIC_PRODUCT_TYPES = {"landing", "card", "invitation"}

_DEFAULT_EVENTS = [
    "add_to_cart",
    "update_qty",
    "remove_item",
    "checkout_draft",
    "submit_order",
    "submit_booking",
    "submit_form",
    "clear_cart",
]

_DEFAULT_SCHEMAS: dict[str, dict[str, Any]] = {
    "ecommerce": {
        "cart": {
            "items": [],
            "totals": {"subtotal": 0, "tax": 0, "total": 0},
            "currency": "USD",
        },
        "booking": {"draft": {}},
        "forms": {"draft": {}},
        "user": {"profile": {}},
    },
    "booking": {
        "cart": {
            "items": [],
            "totals": {"subtotal": 0, "tax": 0, "total": 0},
            "currency": "USD",
        },
        "booking": {"draft": {}},
        "forms": {"draft": {}},
        "user": {"profile": {}},
    },
    "dashboard": {
        "cart": {
            "items": [],
            "totals": {"subtotal": 0, "tax": 0, "total": 0},
            "currency": "USD",
        },
        "booking": {"draft": {}},
        "forms": {"draft": {}},
        "user": {"profile": {}},
        "filters": {},
        "widgets": [],
        "insights": [],
    },
    "travel": {
        "trip": {"current": {}},
        "day_plans": [],
        "activities": [],
        "locations": [],
        "bookmarks": [],
    },
    "manual": {
        "manual": {},
        "sections": [],
        "pages": [],
        "reading": {"progress": {}},
    },
    "kanban": {
        "board": {},
        "columns": [],
        "tasks": [],
        "users": [],
        "tags": [],
    },
}

_STATE_SCHEMA_ENTITY_MAP: dict[str, str] = {
    "cart": "Cart",
    "booking": "Booking",
    "forms": "Form",
    "user": "User",
    "trip": "Trip",
    "day_plans": "DayPlan",
    "activities": "Activity",
    "locations": "Location",
    "bookmarks": "Bookmark",
    "manual": "Manual",
    "sections": "Section",
    "pages": "Page",
    "reading": "Reading",
    "board": "Board",
    "columns": "Column",
    "tasks": "Task",
    "tags": "Tag",
    "widgets": "Widget",
    "insights": "Insight",
    "filters": "Filter",
}


_ENTITY_STATE_PATH_HINTS: dict[str, str] = {
    "cartitem": "cart.items",
    "cart": "cart.items",
    "order": "orders",
    "booking": "booking.draft",
    "form": "forms.submissions",
    "formsubmission": "forms.submissions",
    "user": "user.profile",
    "product": "products",
    "category": "categories",
    "trip": "trip.current",
    "dayplan": "day_plans",
    "activity": "activities",
    "location": "locations",
    "bookmark": "bookmarks",
    "manual": "manual.current",
    "section": "sections",
    "page": "pages",
    "board": "board.current",
    "column": "columns",
    "task": "tasks",
    "tag": "tags",
    "widget": "widgets",
    "insight": "insights",
    "filter": "filters",
}


def _normalize_lookup_key(value: Any) -> str:
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def _root_path_exists(schema: dict[str, Any], path: str) -> bool:
    root = str(path or "").split(".", 1)[0]
    return bool(root) and root in schema


def _build_state_path_index(schema: dict[str, Any]) -> dict[str, str]:
    index: dict[str, str] = {}
    for key, value in schema.items():
        root_key = str(key)
        root_normalized = _normalize_lookup_key(root_key)
        if root_normalized and root_normalized not in index:
            index[root_normalized] = root_key

        if not isinstance(value, dict):
            continue

        for child_key in value.keys():
            child = str(child_key)
            child_path = f"{root_key}.{child}"
            child_normalized = _normalize_lookup_key(child)
            combined_normalized = _normalize_lookup_key(f"{root_key}{child}")
            if child_normalized and child_normalized not in index:
                index[child_normalized] = child_path
            if combined_normalized and combined_normalized not in index:
                index[combined_normalized] = child_path
    return index


def _derive_entity_state_map(schema: dict[str, Any], data_model: dict[str, Any]) -> dict[str, str]:
    if not isinstance(schema, dict) or not schema:
        return {}
    if not isinstance(data_model, dict):
        return {}

    entities = data_model.get("entities")
    if not isinstance(entities, dict) or not entities:
        return {}

    state_index = _build_state_path_index(schema)
    reverse_map = {
        _normalize_lookup_key(entity_name): state_key
        for state_key, entity_name in _STATE_SCHEMA_ENTITY_MAP.items()
    }

    mapping: dict[str, str] = {}
    for entity_name in entities.keys():
        source_name = str(entity_name)
        normalized = _normalize_lookup_key(source_name)
        if not normalized:
            continue

        singular = normalized[:-1] if normalized.endswith("s") and len(normalized) > 1 else normalized
        plural = normalized if normalized.endswith("s") else f"{normalized}s"
        candidates = [normalized, singular, plural]
        if singular.endswith("item") and len(singular) > 4:
            candidates.append(singular[:-4])

        resolved_path: str | None = None

        explicit_path = None
        for candidate in candidates:
            explicit_path = _ENTITY_STATE_PATH_HINTS.get(candidate)
            if explicit_path:
                break
        if explicit_path and _root_path_exists(schema, explicit_path):
            resolved_path = explicit_path

        if resolved_path is None:
            for candidate in candidates:
                mapped_state_key = reverse_map.get(candidate)
                if mapped_state_key and mapped_state_key in schema:
                    resolved_path = mapped_state_key
                    break

        if resolved_path is None:
            for candidate in candidates:
                indexed = state_index.get(candidate)
                if indexed:
                    resolved_path = indexed
                    break

        if resolved_path is not None:
            mapping[source_name] = resolved_path

    return mapping


def _normalize_entity_name(name: str) -> str:
    raw = str(name or "").strip()
    if not raw:
        return "Entity"
    normalized = "".join(ch if ch.isalnum() else "_" for ch in raw)
    normalized = normalized.strip("_") or "Entity"
    if normalized[0].isdigit():
        normalized = f"Entity_{normalized}"
    return normalized[:63]


def _is_primitive(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _infer_field_type(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "string"


def _state_schema_to_data_model(schema: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(schema, dict) or not schema:
        return {}

    entities: dict[str, Any] = {}
    for key, value in schema.items():
        entity_name = _normalize_entity_name(_STATE_SCHEMA_ENTITY_MAP.get(str(key), str(key)))
        fields: list[dict[str, Any]] = []

        if isinstance(value, dict):
            for field_name, field_value in value.items():
                normalized_field = _normalize_entity_name(str(field_name)).lower()
                fields.append(
                    {
                        "name": normalized_field,
                        "type": _infer_field_type(field_value),
                        "required": False,
                    }
                )
        elif isinstance(value, list):
            item_type = "object"
            if value:
                item_type = _infer_field_type(value[0])
            fields.append({"name": "items", "type": "array", "required": False})
            if item_type != "object":
                fields.append({"name": "value", "type": item_type, "required": False})
        elif _is_primitive(value):
            fields.append({"name": "value", "type": _infer_field_type(value), "required": False})

        if not fields:
            fields = [{"name": "value", "type": "object", "required": False}]

        entities[entity_name] = {
            "fields": fields,
            "primaryKey": "id",
        }

    return {"entities": entities, "relations": []}


def _extract_data_model_from_doc(product_doc: Any | None) -> dict[str, Any]:
    if product_doc is None:
        return {}

    structured: Any = None
    if isinstance(product_doc, dict):
        structured = product_doc.get("structured") if isinstance(product_doc.get("structured"), dict) else None
        if structured is None:
            structured = product_doc
    else:
        maybe_structured = getattr(product_doc, "structured", None)
        if isinstance(maybe_structured, dict):
            structured = maybe_structured

    if not isinstance(structured, dict):
        return {}

    data_model = structured.get("data_model")
    if hasattr(data_model, "model_dump"):
        dumped = data_model.model_dump(by_alias=True, exclude_none=True)
        return dumped if isinstance(dumped, dict) else {}
    if isinstance(data_model, dict):
        return data_model

    state_contract = structured.get("state_contract")
    if isinstance(state_contract, dict):
        return _state_schema_to_data_model(state_contract.get("schema"))

    return {}


@dataclass
class DataProtocolAssets:
    shared_dir: Path
    contract_path: Path
    data_store_path: Path
    data_client_path: Optional[Path]


class DataProtocolGenerator:
    def __init__(
        self,
        *,
        output_dir: str,
        session_id: str,
        db: Optional[DbSession] = None,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.session_id = session_id
        self.db = db
        self._skills = SkillsRegistry()

    def prepare_html(
        self,
        html: str,
        *,
        product_doc: Any | None,
        page_slug: str = "index",
    ) -> str:
        product_type = self._resolve_product_type(product_doc)
        if product_type not in _FLOW_PRODUCT_TYPES and product_type not in _STATIC_PRODUCT_TYPES:
            return html
        skill_id = self._resolve_skill_id()
        contract = self.generate_state_contract(product_type, skill_id=skill_id)
        contract = self._inject_runtime_context(contract, product_doc=product_doc)
        include_client = product_type in _FLOW_PRODUCT_TYPES
        self.write_shared_assets(product_type, contract, include_client=include_client)
        return self.inject_scripts_into_page(
            html=html,
            product_type=product_type,
            page_slug=page_slug,
            contract=contract,
        )

    def generate_state_contract(
        self,
        product_type: str,
        skill: Optional[SkillManifest] = None,
        *,
        skill_id: Optional[str] = None,
    ) -> dict:
        normalized_type = (product_type or "").strip().lower()
        contract = None
        if skill and skill.id:
            contract = self._skills.get_state_contract(skill.id)
        if contract is None and skill_id:
            contract = self._skills.get_state_contract(skill_id)
        if contract is None and normalized_type:
            manifest = self._skills.select_best(normalized_type)
            if manifest:
                contract = self._skills.get_state_contract(manifest.id)
        return self._normalize_contract(contract, normalized_type)

    def generate_data_store_script(self, contract: dict) -> str:
        return build_data_store_script(contract)

    def generate_data_client_script(self, product_type: str, contract: dict) -> str:
        return build_data_client_script(product_type, contract)

    def inject_scripts_into_page(
        self,
        html: str,
        product_type: str,
        *,
        page_slug: str = "index",
        contract: Optional[dict] = None,
    ) -> str:
        normalized_type = (product_type or "").strip().lower()
        include_client = normalized_type in _FLOW_PRODUCT_TYPES
        store_src = self._resolve_store_src(page_slug)
        client_src = self._resolve_client_src(page_slug) if include_client else None
        return inject_data_scripts(
            html,
            store_src=store_src,
            client_src=client_src,
            contract=contract,
            product_type=normalized_type,
        )

    def write_shared_assets(
        self,
        product_type: str,
        contract: dict,
        *,
        include_client: bool,
    ) -> DataProtocolAssets:
        session_dir = self.output_dir / self.session_id
        shared_dir = session_dir / "shared"
        shared_dir.mkdir(parents=True, exist_ok=True)

        contract_path = shared_dir / "state-contract.json"
        contract_path.write_text(
            json.dumps(contract, ensure_ascii=True, indent=2),
            encoding="utf-8",
        )

        data_store_path = shared_dir / "data-store.js"
        data_store_path.write_text(
            self.generate_data_store_script(contract),
            encoding="utf-8",
        )

        data_client_path = None
        if include_client:
            data_client_path = shared_dir / "data-client.js"
            data_client_path.write_text(
                self.generate_data_client_script(product_type, contract),
                encoding="utf-8",
            )

        return DataProtocolAssets(
            shared_dir=shared_dir,
            contract_path=contract_path,
            data_store_path=data_store_path,
            data_client_path=data_client_path,
        )

    def _resolve_product_type(self, product_doc: Any | None) -> str:
        if product_doc is None:
            session_type = self._resolve_session_product_type()
            return session_type or "unknown"

        if isinstance(product_doc, dict):
            structured = product_doc.get("structured")
            if isinstance(structured, dict):
                product_type = structured.get("product_type") or structured.get("productType")
            else:
                product_type = product_doc.get("product_type") or product_doc.get("productType")
        else:
            structured = getattr(product_doc, "structured", None)
            if isinstance(structured, dict):
                product_type = structured.get("product_type") or structured.get("productType")
            else:
                product_type = getattr(product_doc, "product_type", None)

        if not product_type:
            product_type = self._resolve_session_product_type()
        return str(product_type or "unknown").strip().lower()

    def _resolve_session_product_type(self) -> Optional[str]:
        if self.db is None:
            return None
        session = self.db.get(SessionModel, self.session_id)
        if session is None:
            return None
        return session.product_type

    def _resolve_skill_id(self) -> Optional[str]:
        if self.db is None:
            return None
        session = self.db.get(SessionModel, self.session_id)
        if session is None:
            return None
        return session.skill_id

    def _resolve_store_src(self, page_slug: str) -> str:
        return "shared/data-store.js" if page_slug in {"", "index"} else "../shared/data-store.js"

    def _resolve_client_src(self, page_slug: str) -> str:
        return "shared/data-client.js" if page_slug in {"", "index"} else "../shared/data-client.js"

    def _inject_runtime_context(self, contract: dict, *, product_doc: Any | None) -> dict:
        runtime = dict(contract or {})
        runtime["session_id"] = self.session_id
        runtime["api_base_url"] = self._resolve_api_base_url()

        data_model = _extract_data_model_from_doc(product_doc)
        if isinstance(data_model, dict) and isinstance(data_model.get("entities"), dict):
            runtime["data_model"] = data_model
            schema = runtime.get("schema") if isinstance(runtime.get("schema"), dict) else {}
            entity_state_map = _derive_entity_state_map(schema, data_model)
            if entity_state_map:
                runtime["entity_state_map"] = entity_state_map
        return runtime

    @staticmethod
    def _resolve_api_base_url() -> str:
        raw = os.getenv("VITE_API_URL") or os.getenv("API_BASE_URL") or ""
        value = str(raw).strip()
        if not value:
            return ""
        return value.rstrip("/")

    def _normalize_contract(self, contract: Optional[dict], product_type: str) -> dict:
        normalized_type = (product_type or "").strip().lower()
        if normalized_type in _STATIC_PRODUCT_TYPES:
            return {
                "shared_state_key": "instant-coffee:state",
                "records_key": "instant-coffee:records",
                "events_key": "instant-coffee:events",
                "schema": {},
                "events": [],
            }

        schema: dict[str, Any] = {}
        if isinstance(contract, dict) and isinstance(contract.get("schema"), dict):
            schema = contract.get("schema") or {}
        elif normalized_type in _DEFAULT_SCHEMAS:
            schema = _DEFAULT_SCHEMAS[normalized_type]

        events: list[str] = []
        if isinstance(contract, dict) and isinstance(contract.get("events"), list):
            events = [str(item) for item in contract.get("events", []) if str(item).strip()]
        if not events:
            events = list(_DEFAULT_EVENTS) if normalized_type in _FLOW_PRODUCT_TYPES else []

        return {
            "shared_state_key": self._get_key(contract, "shared_state_key", "instant-coffee:state"),
            "records_key": self._get_key(contract, "records_key", "instant-coffee:records"),
            "events_key": self._get_key(contract, "events_key", "instant-coffee:events"),
            "schema": schema,
            "events": events,
        }

    @staticmethod
    def _get_key(contract: Optional[dict], key: str, fallback: str) -> str:
        if isinstance(contract, dict):
            value = contract.get(key)
            if value:
                return str(value)
        return fallback


__all__ = ["DataProtocolGenerator", "DataProtocolAssets"]
