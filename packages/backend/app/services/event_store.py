from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from enum import Enum
from contextlib import contextmanager
from threading import Lock
import time
from typing import Any, Iterator, Literal, Optional

from sqlalchemy import func, inspect
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.exc import OperationalError

from ..db.models import (
    Plan,
    PlanEvent,
    SessionEvent,
    SessionEventSequence,
    SessionEventSource,
    Task,
    TaskEvent,
)
from ..events.models import BaseEvent, PlanCreatedEvent, PlanUpdatedEvent
from ..events.types import EXCLUDED_EVENT_TYPES, STRUCTURED_EVENT_TYPES
from ..config import get_settings
from ..db.database import get_database
from .plan import PlanService

logger = logging.getLogger(__name__)


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, Enum):
        return value.value
    return str(value)


def _safe_json_dumps(value: Any) -> Optional[str]:
    if value is None:
        return None
    try:
        return json.dumps(value, ensure_ascii=False, default=_json_default)
    except TypeError:
        return json.dumps(str(value), ensure_ascii=False)


def _normalize_payload(payload: Any) -> Any:
    if payload is None:
        return {}
    try:
        json.dumps(payload, ensure_ascii=False, default=_json_default)
        return payload
    except TypeError:
        return json.loads(json.dumps(payload, ensure_ascii=False, default=_json_default))


