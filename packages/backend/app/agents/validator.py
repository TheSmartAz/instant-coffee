from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from .aesthetic_scorer import AestheticScorer
from .style_refiner import StyleRefiner
from ..schemas.validation import AestheticScore

logger = logging.getLogger(__name__)


@dataclass
class RewriteAttempt:
    version: int
    html: str
    score: AestheticScore
    timestamp: datetime


class AestheticValidator:
    THRESHOLD = 18
    MAX_ATTEMPTS = 2

    def __init__(
        self,
        db,
        session_id: str,
        settings,
        *,
        event_emitter=None,
    ) -> None:
        self.db = db
        self.session_id = session_id
        self.settings = settings
        self.event_emitter = event_emitter
        self.scorer = AestheticScorer(
            db,
            session_id,
            settings,
            event_emitter=event_emitter,
            agent_id="aesthetic_scorer_1",
            emit_lifecycle_events=False,
        )
        self.style_refiner = StyleRefiner(
            db,
            session_id,
            settings,
            event_emitter=event_emitter,
            agent_id="style_refiner_1",
            emit_lifecycle_events=False,
        )

    async def validate_and_refine(
        self,
        html: str,
        *,
        product_type: Optional[str],
    ) -> tuple[str, Optional[AestheticScore], list[RewriteAttempt]]:
        if product_type not in {"landing", "card", "invitation"}:
            return html, None, []

        attempts: list[RewriteAttempt] = []
        current_html = html

        original_score = await self.scorer.score(current_html, product_type=product_type)
        attempts.append(RewriteAttempt(0, current_html, original_score, datetime.now(timezone.utc)))

        if original_score.total >= self.THRESHOLD:
            return current_html, original_score, attempts

        try:
            refiner_html = await self.style_refiner.refine(
                current_html,
                score=original_score,
                product_type=product_type,
            )
        except Exception:
            logger.exception("Style refiner failed; returning original HTML")
            return current_html, original_score, attempts

        refiner_score = await self.scorer.score(refiner_html, product_type=product_type)
        attempts.append(RewriteAttempt(1, refiner_html, refiner_score, datetime.now(timezone.utc)))

        if refiner_score.total < original_score.total:
            return current_html, original_score, attempts

        current_html = refiner_html
        current_score = refiner_score

        if current_score.total >= self.THRESHOLD or self.MAX_ATTEMPTS < 2:
            return current_html, current_score, attempts

        try:
            refiner_html_2 = await self.style_refiner.refine(
                current_html,
                score=current_score,
                product_type=product_type,
            )
        except Exception:
            logger.exception("Second refinement failed; keeping previous HTML")
            return current_html, current_score, attempts

        refiner_score_2 = await self.scorer.score(refiner_html_2, product_type=product_type)
        attempts.append(RewriteAttempt(2, refiner_html_2, refiner_score_2, datetime.now(timezone.utc)))

        if refiner_score_2.total >= current_score.total:
            return refiner_html_2, refiner_score_2, attempts
        return current_html, current_score, attempts


__all__ = ["AestheticValidator", "RewriteAttempt"]
