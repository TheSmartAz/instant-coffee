from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Event, Lock
from typing import Any, AsyncGenerator, Generator, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session as DbSession

from ..db.database import get_database
from ..db.models import Session as SessionModel, SessionEvent
from ..db.utils import get_db
from ..events.emitter import EventEmitter
from ..renderer.builder import BuildError, ReactSSGBuilder
from ..schemas.session_metadata import BuildInfo, BuildStatus, SessionMetadata
from ..config import get_settings
from ..services.event_store import EventStoreService
from ..services.page import PageService
from ..services.build_runner import build_artifact_base_dir, build_artifact_log_path
from ..services.state_store import StateStoreService
from .auth import require_admin_token

router = APIRouter(prefix="/api/sessions", tags=["build"])
logger = logging.getLogger(__name__)

BUILD_EVENT_TYPES = {
    "build_start",
    "build_progress",
    "build_complete",
    "build_failed",
}


@dataclass
class _BuildJob:
    task: asyncio.Task | None
    cancel_event: Event


_active_builds: dict[str, _BuildJob] = {}
_active_builds_lock = Lock()


def _register_build(session_id: str, job: _BuildJob) -> None:
    with _active_builds_lock:
        _active_builds[session_id] = job


def _clear_build(session_id: str, task: asyncio.Task | None = None) -> None:
    with _active_builds_lock:
        existing = _active_builds.get(session_id)
        if existing is None:
            return
        if task is not None and existing.task is not task:
            return
        _active_builds.pop(session_id, None)


def _get_build_job(session_id: str) -> _BuildJob | None:
    with _active_builds_lock:
        return _active_builds.get(session_id)


def _build_log_path(session_id: str) -> Path:
    return build_artifact_log_path(session_id).resolve()


def _get_db_session() -> Generator[DbSession, None, None]:
    with get_db() as session:
        yield session


def _build_info_from_metadata(metadata: SessionMetadata) -> BuildInfo:
    artifacts = metadata.build_artifacts or {}
    if not isinstance(artifacts, dict):
        artifacts = {}
    return BuildInfo(
        status=metadata.build_status,
        pages=artifacts.get("pages") or [],
        dist_path=artifacts.get("dist_path"),
        error=artifacts.get("error"),
        source_mode=artifacts.get("source_mode"),
        started_at=artifacts.get("started_at"),
        completed_at=artifacts.get("completed_at"),
    )


def _format_build_error(exc: Exception) -> str:
    if isinstance(exc, BuildError):
        return exc.summary()
    return str(exc)


def _resolve_workspace_source(session_id: str) -> Path | None:
    workspace = (Path(get_settings().output_dir).expanduser() / session_id).resolve()
    src_dir = workspace / "src"
    if not src_dir.is_dir():
        return None
    if (src_dir / "App.tsx").is_file():
        return workspace
    return None


def _format_timestamp(value: Optional[datetime]) -> str:
    if value is None:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _serialize_build_event(event: SessionEvent) -> dict[str, Any]:
    payload = event.payload or {}
    if not isinstance(payload, dict):
        payload = {"value": payload}
    return {
        "type": event.type,
        "timestamp": _format_timestamp(event.created_at),
        "session_id": event.session_id,
        "seq": event.seq,
        "payload": payload,
        "source": getattr(event.source, "value", event.source),
    }


async def _run_build_task(
    *,
    session_id: str,
    payload: dict[str, Any],
    started_at: datetime,
    cancel_event: Event,
) -> None:
    database = get_database()
    with database.session() as db:
        store = StateStoreService(db)
        emitter = EventEmitter(session_id=session_id, event_store=EventStoreService(db))
        builder = ReactSSGBuilder(
            session_id,
            base_dir=build_artifact_base_dir(),
            event_emitter=emitter,
            cancel_event=cancel_event,
        )
        try:
            workspace_source = _resolve_workspace_source(session_id)
            if workspace_source is None:
                raise BuildError(
                    "React app source not found. Generate `src/App.tsx` before building; "
                    "static HTML and HTML-to-React builds are no longer supported.",
                    stage="workspace_source",
                )
            page_hints = [
                {"slug": page.slug, "title": page.title}
                for page in PageService(db).list_by_session(session_id)
            ] or [{"slug": "index", "title": "Index"}]
            result = await builder.build_from_workspace_source(
                workspace_source,
                pages=page_hints,
            )
            completed_at = datetime.now(timezone.utc)
            info = BuildInfo(
                status=BuildStatus.SUCCESS,
                pages=(result or {}).get("pages") or [],
                dist_path=(result or {}).get("dist_path"),
                source_mode=(result or {}).get("source_mode"),
                started_at=started_at,
                completed_at=completed_at,
            )
        except Exception as exc:
            completed_at = datetime.now(timezone.utc)
            info = BuildInfo(
                status=BuildStatus.FAILED,
                error=_format_build_error(exc),
                pages=[],
                started_at=started_at,
                completed_at=completed_at,
            )
        store.update_build_info(session_id, info)
        db.commit()


