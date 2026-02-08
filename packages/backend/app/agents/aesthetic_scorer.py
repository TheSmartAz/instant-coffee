from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Optional

from pydantic import ValidationError

from .base import BaseAgent
from .prompts import get_aesthetic_scoring_prompt
from ..llm.model_pool import ModelRole
from ..schemas.validation import AestheticScore, AutoChecks, DimensionScores
from ..utils.validation import run_auto_checks

logger = logging.getLogger(__name__)


@dataclass
class AestheticScoringResult:
    score: AestheticScore
    raw: Optional[dict] = None


class AestheticScorer(BaseAgent):
    agent_type = "aesthetic_scorer"

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
            model_role=ModelRole.VALIDATOR,
        )
        self.system_prompt = get_aesthetic_scoring_prompt()

    async def score(self, html: str, *, product_type: Optional[str] = None) -> AestheticScore:
        auto_checks = run_auto_checks(html or "")
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": html or ""},
        ]

        try:
            response = await self._call_llm(
                messages=messages,
                agent_type=self.agent_type,
                temperature=self.settings.temperature,
                stream=False,
                context="aesthetic-scoring",
                model_role=ModelRole.VALIDATOR,
                product_type=product_type,
            )
            payload = self._parse_response(getattr(response, "content", "") or "")
            score = self._build_score(payload, auto_checks)
            if score is not None:
                return score
        except Exception:
            logger.exception("AestheticScorer failed to score, falling back to defaults")

        return self._fallback_score(auto_checks, issues=["Scoring failed; used fallback defaults."])

    def _build_score(self, payload: Optional[dict], auto_checks: AutoChecks) -> Optional[AestheticScore]:
        if not isinstance(payload, dict):
            return None
        cleaned = self._clean_payload(payload)
        cleaned["auto_checks"] = auto_checks
        try:
            return AestheticScore.model_validate(cleaned)
        except ValidationError:
            return None

    def _clean_payload(self, payload: dict) -> dict:
        dimensions = payload.get("dimensions")
        cleaned_dimensions = {}
        if isinstance(dimensions, dict):
            for key in ("typography", "contrast", "layout", "color", "cta"):
                if key in dimensions:
                    cleaned_dimensions[key] = dimensions.get(key)
        issues = payload.get("issues", [])
        if isinstance(issues, str):
            issues = [issues]
        if not isinstance(issues, list):
            issues = []
        return {
            "dimensions": cleaned_dimensions,
            "total": payload.get("total"),
            "issues": issues,
        }

    def _parse_response(self, content: str) -> Optional[dict]:
        text = (content or "").strip()
        if not text:
            return None
        payload = None
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", text)
            if match:
                try:
                    payload = json.loads(match.group(0))
                except json.JSONDecodeError:
                    payload = None
        if isinstance(payload, dict):
            return payload
        return None

    def _fallback_score(self, auto_checks: AutoChecks, *, issues: list[str]) -> AestheticScore:
        dimensions = DimensionScores(
            typography=3,
            contrast=3,
            layout=3,
            color=3,
            cta=3,
        )
        if auto_checks.wcag_contrast == "fail":
            dimensions.contrast = 2
        if auto_checks.line_height == "fail":
            dimensions.typography = min(dimensions.typography, 2)
        if auto_checks.type_scale == "fail":
            dimensions.typography = min(dimensions.typography, 2)
            dimensions.cta = min(dimensions.cta, 2)
        return AestheticScore(dimensions=dimensions, issues=issues, auto_checks=auto_checks)


__all__ = ["AestheticScorer", "AestheticScoringResult"]
