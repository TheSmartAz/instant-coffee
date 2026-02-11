"""Data cleanup service for removing old sessions and associated data.

Provides configurable retention policies to prevent unbounded database growth.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session as DbSession

from ..db.models import Message, Session as SessionModel, Version

logger = logging.getLogger(__name__)


class CleanupPolicy:
    """Configurable data retention policy."""

    def __init__(
        self,
        max_session_age_days: int = 90,
        max_sessions: int = 500,
        max_messages_per_session: int = 1000,
        dry_run: bool = False,
    ):
        self.max_session_age_days = max_session_age_days
        self.max_sessions = max_sessions
        self.max_messages_per_session = max_messages_per_session
        self.dry_run = dry_run


class CleanupService:
    """Removes stale data according to retention policies."""

    def __init__(self, db: DbSession, policy: CleanupPolicy | None = None):
        self.db = db
        self.policy = policy or CleanupPolicy()

    def cleanup_old_sessions(self) -> int:
        """Delete sessions older than max_session_age_days. Returns count deleted."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.policy.max_session_age_days)
        old_sessions = (
            self.db.query(SessionModel)
            .filter(SessionModel.updated_at < cutoff)
            .all()
        )
        if not old_sessions:
            return 0

        count = len(old_sessions)
        if self.policy.dry_run:
            logger.info("Dry run: would delete %d old sessions", count)
            return count

        for session in old_sessions:
            self.db.delete(session)
        self.db.commit()
        logger.info("Deleted %d sessions older than %d days", count, self.policy.max_session_age_days)
        return count

    def cleanup_excess_sessions(self) -> int:
        """Keep only the most recent max_sessions. Returns count deleted."""
        total = self.db.query(func.count(SessionModel.id)).scalar() or 0
        if total <= self.policy.max_sessions:
            return 0

        excess = total - self.policy.max_sessions
        oldest = (
            self.db.query(SessionModel)
            .order_by(SessionModel.updated_at.asc())
            .limit(excess)
            .all()
        )
        if not oldest:
            return 0

        count = len(oldest)
        if self.policy.dry_run:
            logger.info("Dry run: would delete %d excess sessions", count)
            return count

        for session in oldest:
            self.db.delete(session)
        self.db.commit()
        logger.info("Deleted %d excess sessions (limit: %d)", count, self.policy.max_sessions)
        return count

    def cleanup_excess_messages(self) -> int:
        """Trim messages per session to max_messages_per_session. Returns count deleted."""
        total_deleted = 0
        sessions_with_excess = (
            self.db.query(Message.session_id, func.count(Message.id).label("cnt"))
            .group_by(Message.session_id)
            .having(func.count(Message.id) > self.policy.max_messages_per_session)
            .all()
        )

        for session_id, msg_count in sessions_with_excess:
            excess = msg_count - self.policy.max_messages_per_session
            oldest_msgs = (
                self.db.query(Message)
                .filter(Message.session_id == session_id)
                .order_by(Message.created_at.asc())
                .limit(excess)
                .all()
            )
            if self.policy.dry_run:
                total_deleted += len(oldest_msgs)
                continue
            for msg in oldest_msgs:
                self.db.delete(msg)
            total_deleted += len(oldest_msgs)

        if total_deleted > 0 and not self.policy.dry_run:
            self.db.commit()
            logger.info("Deleted %d excess messages across sessions", total_deleted)
        return total_deleted

    def run_all(self) -> dict[str, int]:
        """Run all cleanup policies. Returns summary of deletions."""
        results = {
            "old_sessions": self.cleanup_old_sessions(),
            "excess_sessions": self.cleanup_excess_sessions(),
            "excess_messages": self.cleanup_excess_messages(),
        }
        logger.info("Cleanup complete: %s", results)
        return results