@router.get("/{session_id}/build/status", response_model=BuildInfo)
async def get_build_status(
    session_id: str,
    db: DbSession = Depends(_get_db_session),
) -> BuildInfo:
    if db.get(SessionModel, session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")
    metadata = StateStoreService(db).get_metadata(session_id)
    if metadata is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return _build_info_from_metadata(metadata)


@router.get("/{session_id}/build/logs")
async def get_build_logs(
    session_id: str,
    db: DbSession = Depends(_get_db_session),
) -> dict:
    if db.get(SessionModel, session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")
    log_path = _build_log_path(session_id)
    if not log_path.exists():
        return {"logs": "", "available": False}
    try:
        content = log_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"logs": content, "available": True}


@router.post("/{session_id}/build", response_model=BuildInfo)
async def trigger_build(
    session_id: str,
    db: DbSession = Depends(_get_db_session),
    _: None = Depends(require_admin_token),
) -> BuildInfo:
    if db.get(SessionModel, session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")

    store = StateStoreService(db)
    metadata = store.get_metadata(session_id)
    if metadata is None:
        raise HTTPException(status_code=404, detail="Session not found")

    current_info = _build_info_from_metadata(metadata)
    if current_info.status == BuildStatus.BUILDING:
        return current_info

    if _resolve_workspace_source(session_id) is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "React app source not found. Generate `src/App.tsx` before building; "
                "static HTML and HTML-to-React builds are no longer supported."
            ),
        )

    payload = {}

    started_at = datetime.now(timezone.utc)
    building_info = BuildInfo(status=BuildStatus.BUILDING, pages=[], started_at=started_at)
    store.update_build_info(session_id, building_info)
    db.commit()

    loop = asyncio.get_running_loop()
    cancel_event = Event()
    task = loop.create_task(
        _run_build_task(
            session_id=session_id,
            payload=payload,
            started_at=started_at,
            cancel_event=cancel_event,
        )
    )
    _register_build(session_id, _BuildJob(task=task, cancel_event=cancel_event))
    task.add_done_callback(lambda finished: _clear_build(session_id, finished))

    return building_info


@router.delete("/{session_id}/build", response_model=BuildInfo)
async def cancel_build(
    session_id: str,
    db: DbSession = Depends(_get_db_session),
    _: None = Depends(require_admin_token),
) -> BuildInfo:
    if db.get(SessionModel, session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")

    job = _get_build_job(session_id)
    if job is not None:
        job.cancel_event.set()
        if job.task is not None and not job.task.done():
            job.task.cancel()

    store = StateStoreService(db)
    metadata = store.get_metadata(session_id)
    if metadata is None:
        raise HTTPException(status_code=404, detail="Session not found")
    current_info = _build_info_from_metadata(metadata)
    if current_info.status != BuildStatus.BUILDING:
        return current_info
    now = datetime.now(timezone.utc)
    cancelled_info = BuildInfo(
        status=BuildStatus.FAILED,
        error="Build cancelled",
        pages=[],
        started_at=current_info.started_at,
        completed_at=now,
    )
    store.update_build_info(session_id, cancelled_info)
    db.commit()
    return cancelled_info


@router.get("/{session_id}/build/stream")
async def stream_build_events(
    request: Request,
    session_id: str,
    since_seq: Optional[int] = Query(None, ge=0),
) -> StreamingResponse:
    database = get_database()
    with database.session() as db:
        if db.get(SessionModel, session_id) is None:
            raise HTTPException(status_code=404, detail="Session not found")

    async def event_stream() -> AsyncGenerator[str, None]:
        last_seq = since_seq
        done = False
        last_keepalive = asyncio.get_running_loop().time()
        while True:
            if await request.is_disconnected():
                return
            with database.session() as db:
                query = (
                    db.query(SessionEvent)
                    .filter(SessionEvent.session_id == session_id)
                    .filter(SessionEvent.type.in_(BUILD_EVENT_TYPES))
                )
                if last_seq is not None:
                    query = query.filter(SessionEvent.seq > last_seq)
                events = query.order_by(SessionEvent.seq.asc()).limit(200).all()

            if events:
                last_seq = events[-1].seq
                for event in events:
                    payload = _serialize_build_event(event)
                    yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                    if event.type in {"build_complete", "build_failed"}:
                        done = True
            else:
                if done:
                    break
                now = asyncio.get_running_loop().time()
                if now - last_keepalive >= 15:
                    yield ": keepalive\n\n"
                    last_keepalive = now
            await asyncio.sleep(0.5)
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


__all__ = ["router"]
