from __future__ import annotations

import logging
from typing import Any, Optional

from .base import BaseAgent
from .prompts import get_expander_prompt
from ..llm.model_pool import ModelRole

logger = logging.getLogger(__name__)


class ExpanderAgent(BaseAgent):
    agent_type = "expander"

    def __init__(
        self,
        db,
        session_id: str,
        settings,
        event_emitter=None,
        agent_id: Optional[str] = None,
        task_id: Optional[str] = None,
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
        self.system_prompt = get_expander_prompt()

    async def expand_page(
        self,
        *,
        user_message: str,
        page_spec: dict,
        product_doc_context: Optional[str] = None,
    ) -> str:
        page_title = str(page_spec.get("title") or page_spec.get("slug") or "Page")
        page_slug = str(page_spec.get("slug") or "index")
        page_purpose = str(page_spec.get("purpose") or "")
        sections = page_spec.get("sections") if isinstance(page_spec.get("sections"), list) else []
        sections_text = ", ".join(str(item) for item in sections if str(item).strip())

        parts = [
            f"User Request: {user_message}",
            f"Page: {page_title} ({page_slug})",
        ]
        if page_purpose:
            parts.append(f"Purpose: {page_purpose}")
        if sections_text:
            parts.append(f"Sections: {sections_text}")
        if product_doc_context:
            parts.append(f"Product Doc Context:\n{product_doc_context}")

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": "\n\n".join(parts)},
        ]

        response = await self._call_llm(
            messages=messages,
            agent_type=self.agent_type,
            temperature=min(self.settings.temperature, 0.5),
            max_tokens=800,
            context="expander",
        )
        return self._sanitize_notes(getattr(response, "content", ""))

    @staticmethod
    def _sanitize_notes(raw: Any) -> str:
        if not raw:
            return ""
        text = str(raw).strip()
        if not text:
            return ""
        max_chars = 1500
        if len(text) > max_chars:
            return text[:max_chars].rstrip() + "..."
        return text


__all__ = ["ExpanderAgent"]
