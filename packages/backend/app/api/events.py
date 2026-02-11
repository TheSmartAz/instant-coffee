from __future__ import annotations

from datetime import datetime, timezone
from typing import Generator, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from ..db.models import (
    Session as SessionModel,
    SessionEvent,
)
from ..db.utils import get_db
from ..services.event_store import EventStoreService

router = APIRouter(prefix="/api", tags=["events"])


class SessionEventResponse(BaseModel):
    id: int
    session_id: str
    seq: int
    run_id: str | None = None
    event_id: str | None = None
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


def _serialize_event(event: SessionEvent) -> SessionEventResponse:
    payload = event.payload or {}
    if not isinstance(payload, dict):
        payload = {"value": payload}
    return SessionEventResponse(
        id=event.id,
        session_id=event.session_id,
        seq=event.seq,
        run_id=event.run_id,
        event_id=event.event_id,
        type=event.type,
        payload=payload,
        source=getattr(event.source, "value", event.source),
        created_at=_format_timestamp(event.created_at),
    )


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

    return SessionEventsResponse(events=serialized, last_seq=last_seq, has_more=has_more)


__all__ = ["router"]
