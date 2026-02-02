from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy import case, func
from sqlalchemy.orm import Session as DbSession

from ..db.models import Page, PageVersion, VersionSource
from ..events.emitter import EventEmitter
from ..events.models import PagePreviewReadyEvent, PageVersionCreatedEvent
from ..utils.html import inline_css, strip_prompt_artifacts


class PageVersionNotFoundError(Exception):
    pass


class PageVersionReleasedError(Exception):
    pass


class PinnedLimitExceeded(Exception):
    def __init__(self, message: str, current_pinned: Optional[list[int]] = None) -> None:
        super().__init__(message)
        self.current_pinned = current_pinned or []


class PageVersionService:
    def __init__(self, db: DbSession, event_emitter: Optional[EventEmitter] = None) -> None:
        self.db = db
        self._event_emitter = event_emitter

    def list_by_page(self, page_id: str, *, include_released: bool = False) -> List[PageVersion]:
        return self.get_versions(page_id, include_released=include_released)

    def get_versions(self, page_id: str, *, include_released: bool = False) -> List[PageVersion]:
        query = self.db.query(PageVersion).filter(PageVersion.page_id == page_id)
        if not include_released:
            query = query.filter(PageVersion.is_released.is_(False))
        return query.order_by(PageVersion.version.desc()).all()

    def get_current(self, page_id: str) -> Optional[PageVersion]:
        page = self.db.get(Page, page_id)
        if page is None or page.current_version_id is None:
            return None
        return self.db.get(PageVersion, page.current_version_id)

    def get_by_id(self, version_id: int) -> Optional[PageVersion]:
        return self.db.get(PageVersion, version_id)

    def create_version(
        self,
        page_id: str,
        html: str,
        description: Optional[str] = None,
        source: str | VersionSource = VersionSource.AUTO,
        *,
        preview_url: Optional[str] = None,
        fallback_used: bool = False,
        fallback_excerpt: Optional[str] = None,
    ) -> PageVersion:
        page = self.db.get(Page, page_id)
        if page is None:
            raise ValueError("Page not found")

        next_version = (
            self.db.query(func.max(PageVersion.version))
            .filter(PageVersion.page_id == page_id)
            .scalar()
        )
        next_version = 1 if next_version is None else int(next_version) + 1

        resolved_source = source
        if isinstance(source, str):
            try:
                resolved_source = VersionSource(source)
            except ValueError as exc:
                raise ValueError("Invalid version source") from exc

        record = PageVersion(
            page_id=page_id,
            version=next_version,
            html=html or "",
            description=description,
            source=resolved_source,
            fallback_used=bool(fallback_used),
            fallback_excerpt=fallback_excerpt,
        )
        self.db.add(record)
        self.db.flush()

        page.current_version_id = record.id
        page.updated_at = datetime.utcnow()
        self.db.add(page)

        self.apply_retention_policy(page_id)

        if self._event_emitter:
            self._event_emitter.emit(
                PageVersionCreatedEvent(
                    session_id=page.session_id,
                    page_id=page.id,
                    slug=page.slug,
                    version=record.version,
                )
            )
            self._event_emitter.emit(
                PagePreviewReadyEvent(
                    session_id=page.session_id,
                    page_id=page.id,
                    slug=page.slug,
                    preview_url=preview_url,
                )
            )

        return record

    def create(
        self,
        page_id: str,
        html: str,
        description: Optional[str] = None,
        *,
        preview_url: Optional[str] = None,
        fallback_used: bool = False,
        fallback_excerpt: Optional[str] = None,
    ) -> PageVersion:
        return self.create_version(
            page_id,
            html,
            description=description,
            source=VersionSource.AUTO,
            preview_url=preview_url,
            fallback_used=fallback_used,
            fallback_excerpt=fallback_excerpt,
        )

    def rollback(self, page_id: str, version_id: int) -> Optional[PageVersion]:
        raise NotImplementedError("PageVersion rollback is no longer supported. Use ProjectSnapshot.")

    def preview_version(self, page_id: str, version_id: int) -> PageVersion:
        record = self.db.get(PageVersion, version_id)
        if record is None or record.page_id != page_id:
            raise PageVersionNotFoundError("Version not found")
        if record.is_released or record.payload_pruned_at is not None or record.html is None:
            raise PageVersionReleasedError("Version has been released")
        return record

    def pin_version(self, version_id: int) -> PageVersion:
        record = self.db.get(PageVersion, version_id)
        if record is None:
            raise PageVersionNotFoundError("Version not found")
        if record.is_released:
            raise PageVersionReleasedError("Version has been released")
        if record.is_pinned:
            return record

        pinned = (
            self.db.query(func.count(PageVersion.id))
            .filter(PageVersion.page_id == record.page_id)
            .filter(PageVersion.is_pinned.is_(True))
            .filter(PageVersion.is_released.is_(False))
            .scalar()
            or 0
        )
        if pinned >= 2:
            pinned_ids = [
                version.id
                for version in (
                    self.db.query(PageVersion)
                    .filter(PageVersion.page_id == record.page_id)
                    .filter(PageVersion.is_pinned.is_(True))
                    .filter(PageVersion.is_released.is_(False))
                    .order_by(PageVersion.version.desc())
                    .limit(2)
                    .all()
                )
            ]
            raise PinnedLimitExceeded(
                "Maximum 2 versions can be pinned per page",
                current_pinned=pinned_ids,
            )

        record.is_pinned = True
        self.db.add(record)
        self.db.flush()
        self.apply_retention_policy(record.page_id)
        return record

    def unpin_version(self, version_id: int) -> PageVersion:
        record = self.db.get(PageVersion, version_id)
        if record is None:
            raise PageVersionNotFoundError("Version not found")
        if not record.is_pinned:
            return record
        record.is_pinned = False
        self.db.add(record)
        self.db.flush()
        self.apply_retention_policy(record.page_id)
        return record

    def apply_retention_policy(self, page_id: str) -> int:
        page = self.db.get(Page, page_id)
        if page is None:
            return 0

        now = datetime.utcnow()
        keep_ids: set[int] = set()
        if page.current_version_id is not None:
            keep_ids.add(page.current_version_id)

        pinned = (
            self.db.query(PageVersion)
            .filter(PageVersion.page_id == page_id)
            .filter(PageVersion.is_pinned.is_(True))
            .filter(PageVersion.is_released.is_(False))
            .order_by(PageVersion.version.desc())
            .limit(2)
            .all()
        )
        keep_ids.update(version.id for version in pinned)

        recent_auto = (
            self.db.query(PageVersion)
            .filter(PageVersion.page_id == page_id)
            .filter(PageVersion.source == VersionSource.AUTO)
            .filter(PageVersion.is_released.is_(False))
            .order_by(PageVersion.version.desc())
            .limit(5)
            .all()
        )
        keep_ids.update(version.id for version in recent_auto)

        updated_ids: set[int] = set()
        releasable_query = (
            self.db.query(PageVersion)
            .filter(PageVersion.page_id == page_id)
            .filter(PageVersion.is_released.is_(False))
        )
        if keep_ids:
            releasable_query = releasable_query.filter(PageVersion.id.notin_(keep_ids))
        releasable = releasable_query.all()
        for version in releasable:
            version.is_released = True
            version.released_at = version.released_at or now
            if version.html is not None:
                version.html = None
            version.payload_pruned_at = version.payload_pruned_at or now
            updated_ids.add(version.id)
            self.db.add(version)

        released_to_prune = (
            self.db.query(PageVersion)
            .filter(PageVersion.page_id == page_id)
            .filter(PageVersion.is_released.is_(True))
            .filter(PageVersion.payload_pruned_at.is_(None))
            .all()
        )
        for version in released_to_prune:
            if version.html is not None:
                version.html = None
            version.payload_pruned_at = now
            if version.released_at is None:
                version.released_at = now
            updated_ids.add(version.id)
            self.db.add(version)

        self.db.flush()
        return len(updated_ids)

    def build_preview(
        self,
        page_id: str,
        *,
        global_style_css: Optional[str] = None,
    ) -> Optional[Tuple[PageVersion, str]]:
        page = self.db.get(Page, page_id)
        if page is None:
            return None
        version = None
        if page.current_version_id is not None:
            version = self.db.get(PageVersion, page.current_version_id)
        if version is None:
            version = (
                self.db.query(PageVersion)
                .filter(PageVersion.page_id == page_id)
                .order_by(PageVersion.version.desc())
                .first()
            )
        if version is None:
            return None
        html = inline_css(version.html or "", global_style_css)
        html = strip_prompt_artifacts(html)
        return version, html

    def fallback_stats_by_session(self, session_id: str, *, limit: int = 10) -> dict:
        total_versions = (
            self.db.query(func.count(PageVersion.id))
            .join(Page, PageVersion.page_id == Page.id)
            .filter(Page.session_id == session_id)
            .scalar()
            or 0
        )
        fallback_versions = (
            self.db.query(func.count(PageVersion.id))
            .join(Page, PageVersion.page_id == Page.id)
            .filter(Page.session_id == session_id)
            .filter(PageVersion.fallback_used.is_(True))
            .scalar()
            or 0
        )
        fallback_rate = (fallback_versions / total_versions) if total_versions else 0.0

        page_rows = (
            self.db.query(
                Page.id,
                Page.slug,
                func.count(PageVersion.id).label("total_versions"),
                func.sum(
                    case((PageVersion.fallback_used.is_(True), 1), else_=0)
                ).label("fallback_versions"),
                func.max(
                    case(
                        (PageVersion.fallback_used.is_(True), PageVersion.created_at),
                        else_=None,
                    )
                ).label("latest_fallback_at"),
            )
            .join(PageVersion, PageVersion.page_id == Page.id)
            .filter(Page.session_id == session_id)
            .group_by(Page.id, Page.slug)
            .order_by(Page.slug.asc())
            .all()
        )
        page_stats = [
            {
                "page_id": row.id,
                "slug": row.slug,
                "total_versions": int(row.total_versions or 0),
                "fallback_versions": int(row.fallback_versions or 0),
                "latest_fallback_at": row.latest_fallback_at,
            }
            for row in page_rows
        ]

        recent_rows = (
            self.db.query(PageVersion, Page)
            .join(Page, PageVersion.page_id == Page.id)
            .filter(Page.session_id == session_id)
            .filter(PageVersion.fallback_used.is_(True))
            .order_by(PageVersion.created_at.desc())
            .limit(limit)
            .all()
        )
        recent_fallbacks = [
            {
                "page_id": page.id,
                "slug": page.slug,
                "version": version.version,
                "created_at": version.created_at,
                "fallback_excerpt": version.fallback_excerpt,
            }
            for version, page in recent_rows
        ]

        return {
            "session_id": session_id,
            "total_versions": int(total_versions),
            "fallback_versions": int(fallback_versions),
            "fallback_rate": float(fallback_rate),
            "pages": page_stats,
            "recent_fallbacks": recent_fallbacks,
        }


__all__ = [
    "PageVersionService",
    "PageVersionNotFoundError",
    "PageVersionReleasedError",
    "PinnedLimitExceeded",
]
