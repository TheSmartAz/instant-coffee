from __future__ import annotations

import re
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session as DbSession

from ..db.models import Page, Session as SessionModel
from ..events.emitter import EventEmitter
from ..events.models import PageCreatedEvent
from ..schemas.page import PageCreate

_SLUG_PATTERN = re.compile(r"^[a-z0-9-]+$")


def _validate_slug(slug: str) -> str:
    if slug is None:
        raise ValueError("slug is required")
    resolved = str(slug).strip()
    if not resolved:
        raise ValueError("slug is required")
    if len(resolved) > 40:
        raise ValueError("slug must be 40 characters or fewer")
    if _SLUG_PATTERN.fullmatch(resolved) is None:
        raise ValueError("slug must match pattern [a-z0-9-]+")
    return resolved


class PageService:
    def __init__(self, db: DbSession, event_emitter: Optional[EventEmitter] = None) -> None:
        self.db = db
        self._event_emitter = event_emitter

    def list_by_session(self, session_id: str) -> List[Page]:
        return (
            self.db.query(Page)
            .filter(Page.session_id == session_id)
            .order_by(Page.order_index.asc(), Page.created_at.asc())
            .all()
        )

    def get_by_id(self, page_id: str) -> Optional[Page]:
        return self.db.get(Page, page_id)

    def get_by_slug(self, session_id: str, slug: str) -> Optional[Page]:
        return (
            self.db.query(Page)
            .filter(Page.session_id == session_id)
            .filter(Page.slug == slug)
            .first()
        )

    def create(
        self,
        session_id: str,
        title: str,
        slug: str,
        description: str = "",
        order_index: int = 0,
    ) -> Page:
        if self.db.get(SessionModel, session_id) is None:
            raise ValueError("Session not found")
        resolved_slug = _validate_slug(slug)
        if self.get_by_slug(session_id, resolved_slug) is not None:
            raise ValueError("slug already exists for session")
        resolved_title = (title or "").strip()
        if not resolved_title:
            raise ValueError("title is required")
        record = Page(
            session_id=session_id,
            title=resolved_title,
            slug=resolved_slug,
            description=description or "",
            order_index=order_index,
        )
        self.db.add(record)
        self.db.flush()
        if self._event_emitter:
            self._event_emitter.emit(
                PageCreatedEvent(
                    session_id=session_id,
                    page_id=record.id,
                    slug=record.slug,
                    title=record.title,
                )
            )
        return record

    def create_batch(self, session_id: str, pages: List[PageCreate]) -> List[Page]:
        if self.db.get(SessionModel, session_id) is None:
            raise ValueError("Session not found")
        if not pages:
            return []

        resolved_pages: List[Page] = []
        seen_slugs = set()
        for page in pages:
            resolved_slug = _validate_slug(page.slug)
            if resolved_slug in seen_slugs:
                raise ValueError(f"duplicate slug in batch: {resolved_slug}")
            seen_slugs.add(resolved_slug)
            resolved_title = (page.title or "").strip()
            if not resolved_title:
                raise ValueError("title is required")
            resolved_pages.append(
                Page(
                    session_id=session_id,
                    title=resolved_title,
                    slug=resolved_slug,
                    description=page.description or "",
                    order_index=page.order_index,
                )
            )

        existing = (
            self.db.query(Page.slug)
            .filter(Page.session_id == session_id)
            .filter(Page.slug.in_(list(seen_slugs)))
            .all()
        )
        if existing:
            duplicates = ", ".join(sorted({row[0] for row in existing}))
            raise ValueError(f"slug already exists for session: {duplicates}")

        try:
            self.db.add_all(resolved_pages)
            self.db.flush()
        except Exception:
            self.db.rollback()
            raise

        if self._event_emitter:
            for record in resolved_pages:
                self._event_emitter.emit(
                    PageCreatedEvent(
                        session_id=session_id,
                        page_id=record.id,
                        slug=record.slug,
                        title=record.title,
                    )
                )

        return resolved_pages

    def update(
        self,
        page_id: str,
        *,
        title: Optional[str] = None,
        slug: Optional[str] = None,
        description: Optional[str] = None,
        order_index: Optional[int] = None,
        current_version_id: Optional[int] = None,
    ) -> Optional[Page]:
        record = self.db.get(Page, page_id)
        if record is None:
            return None
        if title is not None:
            resolved_title = title.strip()
            if not resolved_title:
                raise ValueError("title is required")
            record.title = resolved_title
        if slug is not None:
            resolved_slug = _validate_slug(slug)
            if resolved_slug != record.slug:
                if self.get_by_slug(record.session_id, resolved_slug) is not None:
                    raise ValueError("slug already exists for session")
                record.slug = resolved_slug
        if description is not None:
            record.description = description
        if order_index is not None:
            record.order_index = order_index
        if current_version_id is not None:
            record.current_version_id = current_version_id
        record.updated_at = datetime.utcnow()
        self.db.add(record)
        return record

    def delete(self, page_id: str) -> bool:
        record = self.db.get(Page, page_id)
        if record is None:
            return False
        self.db.delete(record)
        return True


__all__ = ["PageService"]
