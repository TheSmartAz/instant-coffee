from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from ...config import get_settings
from ...agents.component_registry import ComponentRegistryAgent
from ..mcp import cache_mcp_handlers, get_mcp_handlers, load_mcp_tooling
from ...schemas.component import ComponentRegistry, normalize_design_tokens

logger = logging.getLogger(__name__)

def _as_dict(state: Any) -> dict:
    if isinstance(state, dict):
        return dict(state)
    if hasattr(state, "__dict__"):
        return dict(state.__dict__)
    return {}


async def component_registry_node(state: Any, *, event_emitter: Any | None = None) -> dict:
    updated = _as_dict(state)

    existing = updated.get("component_registry")
    style_tokens = updated.get("style_tokens")
    input_hash = _compute_registry_hash(
        product_doc=updated.get("product_doc"),
        pages=updated.get("pages"),
        style_tokens=style_tokens,
    )
    existing_hash = updated.get("component_registry_hash")

    if isinstance(existing, dict) and existing.get("components"):
        if existing_hash and existing_hash != input_hash:
            logger.debug("Component registry hash mismatch; regenerating")
        else:
            if not existing.get("tokens"):
                existing["tokens"] = normalize_design_tokens(style_tokens).model_dump()
            updated["component_registry"] = existing
            updated["component_registry_hash"] = input_hash
            return updated

    tokens = normalize_design_tokens(style_tokens).model_dump()
    defaults = _default_components()
    llm_components = await _generate_components_with_llm(
        state=updated,
        component_library=defaults,
        event_emitter=event_emitter,
    )
    components = _merge_component_definitions(defaults, llm_components)
    registry = {"components": components, "tokens": tokens}

    try:
        registry = ComponentRegistry.model_validate(registry).model_dump()
    except ValidationError:
        pass

    updated["component_registry"] = registry
    updated["component_registry_hash"] = input_hash
    return updated


def _prop(name: str, prop_type: str, *, required: bool = False, default: Any = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"name": name, "type": prop_type, "required": required}
    if default is not None:
        payload["default"] = default
    return payload


def _default_components() -> List[Dict[str, Any]]:
    return [
        {
            "id": "nav-primary",
            "type": "nav",
            "slots": ["brand"],
            "props": [
                _prop("brand", "string", default="Instant Coffee"),
                _prop("logo", "asset"),
                _prop("links", "binding"),
                _prop("showSearch", "boolean"),
                _prop("showCart", "boolean"),
                _prop("cartCount", "number"),
            ],
        },
        {
            "id": "nav-bottom",
            "type": "nav",
            "slots": [],
            "props": [
                _prop("items", "binding"),
            ],
        },
        {
            "id": "hero-banner",
            "type": "hero",
            "slots": ["title", "subtitle"],
            "props": [
                _prop("title", "string", required=True),
                _prop("subtitle", "string"),
                _prop("backgroundImage", "asset"),
                _prop("backgroundColor", "string"),
                _prop("cta", "binding"),
                _prop("alignment", "string", default="left"),
            ],
        },
        {
            "id": "card-product",
            "type": "card",
            "slots": ["title", "price"],
            "props": [
                _prop("image", "asset"),
                _prop("title", "string", required=True),
                _prop("price", "number"),
                _prop("originalPrice", "number"),
                _prop("badge", "string"),
                _prop("rating", "number"),
                _prop("href", "string"),
            ],
        },
        {
            "id": "card-task",
            "type": "card",
            "slots": ["title", "description"],
            "props": [
                _prop("title", "string", required=True),
                _prop("description", "string"),
                _prop("status", "string"),
                _prop("assignee", "string"),
                _prop("dueDate", "string"),
                _prop("tags", "binding"),
            ],
        },
        {
            "id": "card-timeline",
            "type": "card",
            "slots": ["title", "description"],
            "props": [
                _prop("title", "string", required=True),
                _prop("time", "string"),
                _prop("description", "string"),
                _prop("badge", "string"),
                _prop("status", "string"),
            ],
        },
        {
            "id": "list-simple",
            "type": "list",
            "slots": ["items"],
            "props": [
                _prop("title", "string"),
                _prop("items", "binding"),
            ],
        },
        {
            "id": "list-grid",
            "type": "list",
            "slots": ["items"],
            "props": [
                _prop("title", "string"),
                _prop("items", "binding"),
                _prop("columns", "number", default=2),
            ],
        },
        {
            "id": "form-basic",
            "type": "form",
            "slots": ["fields"],
            "props": [
                _prop("title", "string"),
                _prop("description", "string"),
                _prop("fields", "binding"),
                _prop("submitLabel", "string"),
            ],
        },
        {
            "id": "form-checkout",
            "type": "form",
            "slots": ["sections"],
            "props": [
                _prop("title", "string"),
                _prop("sections", "binding"),
                _prop("submitLabel", "string"),
            ],
        },
        {
            "id": "button-primary",
            "type": "button",
            "slots": ["label"],
            "props": [
                _prop("label", "string", required=True),
                _prop("href", "string"),
                _prop("variant", "string", default="primary"),
                _prop("fullWidth", "boolean"),
                _prop("size", "string"),
            ],
            "variants": ["primary"],
        },
        {
            "id": "button-secondary",
            "type": "button",
            "slots": ["label"],
            "props": [
                _prop("label", "string", required=True),
                _prop("href", "string"),
                _prop("variant", "string", default="secondary"),
                _prop("fullWidth", "boolean"),
                _prop("size", "string"),
            ],
            "variants": ["secondary"],
        },
        {
            "id": "section-header",
            "type": "section",
            "slots": ["title", "subtitle"],
            "props": [
                _prop("title", "string", required=True),
                _prop("subtitle", "string"),
                _prop("align", "string", default="left"),
            ],
        },
        {
            "id": "cart-summary",
            "type": "summary",
            "slots": [],
            "props": [
                _prop("itemCount", "number"),
                _prop("subtotal", "number"),
                _prop("shipping", "number"),
                _prop("tax", "number"),
                _prop("total", "number"),
                _prop("ctaLabel", "string"),
                _prop("ctaHref", "string"),
            ],
        },
        {
            "id": "order-summary",
            "type": "summary",
            "slots": [],
            "props": [
                _prop("orderId", "string"),
                _prop("status", "string"),
                _prop("date", "string"),
                _prop("items", "binding"),
                _prop("total", "number"),
            ],
        },
        {
            "id": "footer-simple",
            "type": "footer",
            "slots": ["links"],
            "props": [
                _prop("links", "binding"),
                _prop("copyright", "string"),
            ],
        },
        {
            "id": "breadcrumb",
            "type": "nav",
            "slots": ["items"],
            "props": [
                _prop("items", "binding"),
            ],
        },
        {
            "id": "tabs-basic",
            "type": "tabs",
            "slots": ["tabs"],
            "props": [
                _prop("tabs", "binding"),
                _prop("defaultTabId", "string"),
            ],
        },
        {
            "id": "modal-confirm",
            "type": "modal",
            "slots": ["title", "description"],
            "props": [
                _prop("open", "boolean", default=False),
                _prop("title", "string"),
                _prop("description", "string"),
                _prop("confirmLabel", "string"),
                _prop("cancelLabel", "string"),
            ],
        },
        {
            "id": "toast-message",
            "type": "toast",
            "slots": ["message"],
            "props": [
                _prop("message", "string", required=True),
                _prop("type", "string", default="info"),
                _prop("open", "boolean", default=True),
            ],
        },
    ]


