from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Generator, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from ..db.models import (
    Plan,
    PlanEvent,
    Session as SessionModel,
    SessionEvent,
    Task,
    TaskEvent,
)
from ..db.utils import get_db
from ..services.event_store import EventStoreService

router = APIRouter(prefix="/api", tags=["events"])


class SessionEventResponse(BaseModel):
    id: int
    session_id: str
    seq: int
    type: str
    payload: dict
    source: str
    created_at: str


class SessionEventsResponse(BaseModel):
    events: list[SessionEventResponse]
    last_seq: int
    has_more: bool


def _get_db_session() -> Generator[DbSession, None, None]:
    with get_db() as session:
        yield session


def _format_timestamp(value: Optional[datetime]) -> str:
    if value is None:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_json_payload(raw: Optional[str]) -> dict:
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            value = json.loads(raw)
            return value if isinstance(value, dict) else {"value": value}
        except json.JSONDecodeError:
            return {"value": raw}
    return {"value": raw}


def _serialize_event(event: SessionEvent) -> SessionEventResponse:
    payload = event.payload or {}
    if not isinstance(payload, dict):
        payload = {"value": payload}
    return SessionEventResponse(
        id=event.id,
        session_id=event.session_id,
        seq=event.seq,
        type=event.type,
        payload=payload,
        source=getattr(event.source, "value", event.source),
        created_at=_format_timestamp(event.created_at),
    )


def _event_key(event_type: str, created_at: Optional[datetime], payload: dict) -> str:
    timestamp = _format_timestamp(created_at)
    try:
        payload_str = json.dumps(payload, sort_keys=True, ensure_ascii=True, default=str)
    except TypeError:
        payload_str = json.dumps(str(payload), ensure_ascii=True)
    return f"{event_type}|{timestamp}|{payload_str}"


def _load_legacy_plan_events(
    db: DbSession,
    session_id: str,
    existing_keys: set[str],
) -> list[SessionEventResponse]:
    events: list[SessionEventResponse] = []
    plan_events = (
        db.query(PlanEvent, Plan)
        .join(Plan, PlanEvent.plan_id == Plan.id)
        .filter(Plan.session_id == session_id)
        .order_by(PlanEvent.timestamp.asc())
        .all()
    )
    for plan_event, plan in plan_events:
        payload = _parse_json_payload(plan_event.payload)
        if plan_event.message:
            payload.setdefault("message", plan_event.message)
        payload.setdefault("plan_id", plan_event.plan_id)
        key = _event_key(plan_event.event_type, plan_event.timestamp, payload)
        if key in existing_keys:
            continue
        existing_keys.add(key)
        events.append(
            SessionEventResponse(
                id=plan_event.id,
                session_id=plan.session_id,
                seq=0,
                type=plan_event.event_type,
                payload=payload,
                source="plan",
                created_at=_format_timestamp(plan_event.timestamp),
            )
        )
    return events


def _load_legacy_task_events(
    db: DbSession,
    session_id: str,
    existing_keys: set[str],
) -> list[SessionEventResponse]:
    events: list[SessionEventResponse] = []
    task_events = (
        db.query(TaskEvent, Task, Plan)
        .join(Task, TaskEvent.task_id == Task.id)
        .join(Plan, Task.plan_id == Plan.id)
        .filter(Plan.session_id == session_id)
        .order_by(TaskEvent.timestamp.asc())
        .all()
    )
    for task_event, task, plan in task_events:
        payload = _parse_json_payload(task_event.payload)
        payload.setdefault("task_id", task_event.task_id)
        if task_event.message:
            payload.setdefault("message", task_event.message)
        if task_event.progress is not None:
            payload.setdefault("progress", task_event.progress)
        if task_event.tool_name:
            payload.setdefault("tool_name", task_event.tool_name)
        if task_event.tool_input:
            payload.setdefault("tool_input", task_event.tool_input)
        if task_event.tool_output:
            payload.setdefault("tool_output", task_event.tool_output)
        if task_event.agent_id:
            payload.setdefault("agent_id", task_event.agent_id)
        if task_event.agent_type:
            payload.setdefault("agent_type", task_event.agent_type)
        if task_event.agent_instance is not None:
            payload.setdefault("agent_instance", task_event.agent_instance)
        key = _event_key(task_event.event_type, task_event.timestamp, payload)
        if key in existing_keys:
            continue
        existing_keys.add(key)
        events.append(
            SessionEventResponse(
                id=task_event.id,
                session_id=plan.session_id,
                seq=0,
                type=task_event.event_type,
                payload=payload,
                source="task",
                created_at=_format_timestamp(task_event.timestamp),
            )
        )
    return events


@router.get("/sessions/{session_id}/events", response_model=SessionEventsResponse)
def get_session_events(
    session_id: str,
    since_seq: Optional[int] = Query(None, ge=0),
    limit: int = Query(1000, ge=1, le=5000),
    db: DbSession = Depends(_get_db_session),
) -> SessionEventsResponse:
    session = db.get(SessionModel, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    service = EventStoreService(db)
    events = service.get_events(session_id, since_seq=since_seq, limit=limit + 1)
    has_more = len(events) > limit
    if has_more:
        events = events[:limit]

    serialized = [_serialize_event(event) for event in events]
    last_seq = serialized[-1].seq if serialized else (since_seq or 0)

    if not has_more and (since_seq is None or since_seq <= 0) and not serialized:
        existing_keys = set()
        for item in serialized:
            if not item.created_at:
                continue
            try:
                created_at = datetime.fromisoformat(item.created_at.replace("Z", "+00:00"))
            except ValueError:
                continue
            existing_keys.add(_event_key(item.type, created_at, item.payload))
        legacy = []
        legacy.extend(_load_legacy_plan_events(db, session_id, existing_keys))
        legacy.extend(_load_legacy_task_events(db, session_id, existing_keys))
        if legacy:
            seq_counter = last_seq
            for legacy_event in legacy:
                seq_counter += 1
                legacy_event.seq = seq_counter
            serialized.extend(legacy)
            if len(serialized) > limit:
                serialized = serialized[:limit]
                has_more = True
            last_seq = serialized[-1].seq if serialized else last_seq

    return SessionEventsResponse(events=serialized, last_seq=last_seq, has_more=has_more)


__all__ = ["router"]
