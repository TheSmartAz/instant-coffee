from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session as DbSession

from ..db.models import TokenUsage


class TokenTrackerService:
    def __init__(self, db: DbSession) -> None:
        self.db = db

    def record_usage(
        self,
        session_id: str,
        *,
        agent_type: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
    ) -> TokenUsage:
        total_tokens = input_tokens + output_tokens
        record = TokenUsage(
            session_id=session_id,
            agent_type=agent_type,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost_usd=cost_usd,
        )
        self.db.add(record)
        self.db.flush()
        return record

    def summarize_session(self, session_id: str) -> dict:
        totals_row = (
            self.db.query(
                func.coalesce(func.sum(TokenUsage.input_tokens), 0),
                func.coalesce(func.sum(TokenUsage.output_tokens), 0),
                func.coalesce(func.sum(TokenUsage.total_tokens), 0),
                func.coalesce(func.sum(TokenUsage.cost_usd), 0.0),
            )
            .filter(TokenUsage.session_id == session_id)
            .one()
        )
        total = {
            "input_tokens": int(totals_row[0] or 0),
            "output_tokens": int(totals_row[1] or 0),
            "total_tokens": int(totals_row[2] or 0),
            "cost_usd": float(totals_row[3] or 0.0),
        }

        by_agent: dict[str, dict] = {}
        rows = (
            self.db.query(
                TokenUsage.agent_type,
                func.coalesce(func.sum(TokenUsage.input_tokens), 0),
                func.coalesce(func.sum(TokenUsage.output_tokens), 0),
                func.coalesce(func.sum(TokenUsage.total_tokens), 0),
                func.coalesce(func.sum(TokenUsage.cost_usd), 0.0),
            )
            .filter(TokenUsage.session_id == session_id)
            .group_by(TokenUsage.agent_type)
            .all()
        )
        for agent_type, input_tokens, output_tokens, total_tokens, cost_usd in rows:
            agent = agent_type or "unknown"
            by_agent[agent] = {
                "input_tokens": int(input_tokens or 0),
                "output_tokens": int(output_tokens or 0),
                "total_tokens": int(total_tokens or 0),
                "cost_usd": float(cost_usd or 0.0),
            }

        return {"total": total, "by_agent": by_agent}


__all__ = ["TokenTrackerService"]
