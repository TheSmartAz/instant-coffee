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
from ..renderer.html_to_react import PageHtml
from ..schemas.session_metadata import BuildInfo, BuildStatus, SessionMetadata
from ..config import get_settings
from ..services.build_payload import generate_node
from ..services.event_store import EventStoreService
from ..services.component_registry import ComponentRegistryService
from ..services.page import PageService
from ..services.product_doc import ProductDocService
from ..services.state_store import StateStoreService

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
    base = Path("~/.instant-coffee/sessions").expanduser()
    return (base / session_id / "build.log").resolve()


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
        started_at=artifacts.get("started_at"),
        completed_at=artifacts.get("completed_at"),
    )


def _extract_build_payload(state: Any) -> dict[str, Any]:
    if not isinstance(state, dict):
        return {}
    return {
        "page_schemas": state.get("page_schemas") or [],
        "component_registry": state.get("component_registry") or {},
        "style_tokens": state.get("style_tokens") or {},
        "assets": state.get("assets"),
    }


_FALLBACK_COMPONENT_IDS = [
    "nav-primary",
    "nav-bottom",
    "hero-banner",
    "section-header",
    "list-grid",
    "list-simple",
    "footer-simple",
    "button-primary",
    "button-secondary",
]


def _ensure_component_registry(registry: Any) -> dict[str, Any]:
    if isinstance(registry, dict):
        components = registry.get("components")
        if isinstance(components, list) and components:
            return registry
    return {
        "components": [{"id": component_id} for component_id in _FALLBACK_COMPONENT_IDS],
    }


def _load_component_registry(session_id: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        service = ComponentRegistryService(settings.output_dir, session_id)
        registry = service.read_registry()
        if isinstance(registry, dict):
            return registry
    except Exception:
        logger.exception("Failed to read component registry for session %s", session_id)
    return {}


def _resolve_pages_payload(db: DbSession, session_id: str, structured: dict | None) -> list[dict[str, Any]]:
    if structured and isinstance(structured.get("pages"), list):
        pages = [
            page
            for page in structured.get("pages", [])
            if isinstance(page, dict)
        ]
        if pages:
            return pages
    try:
        pages = PageService(db).list_by_session(session_id)
    except Exception:
        logger.exception("Failed to resolve pages payload for session %s", session_id)
        pages = []
    return [
        {
            "slug": page.slug,
            "title": page.title,
            "role": "general",
        }
        for page in pages
    ]


async def _fallback_build_payload(
    *,
    db: DbSession,
    session_id: str,
    state: dict | None,
) -> dict[str, Any]:
    state = state if isinstance(state, dict) else {}
    product_doc = ProductDocService(db).get_by_session_id(session_id)
    structured = product_doc.structured if product_doc and isinstance(product_doc.structured, dict) else None

    component_registry = state.get("component_registry")
    if not isinstance(component_registry, dict) or not component_registry:
        component_registry = _load_component_registry(session_id)
    component_registry = _ensure_component_registry(component_registry)

    fallback_state: dict[str, Any] = {
        **state,
        "session_id": session_id,
        "component_registry": component_registry,
        "pages": _resolve_pages_payload(db, session_id, structured),
    }
    if structured:
        fallback_state["product_doc"] = {"structured": structured}

    try:
        updated_state = await generate_node(fallback_state)
    except Exception:
        logger.exception("Fallback build payload generation failed for session %s", session_id)
        updated_state = fallback_state

    payload = _extract_build_payload(updated_state)
    payload["component_registry"] = _ensure_component_registry(
        payload.get("component_registry") or component_registry
    )
    return payload


def _format_build_error(exc: Exception) -> str:
    if isinstance(exc, BuildError):
        return exc.summary()
    return str(exc)


def _fetch_pages_html(db: DbSession, session_id: str) -> list[PageHtml]:
    """Fetch current HTML for all pages in a session."""
    pages = PageService(db).list_by_session(session_id)
    result: list[PageHtml] = []
    for page in pages:
        html: str | None = None
        if page.current_version and hasattr(page.current_version, "html"):
            html = page.current_version.html
        if not html and page.versions:
            latest = sorted(page.versions, key=lambda v: v.version, reverse=True)
            for v in latest:
                if v.html:
                    html = v.html
                    break
        if html:
            result.append(PageHtml(slug=page.slug, title=page.title, html=html))
    return result


def _fetch_product_doc(db: DbSession, session_id: str) -> str | None:
    """Fetch product doc content for a session."""
    doc = ProductDocService(db).get_by_session_id(session_id)
    if doc and doc.content:
        return doc.content
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
        builder = ReactSSGBuilder(session_id, event_emitter=emitter, cancel_event=cancel_event)
        try:
            # Try HTML-to-React path first
            pages_html = _fetch_pages_html(db, session_id)
            if pages_html:
                product_doc = _fetch_product_doc(db, session_id)
                result = await builder.build_from_html(
                    pages=pages_html,
                    product_doc_content=product_doc,
                )
            else:
                # Fallback: schema-based build
                result = await builder.build(
                    page_schemas=payload.get("page_schemas") or [],
                    component_registry=payload.get("component_registry") or {},
                    style_tokens=payload.get("style_tokens") or {},
                    assets=payload.get("assets"),
                )
            completed_at = datetime.now(timezone.utc)
            info = BuildInfo(
                status=BuildStatus.SUCCESS,
                pages=(result or {}).get("pages") or [],
                dist_path=(result or {}).get("dist_path"),
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

    # Check if HTML pages are available (HTML-to-React path)
    has_html_pages = bool(_fetch_pages_html(db, session_id))

    payload = _extract_build_payload(metadata.graph_state)
    page_schemas = payload.get("page_schemas")
    if not has_html_pages and (not isinstance(page_schemas, list) or not page_schemas):
        payload = await _fallback_build_payload(
            db=db,
            session_id=session_id,
            state=metadata.graph_state if isinstance(metadata.graph_state, dict) else {},
        )
        page_schemas = payload.get("page_schemas")
        if isinstance(page_schemas, list) and page_schemas:
            merged_state = dict(metadata.graph_state or {})
            merged_state.update(
                {
                    "page_schemas": page_schemas,
                    "component_registry": payload.get("component_registry") or {},
                    "style_tokens": payload.get("style_tokens") or {},
                    "assets": payload.get("assets"),
                }
            )
            store.update_metadata(session_id, {"graph_state": merged_state})
        else:
            if not has_html_pages:
                raise HTTPException(status_code=400, detail="No page schemas or HTML pages available for build")

    started_at = datetime.now(timezone.utc)
    building_info = BuildInfo(status=BuildStatus.BUILDING, pages=[], started_at=started_at)
    store.update_build_info(session_id, building_info)
    db.commit()

    try:
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
    except RuntimeError:
        cancel_event = Event()
        _register_build(session_id, _BuildJob(task=None, cancel_event=cancel_event))
        asyncio.run(
            _run_build_task(
                session_id=session_id,
                payload=payload,
                started_at=started_at,
                cancel_event=cancel_event,
            )
        )
        _clear_build(session_id)

    return building_info


@router.delete("/{session_id}/build", response_model=BuildInfo)
async def cancel_build(
    session_id: str,
    db: DbSession = Depends(_get_db_session),
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
