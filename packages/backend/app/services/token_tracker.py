from __future__ import annotations

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
        records = (
            self.db.query(TokenUsage)
            .filter(TokenUsage.session_id == session_id)
            .all()
        )
        total = {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "cost_usd": 0.0,
        }
        by_agent: dict[str, dict] = {}
        for record in records:
            total["input_tokens"] += record.input_tokens
            total["output_tokens"] += record.output_tokens
            total["total_tokens"] += record.total_tokens
            total["cost_usd"] += record.cost_usd

            agent = record.agent_type or "unknown"
            agent_usage = by_agent.get(
                agent,
                {
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                    "cost_usd": 0.0,
                },
            )
            agent_usage["input_tokens"] += record.input_tokens
            agent_usage["output_tokens"] += record.output_tokens
            agent_usage["total_tokens"] += record.total_tokens
            agent_usage["cost_usd"] += record.cost_usd
            by_agent[agent] = agent_usage

        return {"total": total, "by_agent": by_agent}


__all__ = ["TokenTrackerService"]
