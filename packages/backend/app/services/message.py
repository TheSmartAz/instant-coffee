from __future__ import annotations

from typing import List

from sqlalchemy.orm import Session as DbSession

from ..db.models import Message


class MessageService:
    def __init__(self, db: DbSession) -> None:
        self.db = db

    def add_message(self, session_id: str, role: str, content: str) -> Message:
        normalized = role.strip().lower()
        if normalized not in {"user", "assistant"}:
            raise ValueError("Invalid role")
        record = Message(session_id=session_id, role=normalized, content=content)
        self.db.add(record)
        self.db.flush()
        return record

    def get_messages(self, session_id: str, *, limit: int = 50, offset: int = 0) -> List[Message]:
        return (
            self.db.query(Message)
            .filter(Message.session_id == session_id)
            .order_by(Message.timestamp.asc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def clear_messages(self, session_id: str) -> int:
        return (
            self.db.query(Message)
            .filter(Message.session_id == session_id)
            .delete(synchronize_session=False)
        )


__all__ = ["MessageService"]