def _merge_component_definitions(
    defaults: List[Dict[str, Any]],
    overrides: Optional[List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    if not overrides:
        return defaults
    by_id = {
        str(item.get("id")): dict(item)
        for item in defaults
        if isinstance(item, dict) and item.get("id")
    }
    for override in overrides:
        if not isinstance(override, dict):
            continue
        comp_id = override.get("id")
        if not comp_id or comp_id not in by_id:
            continue
        merged = dict(by_id[comp_id])
        for key in ("type", "slots", "props", "variants"):
            value = override.get(key)
            if value is not None and value != []:
                merged[key] = value
        by_id[comp_id] = merged
    return list(by_id.values())


def _compute_registry_hash(*, product_doc: Any, pages: Any, style_tokens: Any) -> str:
    payload = {
        "product_doc": _coerce_payload(product_doc),
        "pages": _coerce_payload(pages),
        "style_tokens": _coerce_payload(style_tokens),
    }
    normalized = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return "sha256:" + hashlib.sha256(normalized).hexdigest()


def _coerce_payload(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        try:
            dumped = value.model_dump()
            if isinstance(dumped, dict):
                return dumped
        except Exception:
            pass
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        return value
    if hasattr(value, "__dict__"):
        return dict(value.__dict__)
    return value


async def _generate_components_with_llm(
    *,
    state: dict,
    component_library: List[Dict[str, Any]],
    event_emitter: Any | None = None,
) -> Optional[List[Dict[str, Any]]]:
    settings = get_settings()
    if not settings.use_langgraph:
        return None
    if not (settings.openai_api_key or settings.default_key):
        return None

    session_id = state.get("session_id") or "session"
    emitter = event_emitter if hasattr(event_emitter, "emit") else None
    tools = state.get("mcp_tools") if isinstance(state, dict) else None
    if not isinstance(tools, list):
        tools = None
    tool_handlers = get_mcp_handlers(state.get("session_id") if isinstance(state, dict) else None)
    if tools and not tool_handlers:
        tooling = await load_mcp_tooling()
        if tooling is not None:
            tools = tooling.tools
            tool_handlers = tooling.tool_handlers
            cache_mcp_handlers(state.get("session_id") if isinstance(state, dict) else None, tool_handlers)
    if not tools or not tool_handlers:
        tools = None
        tool_handlers = None

    agent = ComponentRegistryAgent(
        None,
        str(session_id),
        settings,
        event_emitter=emitter,
        emit_lifecycle_events=False,
    )
    try:
        result = await agent.generate(
            product_doc=state.get("product_doc"),
            pages=state.get("pages") or [],
            style_tokens=state.get("style_tokens") or {},
            component_library=component_library,
            tools=tools,
            tool_handlers=tool_handlers,
        )
    except Exception:
        logger.exception("Component registry LLM generation failed")
        return None

    components = result.components if result else None
    if not components:
        return None
    return components


__all__ = ["component_registry_node"]
