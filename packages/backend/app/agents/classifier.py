from __future__ import annotations

import asyncio
from collections import OrderedDict
from dataclasses import dataclass
import json
import logging
import re
from typing import Optional

from .base import BaseAgent
from ..llm.model_pool import ModelRole

logger = logging.getLogger(__name__)


_CLASSIFIER_PROMPT = """You are a product type classifier. Given the user request, classify into one of:
- ecommerce: Online store, shopping, product catalog, cart, checkout
- travel: Trip itineraries, schedules, day plans, destinations
- manual: Documentation/manual/guide sites, knowledge bases
- kanban: Task boards, project management, kanban workflows
- landing: Landing page, marketing page, product showcase
- card: Greeting card, invitation, single-page graphic
- invitation: Event invitation, RSVP
- booking: Appointment booking, reservation, scheduling (legacy)
- dashboard: Data visualization, analytics, admin panel (legacy)

Return JSON: {"type": "...", "confidence": 0.0-1.0, "reasoning": "..."}
"""

_VALID_TYPES = {
    "ecommerce",
    "travel",
    "manual",
    "kanban",
    "booking",
    "dashboard",
    "landing",
    "card",
    "invitation",
}


@dataclass
class ProductClassification:
    product_type: str
    confidence: float
    reasoning: str
    model_used: Optional[str] = None


