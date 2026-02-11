from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy.orm import Session as DbSession

from ..db.models import Message, Thread


class ThreadService:
    def __init__(self, db: DbSession) -> None:
        self.db = db

    def list_threads(self, session_id: str) -> List[Thread]:
        return (
            self.db.query(Thread)
            .filter(Thread.session_id == session_id)
            .order_by(Thread.created_at.asc())
            .all()
        )

    def get_thread(self, thread_id: str) -> Optional[Thread]:
        return self.db.get(Thread, thread_id)

    def create_thread(
        self,
        session_id: str,
        title: Optional[str] = None,
    ) -> Thread:
        thread = Thread(
            id=uuid.uuid4().hex,
            session_id=session_id,
            title=title,
        )
        self.db.add(thread)
        self.db.flush()
        return thread

    def ensure_default_thread(self, session_id: str) -> Thread:
        """Return the first thread for a session, creating one if none exist."""
        existing = (
            self.db.query(Thread)
            .filter(Thread.session_id == session_id)
            .order_by(Thread.created_at.asc())
            .first()
        )
        if existing is not None:
            return existing
        thread = self.create_thread(session_id, title=None)
        # Assign any orphan messages (pre-thread) to this new default thread
        self.db.query(Message).filter(
            Message.session_id == session_id,
            Message.thread_id.is_(None),
        ).update({"thread_id": thread.id}, synchronize_session=False)
        return thread

    def delete_thread(self, thread_id: str) -> bool:
        thread = self.db.get(Thread, thread_id)
        if thread is None:
            return False
        self.db.delete(thread)
        self.db.flush()
        return True

    def get_message_count(self, thread_id: str) -> int:
        return (
            self.db.query(Message)
            .filter(Message.thread_id == thread_id)
            .count()
        )

    def update_title(self, thread_id: str, title: str) -> Optional[Thread]:
        thread = self.db.get(Thread, thread_id)
        if thread is None:
            return None
        thread.title = title
        self.db.flush()
        return thread

    def auto_title_if_empty(self, thread_id: str, user_message: str) -> Optional[str]:
        """Set thread title from user message if it has no title yet.

        Returns the new title if set, None otherwise.
        """
        thread = self.db.get(Thread, thread_id)
        if thread is None or thread.title:
            return None
        title = user_message.strip()
        # Strip interview XML tags
        import re
        title = re.sub(r"<INTERVIEW_ANSWERS>[\s\S]*?</INTERVIEW_ANSWERS>", "", title).strip()
        if not title:
            return None
        if len(title) > 50:
            title = title[:47] + "..."
        thread.title = title
        self.db.flush()
        return title


__all__ = ["ThreadService"]
