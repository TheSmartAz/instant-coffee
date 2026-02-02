from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import ValidationError
from sqlalchemy import func
from sqlalchemy.orm import Session as DbSession

from ..db.models import (
    ProductDoc,
    ProductDocHistory,
    ProductDocStatus,
    Session as SessionModel,
    VersionSource,
)
from ..events.emitter import EventEmitter
from ..events.models import (
    HistoryCreatedEvent,
    ProductDocConfirmedEvent,
    ProductDocGeneratedEvent,
    ProductDocOutdatedEvent,
    ProductDocUpdatedEvent,
)
from ..services.event_store import EventStoreService
from ..exceptions import PinnedLimitExceeded
from ..schemas.product_doc import ProductDocStructured


class ProductDocService:
    def __init__(self, db: DbSession, *, event_emitter: EventEmitter | None = None) -> None:
        self.db = db
        self._event_emitter = event_emitter

    def get_by_session_id(self, session_id: str) -> Optional[ProductDoc]:
        return (
            self.db.query(ProductDoc)
            .filter(ProductDoc.session_id == session_id)
            .first()
        )

    def create(
        self,
        session_id: str,
        content: str,
        structured: Optional[Dict[str, Any]],
        status: str | ProductDocStatus = ProductDocStatus.DRAFT,
    ) -> ProductDoc:
        session = self.db.get(SessionModel, session_id)
        if session is None:
            raise ValueError("Session not found")
        existing = self.get_by_session_id(session_id)
        if existing is not None:
            raise ValueError("ProductDoc already exists for session")

        resolved_status = self._normalize_status(status)
        resolved_structured = self._normalize_structured(structured)
        record = ProductDoc(
            session_id=session_id,
            content=content or "",
            structured=resolved_structured,
            status=resolved_status,
        )
        self.db.add(record)
        self.db.flush()
        self._emit(
            ProductDocGeneratedEvent(
                session_id=session_id,
                doc_id=record.id,
                status=self._status_value(record.status),
            )
        )
        return record

    def update(
        self,
        doc_id: str,
        content: Optional[str] = None,
        structured: Optional[Dict[str, Any]] = None,
        *,
        change_summary: Optional[str] = None,
        affected_pages: Optional[list[str]] = None,
    ) -> ProductDoc:
        record = self.db.get(ProductDoc, doc_id)
        if record is None:
            raise ValueError("ProductDoc not found")
        bump_version = content is not None or structured is not None
        if content is not None:
            record.content = content
        if structured is not None:
            merged = self._merge_structured(record.structured, structured)
            record.structured = self._normalize_structured(merged)
        if affected_pages is not None:
            record.pending_regeneration_pages = self._normalize_pages(affected_pages)
        if bump_version:
            self.create_history(
                record.id,
                content=record.content,
                structured=record.structured,
                source=VersionSource.AUTO,
                change_summary=change_summary,
            )
        record.updated_at = datetime.utcnow()
        self.db.add(record)
        self.db.flush()
        self._emit(
            ProductDocUpdatedEvent(
                session_id=record.session_id,
                doc_id=record.id,
                change_summary=change_summary,
            )
        )
        return record

    def create_history(
        self,
        product_doc_id: str,
        content: str,
        structured: Dict[str, Any],
        source: str | VersionSource = VersionSource.AUTO,
        change_summary: Optional[str] = None,
    ) -> ProductDocHistory:
        doc = self.db.get(ProductDoc, product_doc_id)
        if doc is None:
            raise ValueError("ProductDoc not found")
        resolved_source = self._normalize_source(source)
        next_version = self._next_history_version(doc.id, doc.version)
        doc.version = next_version
        doc.updated_at = datetime.utcnow()

        resolved_structured = self._normalize_structured(structured or {})
        record = ProductDocHistory(
            product_doc_id=doc.id,
            version=next_version,
            content=content or "",
            structured=resolved_structured,
            change_summary=change_summary,
            source=resolved_source,
            is_pinned=False,
            is_released=False,
        )
        self.db.add(record)
        self.db.add(doc)
        self.db.flush()
        self.apply_retention_policy(doc.id)
        event = HistoryCreatedEvent(
            session_id=doc.session_id,
            history_id=record.id,
            version=record.version,
            source=getattr(record.source, "value", record.source),
            change_summary=record.change_summary,
        )
        if self._event_emitter:
            self._event_emitter.emit(event)
        else:
            try:
                EventStoreService(self.db).store_event(
                    doc.session_id,
                    event.type.value,
                    event.model_dump(mode="json", exclude={"type", "timestamp", "session_id"}),
                    source="session",
                    created_at=event.timestamp,
                )
            except Exception:
                pass
        return record

    def get_history(
        self,
        product_doc_id: str,
        include_released: bool = False,
    ) -> list[ProductDocHistory]:
        query = (
            self.db.query(ProductDocHistory)
            .filter(ProductDocHistory.product_doc_id == product_doc_id)
        )
        if not include_released:
            query = query.filter(ProductDocHistory.is_released.is_(False))
        return query.order_by(ProductDocHistory.version.desc()).all()

    def get_history_version(self, history_id: int) -> Optional[ProductDocHistory]:
        return self.db.get(ProductDocHistory, history_id)

    def pin_history(self, history_id: int) -> ProductDocHistory:
        record = self.db.get(ProductDocHistory, history_id)
        if record is None:
            raise ValueError("ProductDocHistory not found")
        if record.is_pinned:
            return record

        pinned = (
            self.db.query(ProductDocHistory)
            .filter(ProductDocHistory.product_doc_id == record.product_doc_id)
            .filter(ProductDocHistory.is_pinned.is_(True))
            .order_by(ProductDocHistory.version.desc())
            .all()
        )
        if len(pinned) >= 2:
            raise PinnedLimitExceeded(
                "Pinned history limit reached",
                current_pinned=[item.id for item in pinned],
            )

        record.is_pinned = True
        if record.is_released:
            record.is_released = False
            record.released_at = None
        self.db.add(record)
        self.db.flush()
        self.apply_retention_policy(record.product_doc_id)
        return record

    def unpin_history(self, history_id: int) -> ProductDocHistory:
        record = self.db.get(ProductDocHistory, history_id)
        if record is None:
            raise ValueError("ProductDocHistory not found")
        if not record.is_pinned:
            return record
        record.is_pinned = False
        self.db.add(record)
        self.db.flush()
        self.apply_retention_policy(record.product_doc_id)
        return record

    def apply_retention_policy(self, product_doc_id: str) -> int:
        histories = (
            self.db.query(ProductDocHistory)
            .filter(ProductDocHistory.product_doc_id == product_doc_id)
            .order_by(ProductDocHistory.version.desc())
            .all()
        )
        if not histories:
            return 0

        pinned_keep = [record for record in histories if record.is_pinned][:2]
        keep_auto: list[ProductDocHistory] = []
        for record in histories:
            if record.source == VersionSource.AUTO:
                keep_auto.append(record)
            if len(keep_auto) >= 5:
                break

        keep_ids = {record.id for record in pinned_keep}
        keep_ids.update(record.id for record in keep_auto)

        updated = 0
        now = datetime.utcnow()
        for record in histories:
            should_release = record.id not in keep_ids
            if should_release and not record.is_released:
                record.is_released = True
                record.released_at = now
                updated += 1
            elif not should_release and record.is_released:
                record.is_released = False
                record.released_at = None
                updated += 1
        if updated:
            self.db.flush()
        return updated

    def get_versions_for_diff(
        self,
        product_doc_id: str,
        version_a: int,
        version_b: int,
    ) -> tuple[ProductDocHistory, ProductDocHistory]:
        versions = (
            self.db.query(ProductDocHistory)
            .filter(ProductDocHistory.product_doc_id == product_doc_id)
            .filter(ProductDocHistory.version.in_([version_a, version_b]))
            .all()
        )
        by_version = {record.version: record for record in versions}
        missing = [version for version in (version_a, version_b) if version not in by_version]
        if missing:
            raise ValueError(f"History versions not found: {', '.join(map(str, missing))}")
        return by_version[version_a], by_version[version_b]

    def update_status(self, doc_id: str, status: str | ProductDocStatus) -> ProductDoc:
        record = self.db.get(ProductDoc, doc_id)
        if record is None:
            raise ValueError("ProductDoc not found")
        previous_status = self._normalize_status(record.status)
        next_status = self._normalize_status(status)
        if not self._is_valid_transition(previous_status, next_status):
            raise ValueError(
                f"Invalid ProductDoc status transition: {previous_status.value} -> {next_status.value}"
            )
        if previous_status != next_status:
            record.status = next_status
            record.updated_at = datetime.utcnow()
            self.db.add(record)
            self.db.flush()
            self._emit_status_event(record, next_status)
        return record

    def confirm(self, doc_id: str) -> ProductDoc:
        return self.update_status(doc_id, ProductDocStatus.CONFIRMED)

    def mark_outdated(self, doc_id: str) -> ProductDoc:
        return self.update_status(doc_id, ProductDocStatus.OUTDATED)

    def set_pending_regeneration(self, doc_id: str, pages: list[str]) -> ProductDoc:
        record = self.db.get(ProductDoc, doc_id)
        if record is None:
            raise ValueError("ProductDoc not found")
        record.pending_regeneration_pages = self._normalize_pages(pages)
        record.updated_at = datetime.utcnow()
        self.db.add(record)
        self.db.flush()
        return record

    def _emit_status_event(self, record: ProductDoc, status: ProductDocStatus) -> None:
        if status == ProductDocStatus.CONFIRMED:
            self._emit(
                ProductDocConfirmedEvent(
                    session_id=record.session_id,
                    doc_id=record.id,
                )
            )
        elif status == ProductDocStatus.OUTDATED:
            self._emit(
                ProductDocOutdatedEvent(
                    session_id=record.session_id,
                    doc_id=record.id,
                )
            )

    def _emit(self, event) -> None:
        if self._event_emitter is None:
            return
        self._event_emitter.emit(event)

    @staticmethod
    def _status_value(status: str | ProductDocStatus) -> str:
        if isinstance(status, ProductDocStatus):
            return status.value
        return str(status)

    def _normalize_status(self, status: str | ProductDocStatus) -> ProductDocStatus:
        if isinstance(status, ProductDocStatus):
            return status
        try:
            return ProductDocStatus(str(status))
        except ValueError as exc:
            raise ValueError(f"Invalid ProductDoc status: {status}") from exc

    def _normalize_source(self, source: str | VersionSource) -> VersionSource:
        if isinstance(source, VersionSource):
            return source
        try:
            return VersionSource(str(source))
        except ValueError as exc:
            raise ValueError(f"Invalid history source: {source}") from exc

    def _normalize_structured(self, structured: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        resolved = structured or {}
        try:
            model = ProductDocStructured.model_validate(resolved)
        except ValidationError as exc:
            raise ValueError(f"Invalid structured data: {exc}") from exc
        return model.model_dump(exclude_none=True, exclude_unset=True)

    def _merge_structured(self, base: Optional[Dict[str, Any]], updates: Dict[str, Any]) -> Dict[str, Any]:
        if updates is None:
            return base or {}
        if not isinstance(updates, dict):
            raise ValueError("Structured update must be a dictionary")
        if base is None:
            return deepcopy(updates)
        merged: Dict[str, Any] = deepcopy(base)
        for key, value in updates.items():
            if value is None:
                continue
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = self._merge_structured(merged.get(key), value)
            else:
                merged[key] = value
        return merged

    @staticmethod
    def _normalize_pages(pages: list[str]) -> list[str]:
        if not pages:
            return []
        resolved: list[str] = []
        for item in pages:
            slug = str(item or "").strip()
            if slug:
                resolved.append(slug)
        return resolved

    @staticmethod
    def _is_valid_transition(
        previous: ProductDocStatus,
        next_status: ProductDocStatus,
    ) -> bool:
        if previous == next_status:
            return True
        if previous == ProductDocStatus.DRAFT and next_status == ProductDocStatus.CONFIRMED:
            return True
        if previous == ProductDocStatus.CONFIRMED and next_status == ProductDocStatus.OUTDATED:
            return True
        if previous == ProductDocStatus.OUTDATED and next_status == ProductDocStatus.CONFIRMED:
            return True
        return False

    def _next_history_version(self, product_doc_id: str, current_version: Optional[int]) -> int:
        latest_history = (
            self.db.query(func.max(ProductDocHistory.version))
            .filter(ProductDocHistory.product_doc_id == product_doc_id)
            .scalar()
        )
        latest_value = max(int(latest_history or 0), int(current_version or 0))
        return latest_value + 1


__all__ = ["ProductDocService"]
