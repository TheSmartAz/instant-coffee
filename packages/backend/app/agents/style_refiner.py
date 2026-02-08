from __future__ import annotations

import html as html_lib
import logging
import re
from typing import Optional

from .base import BaseAgent
from .prompts import get_style_refiner_prompt
from ..llm.model_pool import ModelRole
from ..schemas.validation import AestheticScore

logger = logging.getLogger(__name__)


class StyleRefiner(BaseAgent):
    agent_type = "style_refiner"

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
            model_role=ModelRole.STYLE_REFINER,
        )
        self.system_prompt = get_style_refiner_prompt()

    async def refine(
        self,
        html: str,
        *,
        score: Optional[AestheticScore] = None,
        product_type: Optional[str] = None,
    ) -> str:
        if not html:
            return html
        user_parts = [f"Current HTML:\n{html}"]
        if score is not None:
            user_parts.append(f"Issues:\n{score.issues}")
            try:
                auto_checks = score.auto_checks.model_dump()
            except Exception:
                auto_checks = None
            if auto_checks:
                user_parts.append(f"Auto-checks:\n{auto_checks}")
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": "\n\n".join(user_parts)},
        ]

        try:
            response = await self._call_llm(
                messages=messages,
                agent_type=self.agent_type,
                temperature=self.settings.temperature,
                stream=False,
                context="style-refiner",
                model_role=ModelRole.STYLE_REFINER,
                product_type=product_type,
            )
            refined = self._extract_html(getattr(response, "content", "") or "")
            if refined:
                return refined
        except Exception:
            logger.exception("StyleRefiner failed, returning original HTML")

        return html

    def _extract_html(self, content: str) -> str:
        if not content:
            return ""
        candidate = html_lib.unescape(content.strip())
        if not candidate:
            return ""

        fence_match = re.search(r"```(?:html)?\s*(.*?)```", candidate, re.DOTALL | re.IGNORECASE)
        if fence_match:
            candidate = fence_match.group(1).strip()

        marker_match = re.search(r"<HTML_OUTPUT>(.*?)</HTML_OUTPUT>", candidate, re.DOTALL | re.IGNORECASE)
        if marker_match:
            return marker_match.group(1).strip()

        marker_start = re.search(r"<HTML_OUTPUT>", candidate, re.IGNORECASE)
        if marker_start:
            candidate = candidate[marker_start.end() :].strip()

        lowered = candidate.lower()
        start = lowered.find("<!doctype html")
        end = lowered.rfind("</html>")
        if start != -1:
            if end != -1 and end > start:
                return candidate[start : end + len("</html>")].strip()
            return candidate[start:].strip()

        html_match = re.search(r"<html\b[\s\S]*?</html>", candidate, re.IGNORECASE)
        if html_match:
            return html_match.group(0).strip()
        return ""


__all__ = ["StyleRefiner"]
