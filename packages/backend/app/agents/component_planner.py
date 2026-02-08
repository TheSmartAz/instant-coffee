from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .base import BaseAgent
from .prompts import get_component_planner_prompt
from ..llm.model_pool import ModelRole


@dataclass
class ComponentPlanResult:
    plan: Dict[str, Any]
    tokens_used: int = 0


class ComponentPlannerAgent(BaseAgent):
    agent_type = "component_plan"

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
            model_role=ModelRole.EXPANDER,
        )
        self.system_prompt = get_component_planner_prompt()

    async def plan(
        self,
        *,
        product_doc: Any,
        sitemap_pages: List[Dict[str, Any]],
        design_direction: Optional[Dict[str, Any]] = None,
    ) -> ComponentPlanResult:
        structured = _coerce_structured(product_doc)
        payload = {
            "structured": structured,
            "pages": sitemap_pages,
            "design_direction": design_direction or {},
        }
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]
        response = await self._call_llm(
            messages=messages,
            agent_type=self.agent_type,
            temperature=self.settings.temperature,
            context="component_plan",
        )
        tokens_used = response.token_usage.total_tokens if response.token_usage else 0
        plan = _parse_json_response(response.content or "")
        if plan is None:
            plan = {"components": [], "page_map": {}}
        return ComponentPlanResult(plan=plan, tokens_used=tokens_used)


def _coerce_structured(product_doc: Any) -> Dict[str, Any]:
    if product_doc is None:
        return {}
    if isinstance(product_doc, dict):
        structured = product_doc.get("structured")
        if isinstance(structured, dict):
            return structured
        if isinstance(product_doc, dict):
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


__all__ = ["ComponentPlannerAgent", "ComponentPlanResult"]