class ProductClassifier(BaseAgent):
    agent_type = "classifier"

    _cache: "OrderedDict[str, ProductClassification]" = OrderedDict()
    _cache_limit = 128

    def __init__(
        self,
        db,
        session_id: str,
        settings,
        *,
        model: Optional[str] = None,
        timeout_seconds: float = 5.0,
    ) -> None:
        super().__init__(db, session_id, settings, model_role=ModelRole.CLASSIFIER)
        self.model = model
        self.timeout_seconds = float(timeout_seconds)

    async def classify(self, user_input: str, *, use_llm: bool = True) -> ProductClassification:
        normalized = self._normalize_text(user_input)
        if normalized:
            cached = self._get_cached(normalized)
            if cached is not None:
                return cached

        heuristic = self._heuristic_classify(user_input)
        if not use_llm or not user_input.strip():
            self._set_cached(normalized, heuristic)
            return heuristic

        model = self.model
        messages = [
            {"role": "system", "content": _CLASSIFIER_PROMPT},
            {"role": "user", "content": user_input.strip()},
        ]
        try:
            response = await asyncio.wait_for(
                self._call_llm(
                    messages=messages,
                    agent_type=self.agent_type,
                    model=model,
                    temperature=0.0,
                    max_tokens=200,
                    context="product-classifier",
                ),
                timeout=self.timeout_seconds,
            )
            parsed = self._parse_response(response.content or "")
        except Exception as exc:
            logger.warning("Product classification failed, falling back to heuristics: %s", exc)
            parsed = None

        if parsed is None:
            resolved = heuristic
        else:
            resolved = parsed
            if resolved.confidence < 0.5:
                if heuristic.confidence >= resolved.confidence:
                    resolved = heuristic
            if resolved.product_type not in _VALID_TYPES:
                resolved = heuristic

        resolved = ProductClassification(
            product_type=resolved.product_type,
            confidence=resolved.confidence,
            reasoning=resolved.reasoning,
            model_used=model or self._resolve_preferred_model("classifier") or self.settings.model,
        )
        if normalized:
            self._set_cached(normalized, resolved)
        return resolved

    def _heuristic_classify(self, user_input: str) -> ProductClassification:
        text = (user_input or "").lower()
        if not text.strip():
            return ProductClassification(
                product_type="landing",
                confidence=0.2,
                reasoning="Empty input; defaulted to landing.",
            )

        keywords = {
            "ecommerce": [
                "ecommerce",
                "e-commerce",
                "online store",
                "shop",
                "shopping",
                "product catalog",
                "catalog",
                "cart",
                "checkout",
                "sell",
                "storefront",
                "商品",
                "购物车",
                "下单",
                "商城",
                "电商",
            ],
            "travel": [
                "travel",
                "trip",
                "itinerary",
                "journey",
                "day plan",
                "schedule",
                "行程",
                "旅行",
                "日程",
                "景点",
            ],
            "manual": [
                "manual",
                "docs",
                "documentation",
                "guide",
                "handbook",
                "knowledge base",
                "说明书",
                "文档",
                "手册",
                "指南",
            ],
            "kanban": [
                "kanban",
                "board",
                "task",
                "project management",
                "workflow",
                "看板",
                "任务",
                "项目管理",
            ],
            "booking": [
                "booking",
                "book",
                "appointment",
                "reservation",
                "schedule",
                "calendar",
                "reserve",
            ],
            "dashboard": [
                "dashboard",
                "analytics",
                "admin",
                "metrics",
                "reporting",
                "kpi",
                "insights",
            ],
            "landing": [
                "landing",
                "marketing",
                "campaign",
                "product page",
                "hero",
                "showcase",
                "cta",
                "落地页",
                "宣传页",
                "首页",
            ],
            "card": [
                "card",
                "greeting",
                "birthday",
                "thank you",
                "postcard",
                "valentine",
                "贺卡",
            ],
            "invitation": [
                "invitation",
                "invite",
                "rsvp",
                "event",
                "wedding",
                "party",
                "save the date",
                "邀请函",
                "请柬",
            ],
        }

        scores = {key: 0 for key in keywords}
        for kind, words in keywords.items():
            for word in words:
                if self._keyword_match(text, word):
                    scores[kind] += 2 if " " in word else 1

        if scores["invitation"]:
            if any(term in text for term in ("rsvp", "wedding", "event", "party")):
                scores["invitation"] += 2

        best_type = "landing"
        best_score = 0
        for kind, score in scores.items():
            if score > best_score:
                best_type = kind
                best_score = score

        if best_score == 0:
            return ProductClassification(
                product_type="landing",
                confidence=0.4,
                reasoning="No strong signals detected; defaulted to landing.",
            )

        confidence = min(0.95, 0.55 + 0.1 * best_score)
        return ProductClassification(
            product_type=best_type,
            confidence=confidence,
            reasoning="Heuristic keyword match.",
        )

    def _parse_response(self, content: str) -> ProductClassification | None:
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

        product_type = str(payload.get("type") or payload.get("product_type") or "").lower().strip()
        if product_type not in _VALID_TYPES:
            product_type = "landing"
        confidence = payload.get("confidence")
        try:
            confidence = float(confidence) if confidence is not None else 0.0
        except (TypeError, ValueError):
            confidence = 0.0
        if confidence > 1.0 and confidence <= 100.0:
            confidence = confidence / 100.0
        confidence = max(0.0, min(confidence, 1.0))
        reasoning = str(payload.get("reasoning") or "LLM classification")
        return ProductClassification(
            product_type=product_type,
            confidence=confidence,
            reasoning=reasoning,
        )

    def _normalize_text(self, text: str) -> str:
        cleaned = re.sub(r"\s+", " ", (text or "").strip().lower())
        cleaned = re.sub(r"[^a-z0-9\s-]", "", cleaned)
        return cleaned

    def _get_cached(self, key: str) -> ProductClassification | None:
        if not key:
            return None
        cached = self._cache.get(key)
        if cached is None:
            return None
        self._cache.move_to_end(key)
        return cached

    def _set_cached(self, key: str, value: ProductClassification) -> None:
        if not key:
            return
        self._cache[key] = value
        self._cache.move_to_end(key)
        if len(self._cache) > self._cache_limit:
            self._cache.popitem(last=False)

    def _keyword_match(self, text: str, keyword: str) -> bool:
        if not keyword:
            return False
        if re.match(r"^[a-z0-9]+$", keyword):
            return re.search(rf"\b{re.escape(keyword)}\b", text) is not None
        return keyword in text


__all__ = ["ProductClassifier", "ProductClassification"]
