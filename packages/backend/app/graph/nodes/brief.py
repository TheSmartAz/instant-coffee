from __future__ import annotations

from typing import Any

from ...schemas.scenario import get_default_data_model
from ...services.scenario_detector import detect_scenario


def _as_dict(state: Any) -> dict:
    if isinstance(state, dict):
        return dict(state)
    if hasattr(state, "__dict__"):
        return dict(state.__dict__)
    return {}


def _resolve_product_type(state: dict) -> str | None:
    product_doc = state.get("product_doc")
    if isinstance(product_doc, dict):
        value = product_doc.get("product_type") or product_doc.get("productType")
        if value:
            return str(value).strip().lower()
    user_input = state.get("user_input") or ""
    scenario = detect_scenario(str(user_input))
    if scenario.product_type != "unknown":
        return scenario.product_type
    return None


def _has_entities(value: Any) -> bool:
    return isinstance(value, dict) and isinstance(value.get("entities"), dict) and bool(value.get("entities"))


async def brief_node(state: Any) -> dict:
    updated = _as_dict(state)
    updated.setdefault("product_doc", None)
    updated.setdefault("pages", [])
    updated.setdefault("data_model", None)
    if not _has_entities(updated.get("data_model")):
        product_type = _resolve_product_type(updated)
        if product_type:
            default_model = get_default_data_model(product_type)
            if default_model is not None:
                data_model = default_model.model_dump(by_alias=True, exclude_none=True)
                updated["data_model"] = data_model
                product_doc = updated.get("product_doc")
                if isinstance(product_doc, dict) and not _has_entities(product_doc.get("data_model")):
                    product_doc["data_model"] = data_model
                    if not product_doc.get("product_type"):
                        product_doc["product_type"] = product_type
    return updated


__all__ = ["brief_node"]
