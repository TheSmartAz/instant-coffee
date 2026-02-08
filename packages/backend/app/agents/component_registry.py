from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from .base import BaseAgent
from .prompts import get_component_registry_prompt
from ..llm.model_pool import ModelRole


@dataclass
class ComponentRegistryResult:
    components: List[Dict[str, Any]]
    tokens_used: int = 0


class ComponentRegistryAgent(BaseAgent):
    agent_type = "component_registry"

    def __init__(
        self,
        db,
        session_id: str,
        settings,
        event_emitter=None,
        agent_id=None,
        task_id=None,
        emit_lifecycle_events: bool = True,
    ) -> None:
        super().__init__(
            db,
            session_id,
            settings,
            event_emitter=event_emitter,
            agent_id=agent_id,
            task_id=task_id,
            emit_lifecycle_events=emit_lifecycle_events,
            model_role=ModelRole.WRITER,
        )
        self.system_prompt = get_component_registry_prompt()

    async def generate(
        self,
        *,
        product_doc: Any,
        pages: List[Dict[str, Any]],
        style_tokens: Optional[Dict[str, Any]] = None,
        component_library: Optional[List[Dict[str, Any]]] = None,
        tools: Optional[list[Any]] = None,
        tool_handlers: Optional[dict[str, Callable[..., Any]]] = None,
    ) -> ComponentRegistryResult:
        payload = {
            "structured": _coerce_structured(product_doc),
            "pages": pages,
            "style_tokens": style_tokens or {},
            "component_library": component_library or [],
        }
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]
        if tools and tool_handlers:
            response = await self._call_llm_with_tools(
                messages=messages,
                tools=tools,
                tool_handlers=tool_handlers,
                agent_type=self.agent_type,
                temperature=self.settings.temperature,
                context="component_registry",
            )
        else:
            response = await self._call_llm(
                messages=messages,
                agent_type=self.agent_type,
                temperature=self.settings.temperature,
                context="component_registry",
            )
        tokens_used = response.token_usage.total_tokens if response.token_usage else 0
        payload = _parse_json_response(response.content or "")
        components: List[Dict[str, Any]] = []
        if isinstance(payload, dict):
            raw = payload.get("components")
            if isinstance(raw, list):
                components = [item for item in raw if isinstance(item, dict)]
        return ComponentRegistryResult(components=components, tokens_used=tokens_used)


def _coerce_structured(product_doc: Any) -> Dict[str, Any]:
    if product_doc is None:
        return {}
    if isinstance(product_doc, dict):
        structured = product_doc.get("structured")
        if isinstance(structured, dict):
            return structured
        return product_doc
    structured = getattr(product_doc, "structured", None)
    return structured if isinstance(structured, dict) else {}


def _parse_json_response(content: str) -> Optional[Dict[str, Any]]:
    text = (content or "").strip()
    if not text:
        return None
    try:
        payload = json.loads(text)
        if isinstance(payload, dict):
            return payload
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            payload = json.loads(text[start : end + 1])
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError:
            return None
    return None


__all__ = ["ComponentRegistryAgent", "ComponentRegistryResult"]
