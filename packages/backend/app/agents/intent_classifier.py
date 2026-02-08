from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
import logging
from typing import Optional, Sequence

from .base import BaseAgent
from ..db.models import Page, ProductDoc
from ..llm.model_pool import ModelRole

logger = logging.getLogger(__name__)


_INTENT_PROMPT = """You are a routing classifier for Instant Coffee, an AI system that edits or regenerates website pages.

Decide the user's intent based on their message and the existing pages.

Return JSON only in this shape:
{"intent": "product_doc_update|page_refine|generation_pipeline|direct_reply", "confidence": 0.0-1.0, "target_pages": ["slug"], "reasoning": "..."}

Guidelines:
- product_doc_update: change requirements, goals, features, sitemap/page list, design direction, or the product document.
- page_refine: modify content/style/layout of existing pages.
- generation_pipeline: regenerate or rebuild pages from scratch.
- direct_reply: general questions or non-change requests.

Use only provided page slugs for target_pages. If unsure, return an empty list.
Return JSON only.
"""

_VALID_INTENTS = {
    "product_doc_update",
    "page_refine",
    "generation_pipeline",
    "direct_reply",
}


@dataclass
class IntentClassification:
    intent: str
    confidence: float
    target_pages: list[str]
    reasoning: str
    model_used: Optional[str] = None


class IntentClassifier(BaseAgent):
    agent_type = "intent_classifier"

    def __init__(
        self,
        db,
        session_id: str,
        settings,
        *,
        model: Optional[str] = None,
        timeout_seconds: float = 5.0,
    ) -> None:
        super().__init__(
            db,
            session_id,
            settings,
            model_role=ModelRole.CLASSIFIER,
        )
        self.model = model
        self.timeout_seconds = float(timeout_seconds)

    async def classify(
        self,
        user_input: str,
        *,
        pages: Sequence[Page] | None = None,
        product_doc: ProductDoc | None = None,
    ) -> IntentClassification:
        text = (user_input or "").strip()
        if not text:
            return IntentClassification(
                intent="direct_reply",
                confidence=0.2,
                target_pages=[],
                reasoning="Empty input.",
            )

        page_lines = []
        page_slugs = set()
        for page in pages or []:
            slug = str(page.slug or "").strip()
            if not slug:
                continue
            page_slugs.add(slug.lower())
            title = str(page.title or "").strip()
            if title:
                page_lines.append(f"- {slug}: {title}")
            else:
                page_lines.append(f"- {slug}")

        doc_state = "present" if product_doc is not None else "missing"
        page_block = "\n".join(page_lines) if page_lines else "(none)"

        messages = [
            {"role": "system", "content": _INTENT_PROMPT},
            {
                "role": "user",
                "content": (
                    f"User message:\n{text}\n\n"
                    f"Product doc: {doc_state}\n"
                    f"Existing pages (slug: title):\n{page_block}"
                ),
            },
        ]

        try:
            response = await asyncio.wait_for(
                self._call_llm(
                    messages=messages,
                    agent_type=self.agent_type,
                    model=self.model,
                    temperature=0.0,
                    max_tokens=200,
                    context="intent-classifier",
                    model_role=ModelRole.CLASSIFIER,
                ),
                timeout=self.timeout_seconds,
            )
            parsed = self._parse_response(response.content or "")
        except Exception as exc:
            logger.warning("Intent classification failed, falling back to direct reply: %s", exc)
            parsed = None

        if parsed is None:
            return IntentClassification(
                intent="direct_reply",
                confidence=0.3,
                target_pages=[],
                reasoning="Classifier fallback.",
            )

        intent = parsed.intent if parsed.intent in _VALID_INTENTS else "direct_reply"
        targets = [slug for slug in parsed.target_pages if slug.lower() in page_slugs]
        model_used = self.model or self._resolve_preferred_model("classifier") or self.settings.model
        return IntentClassification(
            intent=intent,
            confidence=parsed.confidence,
            target_pages=targets,
            reasoning=parsed.reasoning,
            model_used=model_used,
        )

    def _parse_response(self, content: str) -> IntentClassification | None:
        text = (content or "").strip()
        if not text:
            return None
        payload = None
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    payload = json.loads(text[start : end + 1])
                except json.JSONDecodeError:
                    payload = None

        if not isinstance(payload, dict):
            return None

        intent = str(payload.get("intent") or payload.get("route") or "").strip().lower()
        confidence = payload.get("confidence")
        try:
            confidence = float(confidence) if confidence is not None else 0.0
        except (TypeError, ValueError):
            confidence = 0.0
        if confidence > 1.0 and confidence <= 100.0:
            confidence = confidence / 100.0
        confidence = max(0.0, min(confidence, 1.0))

        targets_raw = payload.get("target_pages") or payload.get("targets") or []
        if isinstance(targets_raw, str):
            targets = [item.strip() for item in targets_raw.split(",") if item.strip()]
        elif isinstance(targets_raw, list):
            targets = [str(item).strip() for item in targets_raw if str(item).strip()]
        else:
            targets = []

        reasoning = str(payload.get("reasoning") or "LLM classification")

        return IntentClassification(
            intent=intent or "direct_reply",
            confidence=confidence,
            target_pages=targets,
            reasoning=reasoning,
        )


__all__ = ["IntentClassifier", "IntentClassification"]
