from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import AsyncGenerator, Generator, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from ..config import get_settings
from ..db.database import get_database
from ..db.models import SessionEvent, SessionRun
from ..db.utils import get_db
from ..schemas.run import RunCreate, RunResponse, RunResumeRequest, RunStatus
from ..services.event_store import EventStoreService
from ..services.run import RunNotFoundError, RunService, RunStateConflictError

router = APIRouter(prefix="/api/runs", tags=["runs"])


class RunEventResponse(BaseModel):
    id: int
    session_id: str
    run_id: Optional[str]
    event_id: Optional[str]
    seq: int
    type: str
    payload: dict
    source: str
    created_at: str


class RunEventsResponse(BaseModel):
    events: list[RunEventResponse]
    last_seq: int
    has_more: bool


TERMINAL_RUN_STATES = {
    RunStatus.COMPLETED.value,
    RunStatus.FAILED.value,
    RunStatus.CANCELLED.value,
}


@dataclass
class _IdempotencyRecord:
    status_code: int
    body: dict
    expires_at: datetime


_IDEMPOTENCY_TTL = timedelta(hours=24)
_idempotency_guard = Lock()
_idempotency_cache: dict[tuple[str, str], _IdempotencyRecord] = {}


def _get_db_session() -> Generator[DbSession, None, None]:
    with get_db() as session:
        yield session


def _ensure_run_api_enabled() -> None:
    settings = get_settings()
    if not settings.run_api_enabled:
        raise HTTPException(status_code=404, detail="Not found")


def _format_timestamp(value: Optional[datetime]) -> str:
    if value is None:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _serialize_event(event: SessionEvent) -> RunEventResponse:
    payload = event.payload or {}
    if not isinstance(payload, dict):
        payload = {"value": payload}
    return RunEventResponse(
        id=event.id,
        session_id=event.session_id,
        run_id=event.run_id,
        event_id=event.event_id,
        seq=event.seq,
        type=event.type,
        payload=payload,
        source=getattr(event.source, "value", event.source),
        created_at=_format_timestamp(event.created_at),
    )


def _run_to_response(run: SessionRun) -> RunResponse:
    latest_error = run.latest_error if isinstance(run.latest_error, dict) else None
    waiting_reason: Optional[str] = None
    if isinstance(latest_error, dict):
        candidate = latest_error.get("waiting_reason") or latest_error.get("reason")
        if candidate is not None:
            waiting_reason = str(candidate)

    return RunResponse(
        run_id=run.id,
        session_id=run.session_id,
        status=RunStatus(run.status),
        started_at=run.started_at,
        finished_at=run.finished_at,
        latest_error=latest_error,
        metrics=run.metrics if isinstance(run.metrics, dict) else None,
        checkpoint_thread=run.checkpoint_thread,
        checkpoint_ns=run.checkpoint_ns,
        waiting_reason=waiting_reason,
    )


def _idempotency_scope(action: str, target_id: str) -> str:
    return f"{action}:{target_id}"


def _idempotency_get(scope: str, key: str) -> Optional[JSONResponse]:
    if not key:
        return None
    now = datetime.now(timezone.utc)
    cache_key = (scope, key)

    with _idempotency_guard:
        expired = [item for item, entry in _idempotency_cache.items() if entry.expires_at <= now]
        for item in expired:
            _idempotency_cache.pop(item, None)

        entry = _idempotency_cache.get(cache_key)
        if entry is None:
            return None
        return JSONResponse(status_code=entry.status_code, content=entry.body)


def _idempotency_set(scope: str, key: str, status_code: int, body: dict) -> None:
    if not key:
        return
    now = datetime.now(timezone.utc)
    with _idempotency_guard:
        _idempotency_cache[(scope, key)] = _IdempotencyRecord(
            status_code=status_code,
            body=body,
            expires_at=now + _IDEMPOTENCY_TTL,
        )