class EventStoreService:
    """Persist structured SSE events into session_events (and legacy plan/task tables)."""

    _session_locks: dict[str, Lock] = {}
    _session_locks_guard = Lock()
    _seq_cache: dict[str, int] = {}
    _sequence_table_checked = False
    _has_sequence_table = False
    _sqlite_retry_delays = (0.05, 0.1, 0.2, 0.4)

    def __init__(self, db: DbSession) -> None:
        self.db = db
        self._seq_cache = self.__class__._seq_cache
        settings = get_settings()
        database_url = str(settings.database_url or "")
        is_sqlite = database_url.startswith("sqlite")
        is_memory = ":memory:" in database_url or "mode=memory" in database_url
        # Use a dedicated writer session unless we're on in-memory SQLite (separate
        # connections would create isolated databases).
        self._use_separate_session = not (is_sqlite and is_memory)
        self._database = get_database() if self._use_separate_session else None

    @classmethod
    def _get_session_lock(cls, session_id: str) -> Lock:
        with cls._session_locks_guard:
            lock = cls._session_locks.get(session_id)
            if lock is None:
                lock = Lock()
                cls._session_locks[session_id] = lock
        return lock

    def should_store_event(self, event_type: str) -> bool:
        if not event_type:
            return False
        if event_type in EXCLUDED_EVENT_TYPES:
            return False
        return event_type in STRUCTURED_EVENT_TYPES

    def _infer_source(self, event_type: str, payload: dict) -> SessionEventSource:
        if event_type in {"plan_created", "plan_updated"}:
            return SessionEventSource.PLAN
        if event_type.startswith("task_") or payload.get("task_id"):
            return SessionEventSource.TASK
        return SessionEventSource.SESSION

    @classmethod
    def _check_sequence_table(cls, db: DbSession) -> None:
        if cls._sequence_table_checked:
            return
        try:
            inspector = inspect(db.get_bind())
            cls._has_sequence_table = (
                "session_event_sequences" in inspector.get_table_names()
            )
        except Exception:
            cls._has_sequence_table = False
        cls._sequence_table_checked = True

    def _next_seq_from_table(self, session_id: str, db: DbSession) -> int:
        seq_row = db.get(SessionEventSequence, session_id)
        if seq_row is None:
            max_seq = (
                db.query(func.max(SessionEvent.seq))
                .filter(SessionEvent.session_id == session_id)
                .scalar()
            )
            next_seq = int(max_seq or 0) + 1
            seq_row = SessionEventSequence(
                session_id=session_id,
                next_seq=next_seq + 1,
            )
            db.add(seq_row)
            db.flush([seq_row])
            return next_seq
        next_seq = int(seq_row.next_seq or 1)
        seq_row.next_seq = next_seq + 1
        db.add(seq_row)
        db.flush([seq_row])
        return next_seq

    def get_next_seq(self, session_id: str, db: Optional[DbSession] = None) -> int:
        resolved_db = db or self.db
        self._check_sequence_table(resolved_db)
        if self.__class__._has_sequence_table:
            return self._next_seq_from_table(session_id, resolved_db)
        max_seq = self._seq_cache.get(session_id)
        if max_seq is None:
            max_seq = (
                resolved_db.query(func.max(SessionEvent.seq))
                .filter(SessionEvent.session_id == session_id)
                .scalar()
            )
        pending = [
            item.seq
            for item in resolved_db.new
            if isinstance(item, SessionEvent)
            and item.session_id == session_id
            and item.seq is not None
        ]
        if pending:
            max_seq = max(max_seq or 0, max(pending))
        next_seq = int(max_seq or 0) + 1
        self._seq_cache[session_id] = next_seq
        return next_seq

    def _is_sqlite_locked(self, exc: Exception) -> bool:
        if not isinstance(exc, OperationalError):
            return False
        message = str(exc).lower()
        return "database is locked" in message or "database is busy" in message

    @contextmanager
    def _writer_session(self) -> Iterator[DbSession]:
        if not self._use_separate_session or self._database is None:
            yield self.db
            return
        session = self._database.session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def store_event(
        self,
        session_id: str,
        type: str,
        payload: dict,
        source: Literal["session", "plan", "task"],
        created_at: Optional[datetime] = None,
        *,
        db: Optional[DbSession] = None,
    ) -> Optional[int]:
        event_type = getattr(type, "value", type)
        if not session_id or not self.should_store_event(event_type):
            return None

        source_value = getattr(source, "value", source)
        try:
            source_enum = SessionEventSource(source_value)
        except ValueError:
            source_enum = SessionEventSource.SESSION

        safe_payload = _normalize_payload(payload)
        if created_at is None:
            created_at = datetime.now(timezone.utc)

        resolved_db = db or self.db
        with self._get_session_lock(session_id):
            seq = self.get_next_seq(session_id, db=resolved_db)
            session_event = SessionEvent(
                session_id=session_id,
                seq=seq,
                type=event_type,
                payload=safe_payload,
                source=source_enum,
                created_at=created_at,
            )
            resolved_db.add(session_event)
            resolved_db.flush([session_event])
            return seq

    def get_events(
        self, session_id: str, since_seq: Optional[int] = None, limit: int = 1000
    ) -> list[SessionEvent]:
        query = self.db.query(SessionEvent).filter(SessionEvent.session_id == session_id)
        if since_seq is not None:
            query = query.filter(SessionEvent.seq > since_seq)
        return query.order_by(SessionEvent.seq.asc()).limit(limit).all()

    async def store_and_emit(
        self,
        session_id: str,
        type: str,
        payload: dict,
        source: Literal["session", "plan", "task"],
        emitter,
    ) -> Optional[int]:
        seq = self.store_event(session_id, type, payload, source)
        if emitter is not None and hasattr(emitter, "emit"):
            try:
                payload_with_type = dict(payload or {})
                payload_with_type.setdefault("type", type)
                event = BaseEvent.model_construct(**payload_with_type)
                if getattr(emitter, "_event_store", None) is self:
                    original_store = emitter._event_store
                    emitter._event_store = None
                    try:
                        emitter.emit(event)
                    finally:
                        emitter._event_store = original_store
                else:
                    emitter.emit(event)
            except Exception:
                logger.debug("Failed to emit stored event", exc_info=True)
        return seq

    def record_event(self, event: BaseEvent) -> None:
        event_type = getattr(event.type, "value", event.type)
        payload = event.model_dump(mode="json")
        payload.pop("type", None)
        payload.pop("timestamp", None)
        payload.pop("session_id", None)
        session_id = event.session_id
        delays = (0.0,) + self._sqlite_retry_delays
        for attempt, delay in enumerate(delays, start=1):
            try:
                if delay:
                    time.sleep(delay)
                with self._writer_session() as db:
                    if session_id:
                        source = self._infer_source(str(event_type), payload)
                        self.store_event(
                            session_id,
                            str(event_type),
                            payload,
                            source.value,
                            created_at=event.timestamp,
                            db=db,
                        )
                    self._record_plan_task_event(event, str(event_type), payload, db=db)
                return
            except OperationalError as exc:
                if self._is_sqlite_locked(exc):
                    if attempt < len(delays):
                        logger.warning("Event store busy, retrying (attempt %s)", attempt)
                        continue
                    logger.warning("Event store busy, dropping event after retries")
                    return
                raise

    def _record_plan_task_event(
        self, event: BaseEvent, event_type: str, payload: dict, *, db: Optional[DbSession] = None
    ) -> None:
        """Maintain legacy plan/task event tables for compatibility."""
        resolved_db = db or self.db
        timestamp = event.timestamp or datetime.now(timezone.utc)
        if isinstance(event, PlanCreatedEvent):
            plan_payload = payload.get("plan") or {}
            plan = PlanService(resolved_db).upsert_plan_from_payload(
                plan_payload, session_id=event.session_id
            )
            if plan is None:
                return
            plan_event = PlanEvent(
                plan_id=plan.id,
                event_type=event_type,
                message=payload.get("message"),
                payload=_safe_json_dumps(payload),
                timestamp=timestamp,
            )
            resolved_db.add(plan_event)
            return

        if isinstance(event, PlanUpdatedEvent):
            plan_id = payload.get("plan_id")
            if not plan_id:
                return
            if resolved_db.get(Plan, plan_id) is None:
                return
            plan_event = PlanEvent(
                plan_id=plan_id,
                event_type=event_type,
                message=payload.get("message"),
                payload=_safe_json_dumps(payload),
                timestamp=timestamp,
            )
            resolved_db.add(plan_event)
            return

        task_id = payload.get("task_id")
        if not task_id:
            return
        task = resolved_db.get(Task, task_id)
        if task is None:
            logger.debug("Skipping event for unknown task_id=%s", task_id)
            return
        task_event = TaskEvent(
            task_id=task_id,
            event_type=event_type,
            agent_id=payload.get("agent_id"),
            agent_type=payload.get("agent_type"),
            agent_instance=payload.get("agent_instance"),
            message=payload.get("message") or payload.get("summary"),
            progress=payload.get("progress"),
            tool_name=payload.get("tool_name"),
            tool_input=_safe_json_dumps(payload.get("tool_input")),
            tool_output=_safe_json_dumps(payload.get("tool_output")),
            payload=_safe_json_dumps(payload),
            timestamp=timestamp,
        )
        resolved_db.add(task_event)


__all__ = ["EventStoreService"]
