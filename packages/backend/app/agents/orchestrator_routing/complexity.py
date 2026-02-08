from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import json
import logging
import re
from typing import Any, Dict, Optional

from ..base import BaseAgent
from ...llm.model_pool import ModelRole

logger = logging.getLogger(__name__)


@dataclass
class ComplexityReport:
    level: str  # simple, medium, complex
    page_count_estimate: int
    has_cross_page_data_flow: bool
    has_forms: bool
    data_structure_complexity: str  # simple, medium, complex
    scores: dict = field(default_factory=dict)


class ComplexityEvaluator(BaseAgent):
    agent_type = "complexity"

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

    async def evaluate(
        self,
        user_input: str,
        product_type: Optional[str] = None,
        *,
        use_llm: bool = True,
    ) -> ComplexityReport:
        heuristic = self._heuristic_evaluate(user_input, product_type)
        if not use_llm or not user_input.strip():
            return heuristic

        if not self._needs_llm(heuristic):
            return heuristic

        model = self.model
        prompt = self._build_prompt(user_input, product_type, heuristic)
        messages = [
            {"role": "system", "content": "You are a complexity evaluator. Return JSON only."},
            {"role": "user", "content": prompt},
        ]

        try:
            response = await asyncio.wait_for(
                self._call_llm(
                    messages=messages,
                    agent_type=self.agent_type,
                    model=model,
                    temperature=0.0,
                    max_tokens=300,
                    context="complexity-evaluator",
                ),
                timeout=self.timeout_seconds,
            )
            parsed = self._parse_response(response.content or "")
        except Exception as exc:
            logger.warning("Complexity evaluation failed, falling back to heuristics: %s", exc)
            parsed = None

        return parsed or heuristic

    def _heuristic_evaluate(self, user_input: str, product_type: Optional[str]) -> ComplexityReport:
        text = (user_input or "").lower()
        normalized_product = (product_type or "").lower().strip()

        page_count = self._estimate_page_count(text, normalized_product)
        has_forms = self._detect_forms(text)
        has_data_flow = self._detect_cross_page_flow(text, normalized_product)
        data_complexity = self._estimate_data_complexity(text, normalized_product)

        score = 0
        if page_count >= 5:
            score += 2
        elif page_count >= 3:
            score += 1

        if has_forms:
            score += 1
        if has_data_flow:
            score += 1
        if data_complexity == "complex":
            score += 2
        elif data_complexity == "medium":
            score += 1

        if page_count <= 1 and not has_forms and not has_data_flow and data_complexity == "simple":
            level = "simple"
        elif page_count > 1 and has_data_flow and data_complexity == "complex":
            level = "complex"
        elif score >= 4:
            level = "complex"
        elif score >= 2:
            level = "medium"
        else:
            level = "simple"

        return ComplexityReport(
            level=level,
            page_count_estimate=page_count,
            has_cross_page_data_flow=has_data_flow,
            has_forms=has_forms,
            data_structure_complexity=data_complexity,
            scores={
                "page_count": page_count,
                "forms": int(has_forms),
                "cross_page": int(has_data_flow),
                "data_complexity": data_complexity,
                "aggregate": score,
            },
        )

    def _needs_llm(self, report: ComplexityReport) -> bool:
        if report.level == "medium":
            return True
        if report.page_count_estimate in {2, 3} and report.data_structure_complexity != "simple":
            return True
        return False

    def _build_prompt(
        self,
        user_input: str,
        product_type: Optional[str],
        heuristic: ComplexityReport,
    ) -> str:
        return (
            "Estimate complexity for the request below.\n\n"
            f"User request: {user_input.strip()}\n"
            f"Product type: {product_type or 'unknown'}\n"
            "Return JSON with keys: level (simple|medium|complex), page_count_estimate (int), "
            "has_cross_page_data_flow (true/false), has_forms (true/false), "
            "data_structure_complexity (simple|medium|complex).\n"
            "If unsure, use the heuristic estimate as guidance:\n"
            f"Heuristic: {json.dumps(heuristic.__dict__, ensure_ascii=False)}"
        )

    def _parse_response(self, content: str) -> Optional[ComplexityReport]:
        text = (content or "").strip()
        if not text:
            return None
        payload: Any = None
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

        level = str(payload.get("level") or "").lower().strip()
        if level not in {"simple", "medium", "complex"}:
            level = "simple"

        page_count = payload.get("page_count_estimate")
        try:
            page_count = int(page_count) if page_count is not None else 1
        except (TypeError, ValueError):
            page_count = 1
        page_count = max(1, page_count)

        has_data_flow = bool(payload.get("has_cross_page_data_flow"))
        has_forms = bool(payload.get("has_forms"))
        data_complexity = str(payload.get("data_structure_complexity") or "simple").lower().strip()
        if data_complexity not in {"simple", "medium", "complex"}:
            data_complexity = "simple"

        return ComplexityReport(
            level=level,
            page_count_estimate=page_count,
            has_cross_page_data_flow=has_data_flow,
            has_forms=has_forms,
            data_structure_complexity=data_complexity,
            scores={
                "llm": True,
            },
        )

    def _estimate_page_count(self, text: str, product_type: str) -> int:
        if any(term in text for term in ("single page", "one page", "single-page", "singlepage", "landing")):
            return 1

        if any(term in text for term in ("multi-page", "multi page", "multiple pages", "multi pages")):
            return 3

        match = re.search(r"(\d+)\s+pages?", text)
        if match:
            try:
                value = int(match.group(1))
                if value > 0:
                    return value
            except ValueError:
                pass

        if product_type in {"landing", "card", "invitation"}:
            return 1
        if product_type in {"ecommerce", "travel", "manual", "kanban", "booking", "dashboard"}:
            return 3
        return 2

    def _detect_forms(self, text: str) -> bool:
        keywords = [
            "form",
            "signup",
            "sign up",
            "register",
            "contact",
            "checkout",
            "booking",
            "appointment",
            "reservation",
            "rsvp",
            "apply",
        ]
        return any(keyword in text for keyword in keywords)

    def _detect_cross_page_flow(self, text: str, product_type: str) -> bool:
        if product_type in {"ecommerce", "travel", "manual", "kanban", "booking"}:
            return True
        keywords = [
            "multi-page",
            "multiple pages",
            "flow",
            "checkout",
            "cart",
            "step",
            "wizard",
            "dashboard",
            "login",
            "profile",
        ]
        return any(keyword in text for keyword in keywords)

    def _estimate_data_complexity(self, text: str, product_type: str) -> str:
        if product_type in {"dashboard", "kanban"}:
            return "complex"
        complex_terms = [
            "analytics",
            "metrics",
            "kpi",
            "inventory",
            "orders",
            "users",
            "admin",
            "reporting",
        ]
        medium_terms = [
            "booking",
            "reservation",
            "catalog",
            "products",
            "checkout",
            "cart",
            "itinerary",
            "trip",
            "manual",
            "documentation",
            "kanban",
        ]
        if product_type in {"travel", "manual", "booking"}:
            return "medium"
        if any(term in text for term in complex_terms):
            return "complex"
        if any(term in text for term in medium_terms):
            return "medium"
        return "simple"


__all__ = ["ComplexityEvaluator", "ComplexityReport"]
