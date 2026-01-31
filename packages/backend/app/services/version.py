from __future__ import annotations

from typing import List, Optional

from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session as DbSession

from ..db.models import Session, Version


class VersionService:
    def __init__(self, db: DbSession) -> None:
        self.db = db

    def create_version(self, session_id: str, html: str, description: Optional[str] = None) -> Version:
        session = self.db.get(Session, session_id)
        if session is None:
            raise ValueError("Session not found")

        next_version = (
            self.db.query(func.max(Version.version))
            .filter(Version.session_id == session_id)
            .scalar()
        )
        next_version = 0 if next_version is None else int(next_version) + 1

        record = Version(
            session_id=session_id,
            version=next_version,
            html=html,
            description=description,
        )
        session.current_version = next_version
        session.updated_at = datetime.utcnow()
        self.db.add(record)
        self.db.add(session)
        self.db.flush()
        return record

    def get_versions(self, session_id: str, *, limit: int = 50, offset: int = 0) -> List[Version]:
        return (
            self.db.query(Version)
            .filter(Version.session_id == session_id)
            .order_by(Version.version.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_version(self, session_id: str, version: int) -> Optional[Version]:
        return (
            self.db.query(Version)
            .filter(Version.session_id == session_id)
            .filter(Version.version == version)
            .first()
        )

    def rollback(self, session_id: str, version: int) -> Optional[Version]:
        session = self.db.get(Session, session_id)
        if session is None:
            return None
        target = self.get_version(session_id, version)
        if target is None:
            return None
        session.current_version = version
        self.db.add(session)
        self.db.flush()
        return target


__all__ = ["VersionService"]