@router.post("", response_model=RunResponse, status_code=201)
def create_run(
    payload: RunCreate,
    db: DbSession = Depends(_get_db_session),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    _ensure_run_api_enabled()
    key = (idempotency_key or "").strip()
    scope = _idempotency_scope("create", payload.session_id)
    cached = _idempotency_get(scope, key)
    if cached is not None:
        return cached

    service = RunService(db)
    try:
        run = service.create_run(
            session_id=payload.session_id,
            message=payload.message,
            generate_now=payload.generate_now,
            style_reference=(
                payload.style_reference.model_dump(mode="json")
                if payload.style_reference is not None
                else None
            ),
            target_pages=payload.target_pages,
        )
    except ValueError as exc:
        detail = str(exc)
        if detail == "Session not found":
            raise HTTPException(status_code=404, detail=detail) from exc
        raise HTTPException(status_code=422, detail=detail) from exc

    db.commit()
    response = _run_to_response(run)
    body = response.model_dump(mode="json")
    _idempotency_set(scope, key, 201, body)
    return body


@router.get("/{run_id}", response_model=RunResponse)
def get_run(run_id: str, db: DbSession = Depends(_get_db_session)):
    _ensure_run_api_enabled()
    service = RunService(db)
    try:
        run = service.get_run(run_id)
    except RunNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc
    return _run_to_response(run)


@router.post("/{run_id}/resume", response_model=RunResponse)
def resume_run(
    run_id: str,
    payload: RunResumeRequest,
    db: DbSession = Depends(_get_db_session),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    _ensure_run_api_enabled()
    key = (idempotency_key or "").strip()
    scope = _idempotency_scope("resume", run_id)
    cached = _idempotency_get(scope, key)
    if cached is not None:
        return cached

    service = RunService(db)
    try:
        run = service.resume_run(run_id, payload.resume_payload)
    except RunNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc
    except RunStateConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    db.commit()
    response = _run_to_response(run)
    body = response.model_dump(mode="json")
    _idempotency_set(scope, key, 200, body)
    return body


@router.post("/{run_id}/cancel", response_model=RunResponse)
def cancel_run(
    run_id: str,
    response: Response,
    db: DbSession = Depends(_get_db_session),
):
    _ensure_run_api_enabled()
    service = RunService(db)
    try:
        run, accepted = service.cancel_run(run_id)
    except RunNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc

    db.commit()
    response.status_code = 202 if accepted else 200
    return _run_to_response(run)


@router.get("/{run_id}/events", response_model=RunEventsResponse)
async def get_run_events(
    run_id: str,
    request: Request,
    since_seq: Optional[int] = Query(None, ge=0),
    limit: int = Query(1000, ge=1, le=5000),
    db: DbSession = Depends(_get_db_session),
):
    _ensure_run_api_enabled()
    run_service = RunService(db)
    try:
        run = run_service.get_run(run_id)
    except RunNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc

    accept = (request.headers.get("accept") or "").lower()
    wants_sse = "text/event-stream" in accept
    if wants_sse:
        return StreamingResponse(
            _stream_run_events(
                request=request,
                run_id=run_id,
                session_id=run.session_id,
                since_seq=since_seq,
            ),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    event_store = EventStoreService(db)
    events = event_store.get_events_by_run(
        run.session_id,
        run_id,
        since_seq=since_seq,
        limit=limit + 1,
    )
    has_more = len(events) > limit
    if has_more:
        events = events[:limit]

    serialized = [_serialize_event(event) for event in events]
    last_seq = serialized[-1].seq if serialized else (since_seq or 0)
    return RunEventsResponse(events=serialized, last_seq=last_seq, has_more=has_more)


async def _stream_run_events(
    *,
    request: Request,
    run_id: str,
    session_id: str,
    since_seq: Optional[int],
) -> AsyncGenerator[str, None]:
    database = get_database()
    last_seq = since_seq
    done = False
    last_keepalive = asyncio.get_running_loop().time()

    while True:
        if await request.is_disconnected():
            return

        with database.session() as db:
            run = db.get(SessionRun, run_id)
            if run is None:
                return
            event_store = EventStoreService(db)
            events = event_store.get_events_by_run(
                session_id,
                run_id,
                since_seq=last_seq,
                limit=200,
            )
            if run.status in TERMINAL_RUN_STATES:
                done = True

        if events:
            last_seq = events[-1].seq
            for event in events:
                payload = _serialize_event(event).model_dump(mode="json")
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.05)
            continue

        if done:
            break

        now = asyncio.get_running_loop().time()
        if now - last_keepalive >= 15:
            yield ": keepalive\n\n"
            last_keepalive = now
        await asyncio.sleep(0.5)

    yield "data: [DONE]\n\n"


__all__ = ["router"]
