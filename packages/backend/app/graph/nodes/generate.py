from __future__ import annotations

import hashlib
import json
import logging
import re
from typing import Any, Dict, List

from ...db.utils import transaction_scope
from ...services.app_data_store import get_app_data_store
from ...services.component_validator import auto_fix_unknown_components, validate_page_schema
from ...services.page import PageService

logger = logging.getLogger(__name__)


def _as_dict(state: Any) -> dict:
    if isinstance(state, dict):
        return dict(state)
    if hasattr(state, "__dict__"):
        return dict(state.__dict__)
    return {}


def _has_data_model_entities(value: Any) -> bool:
    return isinstance(value, dict) and isinstance(value.get("entities"), dict) and bool(value.get("entities"))


def _resolve_data_model(state: dict) -> dict[str, Any]:
    data_model = state.get("data_model")
    if _has_data_model_entities(data_model):
        return data_model

    product_doc = state.get("product_doc")
    if not isinstance(product_doc, dict):
        return {}

    structured = product_doc.get("structured") if isinstance(product_doc.get("structured"), dict) else product_doc
    if not isinstance(structured, dict):
        return {}

    resolved = structured.get("data_model")
    if _has_data_model_entities(resolved):
        return resolved
    return {}


def _data_model_version(data_model: dict[str, Any]) -> str:
    canonical = json.dumps(data_model, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha1(canonical.encode("utf-8")).hexdigest()[:12]


async def _provision_data_model(
    session_id: Any,
    data_model: dict[str, Any],
) -> dict[str, Any] | None:
    if not session_id or not _has_data_model_entities(data_model):
        return None

    store = get_app_data_store()
    if not store.enabled:
        return None

    try:
        await store.create_schema(str(session_id))
        summary = await store.create_tables(str(session_id), data_model)
    except Exception:
        logger.warning(
            "Generate node failed to provision app data model",
            exc_info=True,
        )
        return None

    if not isinstance(summary, dict):
        return None
    return summary


async def generate_node(state: Any, *, event_emitter: Any | None = None) -> dict:
    updated = _as_dict(state)

    component_registry = updated.get("component_registry") or {}
    page_schemas = updated.get("page_schemas")

    if not isinstance(page_schemas, list) or not page_schemas:
        page_schemas = _fallback_page_schemas(updated, component_registry)

    fixed_schemas: List[dict] = []
    errors: List[str] = []

    for idx, schema in enumerate(page_schemas or []):
        if not isinstance(schema, dict):
            schema = {}
        schema_errors = validate_page_schema(schema, component_registry)
        if schema_errors:
            schema = auto_fix_unknown_components(schema, component_registry)
            schema_errors = validate_page_schema(schema, component_registry)
        if schema_errors:
            errors.extend(schema_errors)
        fixed_schemas.append(_normalize_page_schema(schema, idx))

    updated["page_schemas"] = fixed_schemas
    _sync_pages_with_schemas(
        updated.get("session_id"),
        fixed_schemas,
        event_emitter,
    )

    data_model = _resolve_data_model(updated)
    migration_summary = await _provision_data_model(updated.get("session_id"), data_model)
    if migration_summary is not None:
        updated["data_model_migration"] = {
            "version": _data_model_version(data_model),
            "summary": migration_summary,
        }
    else:
        updated.pop("data_model_migration", None)

    if errors:
        summary = "; ".join(errors[:8])
        if len(errors) > 8:
            summary += f" (+{len(errors) - 8} more)"
        updated["error"] = f"Component registry validation failed: {summary}"

    return updated


def _fallback_page_schemas(state: dict, registry: dict) -> List[dict]:
    pages = _extract_pages(state)
    if not pages:
        pages = [{"slug": "index", "title": "Home", "role": "landing"}]

    registry_ids = _registered_component_ids(registry)
    components_by_id = {comp_id: comp_id for comp_id in registry_ids}

    def pick(*candidates: str) -> str | None:
        for candidate in candidates:
            if candidate in components_by_id:
                return candidate
        return next(iter(components_by_id), None)

    schemas: List[dict] = []
    for page in pages:
        slug = str(page.get("slug") or "index")
        title = page.get("title") or page.get("name") or slug.title()
        role = str(page.get("role") or "").lower()
        components: List[dict] = []

        nav_id = pick("nav-primary", "nav-bottom")
        if nav_id:
            components.append(
                {
                    "id": nav_id,
                    "key": f"{nav_id}-1",
                    "props": _nav_props(pages),
                }
            )

        if role in {"landing", "home"} or slug in {"index", "home"}:
            hero_id = pick("hero-banner")
            if hero_id:
                components.append(
                    {
                        "id": hero_id,
                        "key": f"{hero_id}-1",
                        "props": {
                            "title": _static(str(title)),
                            "subtitle": _static(_goal_from_doc(state)),
                        },
                    }
                )

        header_id = pick("section-header")
        if header_id:
            components.append(
                {
                    "id": header_id,
                    "key": f"{header_id}-1",
                    "props": {
                        "title": _static(str(title)),
                        "subtitle": _static(_goal_from_doc(state)),
                    },
                }
            )

        grid_id = pick("list-grid", "list-simple")
        if grid_id:
            components.append(
                {
                    "id": grid_id,
                    "key": f"{grid_id}-1",
                    "props": {
                        "title": _static("Highlights"),
                        "items": _static(_default_list_items()),
                        "columns": _static(2),
                    },
                }
            )

        footer_id = pick("footer-simple")
        if footer_id:
            components.append(
                {
                    "id": footer_id,
                    "key": f"{footer_id}-1",
                    "props": _footer_props(pages),
                }
            )

        if not components and components_by_id:
            fallback_id = next(iter(components_by_id))
            components.append(
                {
                    "id": fallback_id,
                    "key": f"{fallback_id}-1",
                    "props": {},
                }
            )

        schemas.append(
            {
                "slug": slug,
                "title": title,
                "layout": "default",
                "components": components,
            }
        )

    return schemas


def _extract_pages(state: dict) -> List[dict]:
    pages = state.get("pages")
    if isinstance(pages, list) and pages:
        return [page for page in pages if isinstance(page, dict)]

    product_doc = state.get("product_doc") or {}
    if isinstance(product_doc, dict):
        structured = product_doc.get("structured") if isinstance(product_doc.get("structured"), dict) else product_doc
        if isinstance(structured, dict):
            doc_pages = structured.get("pages")
            if isinstance(doc_pages, list):
                return [page for page in doc_pages if isinstance(page, dict)]

    return []


def _registered_component_ids(registry: dict) -> List[str]:
    components = registry.get("components") if isinstance(registry, dict) else None
    if not isinstance(components, list):
        return []
    return [
        str(item.get("id"))
        for item in components
        if isinstance(item, dict) and item.get("id")
    ]


def _goal_from_doc(state: dict) -> str:
    product_doc = state.get("product_doc")
    if not isinstance(product_doc, dict):
        return ""
    structured = product_doc.get("structured") if isinstance(product_doc.get("structured"), dict) else product_doc
    goal = structured.get("goal") if isinstance(structured, dict) else None
    return str(goal or "").strip()


def _static(value: Any) -> Dict[str, Any]:
    return {"type": "static", "value": value}


def _nav_props(pages: List[dict]) -> Dict[str, Any]:
    links = []
    for page in pages[:4]:
        slug = str(page.get("slug") or "index")
        label = page.get("title") or slug.title()
        href = "/" if slug in {"index", "home"} else f"/{slug}"
        links.append({"label": label, "href": href, "active": slug in {"index", "home"}})
    return {
        "brand": _static("Instant Coffee"),
        "links": _static(links),
    }


def _footer_props(pages: List[dict]) -> Dict[str, Any]:
    links = []
    for page in pages[:4]:
        slug = str(page.get("slug") or "index")
        label = page.get("title") or slug.title()
        href = "/" if slug in {"index", "home"} else f"/{slug}"
        links.append({"label": label, "href": href})
    return {
        "links": _static(links),
    }


def _default_list_items() -> List[Dict[str, Any]]:
    return [
        {"title": "Curated collections", "subtitle": "Hand-picked for the journey"},
        {"title": "Smart reminders", "subtitle": "Never miss a key update"},
        {"title": "Personalized insights", "subtitle": "Tailored to your workflow"},
        {"title": "Fast checkout", "subtitle": "One tap to complete"},
    ]


def _normalize_page_schema(schema: dict, index: int) -> dict:
    title = str(schema.get("title") or "").strip()
    slug = _normalize_slug(schema.get("slug"), title, index)
    schema["slug"] = slug
    schema["title"] = title or _title_from_slug(slug)
    return schema


def _normalize_slug(raw: Any, title: str, index: int) -> str:
    path = str(raw or "").strip()
    if path in {"/", "/index", "index", "home", "/home"}:
        return "index"
    if path.startswith("/"):
        path = path[1:]
    path = path.replace("/", "-").replace(":", "-")
    slug = _slugify(path)
    if not slug:
        slug = _slugify(title)
    if not slug:
        slug = f"page-{index + 1}"
    return slug


def _slugify(text: str) -> str:
    value = str(text or "").strip().lower()
    value = re.sub(r"[^a-z0-9-]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value[:40].rstrip("-")


def _title_from_slug(slug: str) -> str:
    return str(slug or "Page").replace("-", " ").title()


def _sync_pages_with_schemas(
    session_id: Any,
    schemas: List[dict],
    event_emitter: Any | None,
) -> None:
    if not session_id or not schemas:
        return
    resolved_emitter = event_emitter if hasattr(event_emitter, "emit") else None
    try:
        with transaction_scope() as db:
            service = PageService(db, event_emitter=resolved_emitter)
            for idx, schema in enumerate(schemas):
                if not isinstance(schema, dict):
                    continue
                slug = str(schema.get("slug") or "").strip().lower()
                if not slug:
                    continue
                title = str(schema.get("title") or "").strip() or _title_from_slug(slug)
                description = str(schema.get("description") or schema.get("summary") or "").strip()
                try:
                    existing = service.get_by_slug(session_id, slug)
                    if existing is None:
                        service.create(
                            session_id=session_id,
                            title=title,
                            slug=slug,
                            description=description,
                            order_index=idx,
                        )
                        continue
                    updates: dict[str, Any] = {}
                    if title and title != existing.title:
                        updates["title"] = title
                    if description != existing.description:
                        updates["description"] = description
                    if idx != existing.order_index:
                        updates["order_index"] = idx
                    if updates:
                        service.update(existing.id, **updates)
                except Exception:
                    logger.debug("Failed to sync page %s", slug)
    except Exception:
        logger.exception("Failed to sync pages from LangGraph schemas")


__all__ = ["generate_node"]
