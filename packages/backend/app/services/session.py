from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from sqlalchemy import func
from sqlalchemy.orm import Session as DbSession

from ..db.models import Message, Session


class SessionService:
    def __init__(self, db: DbSession) -> None:
        self.db = db

    def create_session(self, title: Optional[str] = None) -> Session:
        session_id = uuid4().hex
        resolved_title = (title or "Untitled project").strip() or "Untitled project"
        record = Session(id=session_id, title=resolved_title)
        self.db.add(record)
        self.db.flush()
        return record

    def get_session(self, session_id: str) -> Optional[Session]:
        return self.db.get(Session, session_id)

    def update_session(self, session_id: str, **fields) -> Optional[Session]:
        record = self.db.get(Session, session_id)
        if record is None:
            return None
        for key, value in fields.items():
            if value is None:
                continue
            if hasattr(record, key):
                setattr(record, key, value)
        record.updated_at = datetime.utcnow()
        self.db.add(record)
        return record

    def list_sessions(self, *, limit: int = 20, offset: int = 0) -> List[Session]:
        return (
            self.db.query(Session)
            .order_by(Session.updated_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def count_messages(self, session_id: str) -> int:
        return (
            self.db.query(func.count(Message.id))
            .filter(Message.session_id == session_id)
            .scalar()
            or 0
        )

    def delete_session(self, session_id: str) -> bool:
        record = self.db.get(Session, session_id)
        if record is None:
            return False
        self.db.delete(record)
        return True


__all__ = ["SessionService"]
