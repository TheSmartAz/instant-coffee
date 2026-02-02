from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession

from ..db.models import (
    Page,
    PageVersion,
    ProductDoc,
    ProjectSnapshot,
    ProjectSnapshotDoc,
    ProjectSnapshotPage,
    Session as SessionModel,
    VersionSource,
)
from ..events.models import SnapshotCreatedEvent
from ..services.event_store import EventStoreService
from ..services.product_doc import ProductDocService
from ..events.emitter import EventEmitter


class PinnedLimitExceeded(ValueError):
    def __init__(self, current_pinned: List[str]) -> None:
        super().__init__("Maximum 2 snapshots can be pinned")
        self.current_pinned = current_pinned


class SnapshotUnavailableError(ValueError):
    pass


@dataclass
class SnapshotPagePayload:
    page_id: str
    slug: str
    title: str
    order_index: int
    rendered_html: str


class ProjectSnapshotService:
    def __init__(
        self,
        db: DbSession,
        *,
        event_emitter: EventEmitter | None = None,
    ) -> None:
        self.db = db
        self._event_emitter = event_emitter

    def create_snapshot(
        self,
        session_id: str,
        source: VersionSource | str,
        label: Optional[str] = None,
    ) -> ProjectSnapshot:
        session = self.db.get(SessionModel, session_id)
        if session is None:
            raise ValueError("Session not found")
        product_doc = (
            self.db.query(ProductDoc)
            .filter(ProductDoc.session_id == session_id)
            .first()
        )
        if product_doc is None:
            raise ValueError("ProductDoc not found")

        pages = self._load_pages(session_id)

        snapshot: Optional[ProjectSnapshot] = None
        for attempt in range(3):
            try:
                with self.db.begin_nested():
                    snapshot = self._create_snapshot_record(
                        session_id=session_id,
                        source=source,
                        label=label,
                        product_doc=product_doc,
                        pages=pages,
                    )
                    self.apply_retention_policy(session_id)
                break
            except IntegrityError:
                self.db.rollback()
                if attempt >= 2:
                    raise
        if snapshot is None:
            raise ValueError("Failed to create snapshot")
        return snapshot

    def get_snapshots(
        self,
        session_id: str,
        include_released: bool = False,
    ) -> List[ProjectSnapshot]:
        query = self.db.query(ProjectSnapshot).filter(ProjectSnapshot.session_id == session_id)
        if not include_released:
            query = query.filter(ProjectSnapshot.is_released.is_(False))
        return query.order_by(ProjectSnapshot.created_at.desc()).all()

    def get_snapshot(self, snapshot_id: str) -> Optional[ProjectSnapshot]:
        return self.db.get(ProjectSnapshot, snapshot_id)

    def rollback_to_snapshot(self, session_id: str, snapshot_id: str) -> ProjectSnapshot:
        snapshot = self.db.get(ProjectSnapshot, snapshot_id)
        if snapshot is None or snapshot.session_id != session_id:
            raise ValueError("Snapshot not found")
        if snapshot.is_released:
            raise SnapshotUnavailableError("Snapshot content has been released")
        if snapshot.doc is None:
            raise SnapshotUnavailableError("Snapshot content missing")

        product_doc = (
            self.db.query(ProductDoc)
            .filter(ProductDoc.session_id == session_id)
            .first()
        )
        if product_doc is None:
            raise ValueError("ProductDoc not found")

        rollback_snapshot: Optional[ProjectSnapshot] = None

        with self.db.begin_nested():
            now = datetime.utcnow()
            product_doc.content = snapshot.doc.content or ""
            product_doc.structured = snapshot.doc.structured or {}
            self.db.add(product_doc)

            ProductDocService(self.db, event_emitter=self._event_emitter).create_history(
                product_doc.id,
                content=product_doc.content,
                structured=product_doc.structured,
                source=VersionSource.AUTO,
                change_summary=f"Rollback to snapshot {snapshot.snapshot_number}",
            )

            for snap_page in snapshot.pages:
                page = self.db.get(Page, snap_page.page_id)
                if page is None:
                    continue
                page.title = snap_page.title
                page.slug = snap_page.slug
                page.order_index = snap_page.order_index

                page_version = self._create_page_version(
                    page_id=page.id,
                    html=snap_page.rendered_html or "",
                    source=VersionSource.AUTO,
                )
                page.current_version_id = page_version.id
                page.updated_at = now
                self.db.add(page)

            pages = self._load_pages(session_id)
            rollback_snapshot = self._create_snapshot_record(
                session_id=session_id,
                source=VersionSource.ROLLBACK,
                label=None,
                product_doc=product_doc,
                pages=pages,
            )
            self.apply_retention_policy(session_id)

        if rollback_snapshot is None:
            raise ValueError("Failed to create rollback snapshot")
        return rollback_snapshot

    def pin_snapshot(self, snapshot_id: str) -> ProjectSnapshot:
        snapshot = self.db.get(ProjectSnapshot, snapshot_id)
        if snapshot is None:
            raise ValueError("Snapshot not found")
        if snapshot.is_released:
            raise SnapshotUnavailableError("Snapshot content has been released")
        if snapshot.is_pinned:
            return snapshot
        current_pinned = self._get_pinned_snapshot_ids(snapshot.session_id)
        if len(current_pinned) >= 2:
            raise PinnedLimitExceeded(current_pinned)
        snapshot.is_pinned = True
        self.db.add(snapshot)
        self.db.flush()
        return snapshot

    def unpin_snapshot(self, snapshot_id: str) -> ProjectSnapshot:
        snapshot = self.db.get(ProjectSnapshot, snapshot_id)
        if snapshot is None:
            raise ValueError("Snapshot not found")
        if not snapshot.is_pinned:
            return snapshot
        snapshot.is_pinned = False
        self.db.add(snapshot)
        self.db.flush()
        return snapshot

    def list_pinned_snapshot_ids(self, session_id: str) -> List[str]:
        return self._get_pinned_snapshot_ids(session_id)

    def apply_retention_policy(self, session_id: str) -> int:
        snapshots = (
            self.db.query(ProjectSnapshot)
            .filter(ProjectSnapshot.session_id == session_id)
            .order_by(ProjectSnapshot.created_at.desc())
            .all()
        )
        auto_keep = [snap for snap in snapshots if snap.source == VersionSource.AUTO][:5]
        pinned_keep = [snap for snap in snapshots if snap.is_pinned][:2]
        keep_ids = {snap.id for snap in auto_keep + pinned_keep}

        released_count = 0
        now = datetime.utcnow()
        for snapshot in snapshots:
            if snapshot.id in keep_ids:
                continue
            if snapshot.is_released:
                continue
            snapshot.is_released = True
            snapshot.released_at = now
            if snapshot.doc is not None:
                snapshot.doc.content = None
                snapshot.doc.structured = None
                snapshot.doc.global_style = None
                snapshot.doc.design_direction = None
            for page in snapshot.pages:
                page.rendered_html = None
            self.db.add(snapshot)
            released_count += 1
        return released_count

    def _normalize_source(self, source: VersionSource | str) -> VersionSource:
        if isinstance(source, VersionSource):
            return source
        return VersionSource(str(source))

    def _next_snapshot_number(self, session_id: str) -> int:
        query = (
            self.db.query(func.max(ProjectSnapshot.snapshot_number))
            .filter(ProjectSnapshot.session_id == session_id)
        )
        try:
            query = query.with_for_update()
        except Exception:
            pass
        current = query.scalar()
        return 1 if current is None else int(current) + 1

    def _extract_styles(self, structured: Optional[dict]) -> tuple[dict, dict]:
        payload = structured or {}
        if not isinstance(payload, dict):
            payload = {}
        global_style = payload.get("global_style") or payload.get("globalStyle") or {}
        if not isinstance(global_style, dict):
            global_style = {}
        design_direction = payload.get("design_direction") or payload.get("designDirection") or {}
        if not isinstance(design_direction, dict):
            design_direction = {}
        return global_style, design_direction

    def _load_pages(self, session_id: str) -> List[Page]:
        return (
            self.db.query(Page)
            .filter(Page.session_id == session_id)
            .order_by(Page.order_index.asc(), Page.created_at.asc())
            .all()
        )

    def _build_page_payloads(self, pages: List[Page]) -> List[SnapshotPagePayload]:
        html_by_page = self._resolve_page_html(pages)
        payloads: List[SnapshotPagePayload] = []
        for page in pages:
            payloads.append(
                SnapshotPagePayload(
                    page_id=page.id,
                    slug=page.slug,
                    title=page.title,
                    order_index=page.order_index,
                    rendered_html=html_by_page.get(page.id, ""),
                )
            )
        return payloads

    def _resolve_page_html(self, pages: List[Page]) -> dict:
        html_by_page: dict[str, str] = {}
        current_ids = [page.current_version_id for page in pages if page.current_version_id]
        if current_ids:
            versions = (
                self.db.query(PageVersion)
                .filter(PageVersion.id.in_(current_ids))
                .all()
            )
            versions_by_id = {version.id: version for version in versions}
            for page in pages:
                if page.current_version_id in versions_by_id:
                    html_by_page[page.id] = versions_by_id[page.current_version_id].html or ""

        missing_page_ids = [page.id for page in pages if page.id not in html_by_page]
        if missing_page_ids:
            subquery = (
                self.db.query(
                    PageVersion.page_id,
                    func.max(PageVersion.version).label("max_version"),
                )
                .filter(PageVersion.page_id.in_(missing_page_ids))
                .group_by(PageVersion.page_id)
                .subquery()
            )
            latest_versions = (
                self.db.query(PageVersion)
                .join(
                    subquery,
                    (PageVersion.page_id == subquery.c.page_id)
                    & (PageVersion.version == subquery.c.max_version),
                )
                .all()
            )
            for version in latest_versions:
                html_by_page[version.page_id] = version.html or ""

        return html_by_page

    def _create_snapshot_record(
        self,
        *,
        session_id: str,
        source: VersionSource | str,
        label: Optional[str],
        product_doc: ProductDoc,
        pages: List[Page],
    ) -> ProjectSnapshot:
        snapshot_number = self._next_snapshot_number(session_id)
        snapshot = ProjectSnapshot(
            session_id=session_id,
            snapshot_number=snapshot_number,
            label=label,
            source=self._normalize_source(source),
        )
        self.db.add(snapshot)
        self.db.flush()

        structured = (
            deepcopy(product_doc.structured)
            if isinstance(product_doc.structured, dict)
            else {}
        )
        global_style, design_direction = self._extract_styles(structured)
        global_style = deepcopy(global_style)
        design_direction = deepcopy(design_direction)

        doc = ProjectSnapshotDoc(
            snapshot_id=snapshot.id,
            content=product_doc.content,
            structured=structured,
            global_style=global_style,
            design_direction=design_direction,
            product_doc_version=product_doc.version,
        )
        self.db.add(doc)

        page_payloads = self._build_page_payloads(pages)
        for payload in page_payloads:
            self.db.add(
                ProjectSnapshotPage(
                    snapshot_id=snapshot.id,
                    page_id=payload.page_id,
                    slug=payload.slug,
                    title=payload.title,
                    order_index=payload.order_index,
                    rendered_html=payload.rendered_html,
                )
            )
        self.db.flush()
        self._record_snapshot_created(snapshot)
        return snapshot

    def _record_snapshot_created(self, snapshot: ProjectSnapshot) -> None:
        event = SnapshotCreatedEvent(
            session_id=snapshot.session_id,
            snapshot_id=snapshot.id,
            snapshot_number=snapshot.snapshot_number,
            source=getattr(snapshot.source, "value", snapshot.source),
            label=snapshot.label,
        )
        if self._event_emitter:
            self._event_emitter.emit(event)
            return
        try:
            EventStoreService(self.db).store_event(
                snapshot.session_id,
                event.type.value,
                event.model_dump(mode="json", exclude={"type", "timestamp", "session_id"}),
                source="session",
                created_at=event.timestamp,
            )
        except Exception:
            # Avoid breaking snapshot creation if persistence fails.
            pass

    def _create_page_version(
        self,
        *,
        page_id: str,
        html: str,
        source: VersionSource,
    ) -> PageVersion:
        next_version = (
            self.db.query(func.max(PageVersion.version))
            .filter(PageVersion.page_id == page_id)
            .scalar()
        )
        next_version = 1 if next_version is None else int(next_version) + 1
        record = PageVersion(
            page_id=page_id,
            version=next_version,
            html=html,
            source=source,
        )
        self.db.add(record)
        self.db.flush()
        return record

    def _get_pinned_snapshot_ids(self, session_id: str) -> List[str]:
        snapshots = (
            self.db.query(ProjectSnapshot)
            .filter(ProjectSnapshot.session_id == session_id)
            .filter(ProjectSnapshot.is_pinned.is_(True))
            .order_by(ProjectSnapshot.created_at.desc())
            .all()
        )
        return [snapshot.id for snapshot in snapshots]


__all__ = ["ProjectSnapshotService", "PinnedLimitExceeded", "SnapshotUnavailableError"]
