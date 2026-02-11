from __future__ import annotations

import asyncio
import logging
from typing import Generator, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session as DbSession

from ..db.models import Message, PageVersion, Session as SessionModel, Thread as ThreadModel, Version
from ..db.utils import get_db
from ..services.message import MessageService
from ..services.page import PageService
from ..services.page_version import PageVersionService
from ..services.product_doc import ProductDocService
from ..services.app_data_store import get_app_data_store
from ..services.session import SessionService
from ..services.state_store import StateStoreService
from ..services.thread import ThreadService
from ..services.token_tracker import TokenTrackerService
from ..schemas.session_metadata import SessionMetadata, SessionMetadataUpdate
from ..services.version import VersionService
from ..utils.html import EMPTY_PREVIEW_HTML, inject_hide_scrollbar_style, strip_prompt_artifacts
from ..utils.style import build_global_style_css
from .utils import build_preview_url

router = APIRouter(prefix="/api/sessions", tags=["sessions"])
logger = logging.getLogger(__name__)


class CreateSessionRequest(BaseModel):
    title: Optional[str] = None


class RollbackRequest(BaseModel):
    version: int


def _get_db_session() -> Generator[DbSession, None, None]:
    with get_db() as session:
        yield session


def _get_index_page(session: DbSession, session_id: str):
    return PageService(session).get_by_slug(session_id, "index")


def _build_preview_css(session: DbSession, session_id: str) -> str | None:
    product_doc = ProductDocService(session).get_by_session_id(session_id)
    if product_doc is None:
        return None
    structured = getattr(product_doc, "structured", None)
    if not isinstance(structured, dict):
        structured = {}
    global_style = structured.get("global_style") or structured.get("globalStyle") or {}
    if not isinstance(global_style, dict):
        global_style = {}
    design_direction = structured.get("design_direction") or structured.get("designDirection") or {}
    if not isinstance(design_direction, dict):
        design_direction = {}
    try:
        return build_global_style_css(global_style, design_direction)
    except Exception:
        return None


def _get_index_preview(session: DbSession, session_id: str) -> tuple[Optional[str], Optional[int]]:
    page = _get_index_page(session, session_id)
    if page is None:
        return None, None
    css = _build_preview_css(session, session_id)
    preview = PageVersionService(session).build_preview(page.id, global_style_css=css)
    if preview is None:
        return None, None
    version, html = preview
    return html, version.version


def _get_page_version_by_number(
    session: DbSession, page_id: str, version_number: int
) -> Optional[PageVersion]:
    return (
        session.query(PageVersion)
        .filter(PageVersion.page_id == page_id)
        .filter(PageVersion.version == version_number)
        .first()
    )


def _session_payload(
    db: DbSession,
    record: SessionModel,
    *,
    message_count: int | None = None,
    version_count: int | None = None,
) -> dict:
    if message_count is None:
        message_count = (
            db.query(func.count(Message.id))
            .filter(Message.session_id == record.id)
            .scalar()
            or 0
        )
    if version_count is None:
        version_count = (
            db.query(func.count(Version.id))
            .filter(Version.session_id == record.id)
            .scalar()
            or 0
        )
    return {
        "id": record.id,
        "title": record.title,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
        "current_version": record.current_version,
        "product_type": record.product_type,
        "complexity": record.complexity,
        "skill_id": record.skill_id,
        "doc_tier": record.doc_tier,
        "style_reference_mode": record.style_reference_mode,
        "model_classifier": record.model_classifier,
        "model_writer": record.model_writer,
        "model_expander": record.model_expander,
        "model_validator": record.model_validator,
        "model_style_refiner": record.model_style_refiner,
        "build_status": record.build_status,
        "message_count": message_count,
        "version_count": version_count,
    }


@router.get("")
def list_sessions(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    search: str = Query(None),
    sort: str = Query("updated_at"),
    order: str = Query("desc"),
    db: DbSession = Depends(_get_db_session),
) -> dict:
    from sqlalchemy import case, literal_column
    from sqlalchemy.orm import aliased

    # Build base query with subquery counts to avoid N+1
    msg_count_sq = (
        db.query(
            Message.session_id,
            func.count(Message.id).label("msg_count"),
        )
        .group_by(Message.session_id)
        .subquery()
    )
    ver_count_sq = (
        db.query(
            Version.session_id,
            func.count(Version.id).label("ver_count"),
        )
        .group_by(Version.session_id)
        .subquery()
    )

    query = (
        db.query(
            SessionModel,
            func.coalesce(msg_count_sq.c.msg_count, 0).label("message_count"),
            func.coalesce(ver_count_sq.c.ver_count, 0).label("version_count"),
        )
        .outerjoin(msg_count_sq, SessionModel.id == msg_count_sq.c.session_id)
        .outerjoin(ver_count_sq, SessionModel.id == ver_count_sq.c.session_id)
    )

    # Search filter
    if search:
        query = query.filter(SessionModel.title.ilike(f"%{search}%"))

    # Sorting
    sort_col = getattr(SessionModel, sort, SessionModel.updated_at)
    query = query.order_by(sort_col.desc() if order == "desc" else sort_col.asc())

    total = query.count()
    rows = query.offset(offset).limit(limit).all()

    return {
        "sessions": [
            _session_payload(
                db,
                record,
                message_count=msg_c,
                version_count=ver_c,
            )
            for record, msg_c, ver_c in rows
        ],
        "total": total,
    }


@router.post("")
def create_session(
    payload: CreateSessionRequest,
    db: DbSession = Depends(_get_db_session),
) -> dict:
    service = SessionService(db)
    record = service.create_session(title=payload.title)
    db.commit()
    db.refresh(record)
    return _session_payload(db, record)


@router.get("/{session_id}")
def get_session(
    session_id: str,
    request: Request,
    db: DbSession = Depends(_get_db_session),
) -> dict:
    record = db.get(SessionModel, session_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Session not found")
    payload = _session_payload(db, record)
    preview_html, _page_version = _get_index_preview(db, session_id)
    if preview_html is None:
        version = None
        if record.current_version is not None:
            version = (
                db.query(Version)
                .filter(Version.session_id == session_id)
                .filter(Version.version == record.current_version)
                .first()
            )
        payload["preview_html"] = strip_prompt_artifacts(version.html) if version is not None else None
    else:
        payload["preview_html"] = preview_html
    payload["preview_url"] = build_preview_url(request, session_id)
    return payload


@router.get("/{session_id}/fallbacks")
def get_session_fallbacks(
    session_id: str,
    limit: int = Query(10, ge=1, le=50),
    db: DbSession = Depends(_get_db_session),
) -> dict:
    if db.get(SessionModel, session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")
    service = PageVersionService(db)
    return service.fallback_stats_by_session(session_id, limit=limit)


@router.get("/{session_id}/messages")
def get_messages(
    session_id: str,
    thread_id: Optional[str] = Query(None),
    db: DbSession = Depends(_get_db_session),
) -> dict:
    service = MessageService(db)
    messages = service.get_messages(session_id, thread_id=thread_id)
    return {
        "messages": [
            {
                "id": message.id,
                "role": message.role,
                "content": message.content,
                "timestamp": message.timestamp,
                "thread_id": message.thread_id,
            }
            for message in messages
        ]
    }


@router.delete("/{session_id}/messages")
def clear_messages(
    session_id: str,
    thread_id: Optional[str] = Query(None),
    db: DbSession = Depends(_get_db_session),
) -> dict:
    session = db.get(SessionModel, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    service = MessageService(db)
    deleted = service.clear_messages(session_id, thread_id=thread_id)
    db.commit()
    return {"deleted": deleted}


@router.delete("/{session_id}")
def delete_session(
    session_id: str,
    db: DbSession = Depends(_get_db_session),
) -> dict:
    service = SessionService(db)
    deleted = service.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")

    app_data_store = get_app_data_store()
    if app_data_store.enabled:
        try:
            asyncio.run(app_data_store.drop_schema(session_id))
            logger.info("App data schema cleanup complete for session %s", session_id)
        except Exception:
            logger.warning("App data schema cleanup failed for session %s", session_id, exc_info=True)

    db.commit()
    return {"deleted": True}


@router.get("/{session_id}/metadata", response_model=SessionMetadata)
def get_session_metadata(
    session_id: str,
    db: DbSession = Depends(_get_db_session),
) -> SessionMetadata:
    service = StateStoreService(db)
    metadata = service.get_metadata(session_id)
    if metadata is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return metadata


@router.patch("/{session_id}/metadata", response_model=SessionMetadata)
def update_session_metadata(
    session_id: str,
    payload: SessionMetadataUpdate,
    db: DbSession = Depends(_get_db_session),
) -> SessionMetadata:
    service = StateStoreService(db)
    metadata = service.update_metadata(session_id, payload)
    if metadata is None:
        raise HTTPException(status_code=404, detail="Session not found")
    db.commit()
    return metadata


@router.delete("/{session_id}/metadata")
def clear_session_metadata(
    session_id: str,
    db: DbSession = Depends(_get_db_session),
) -> dict:
    service = StateStoreService(db)
    cleared = service.clear_metadata(session_id)
    if not cleared:
        raise HTTPException(status_code=404, detail="Session not found")
    db.commit()
    return {"cleared": True}


@router.get("/{session_id}/versions")
def get_versions(
    session_id: str,
    include_preview_html: bool = Query(True),
    db: DbSession = Depends(_get_db_session),
) -> dict:
    session = db.get(SessionModel, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    index_page = _get_index_page(db, session_id)
    if index_page is not None:
        page_version_service = PageVersionService(db)
        versions = page_version_service.list_by_page(index_page.id)
        current = page_version_service.get_current(index_page.id)
        return {
            "versions": [
                {
                    "id": version.id,
                    "version": version.version,
                    "description": version.description,
                    "created_at": version.created_at,
                    **(
                        {"preview_html": strip_prompt_artifacts(version.html)}
                        if include_preview_html
                        else {}
                    ),
                }
                for version in versions
            ],
            "current_version": current.version if current is not None else None,
        }
    service = VersionService(db)
    versions = service.get_versions(session_id)
    return {
        "versions": [
            {
                "id": version.id,
                "version": version.version,
                "description": version.description,
                "created_at": version.created_at,
                **(
                    {"preview_html": strip_prompt_artifacts(version.html)}
                    if include_preview_html
                    else {}
                ),
            }
            for version in versions
        ],
        "current_version": session.current_version,
    }


@router.get("/{session_id}/preview", response_class=HTMLResponse)
def get_preview(
    session_id: str,
    db: DbSession = Depends(_get_db_session),
) -> HTMLResponse:
    session = db.get(SessionModel, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    preview_html, _page_version = _get_index_preview(db, session_id)
    if preview_html is not None:
        preview_html = inject_hide_scrollbar_style(preview_html or "")
        return HTMLResponse(content=preview_html or "")

    version_service = VersionService(db)
    version = None
    if session.current_version is not None:
        version = version_service.get_version(session_id, session.current_version)
    if version is None:
        versions = version_service.get_versions(session_id, limit=1)
        version = versions[0] if versions else None
    if version is None:
        return HTMLResponse(content=EMPTY_PREVIEW_HTML)
    preview_html = inject_hide_scrollbar_style(strip_prompt_artifacts(version.html or ""))
    return HTMLResponse(content=preview_html or "")


@router.post("/{session_id}/rollback")
def rollback_session(
    session_id: str,
    payload: RollbackRequest,
    request: Request,
    db: DbSession = Depends(_get_db_session),
) -> dict:
    index_page = _get_index_page(db, session_id)
    if index_page is not None:
        return JSONResponse(
            status_code=410,
            content={
                "error": "rollback_not_supported",
                "message": "Session rollback via PageVersion is no longer supported. Use ProjectSnapshot rollback instead.",
                "preview_url": build_preview_url(request, session_id),
            },
        )
    service = VersionService(db)
    version = service.rollback(session_id, payload.version)
    if version is None:
        raise HTTPException(status_code=404, detail="Version not found")
    db.commit()
    return {
        "success": True,
        "current_version": payload.version,
        "preview_url": build_preview_url(request, session_id),
            "preview_html": strip_prompt_artifacts(version.html),
    }


@router.post("/{session_id}/versions/{version_id}/revert")
def revert_session_version(
    session_id: str,
    version_id: int,
    request: Request,
    db: DbSession = Depends(_get_db_session),
) -> dict:
    index_page = _get_index_page(db, session_id)
    if index_page is not None:
        return JSONResponse(
            status_code=410,
            content={
                "error": "rollback_not_supported",
                "message": "Session rollback via PageVersion is no longer supported. Use ProjectSnapshot rollback instead.",
                "preview_url": build_preview_url(request, session_id),
            },
        )
    service = VersionService(db)
    version = service.rollback(session_id, int(version_id))
    if version is None:
        raise HTTPException(status_code=404, detail="Version not found")
    db.commit()
    return {
        "success": True,
        "current_version": int(version_id),
        "preview_url": build_preview_url(request, session_id),
        "preview_html": strip_prompt_artifacts(version.html),
    }


class CreateThreadRequest(BaseModel):
    title: Optional[str] = None


class UpdateThreadRequest(BaseModel):
    title: Optional[str] = None


@router.get("/{session_id}/threads")
def list_threads(
    session_id: str,
    db: DbSession = Depends(_get_db_session),
) -> dict:
    session = db.get(SessionModel, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    service = ThreadService(db)
    threads = service.list_threads(session_id)
    if not threads:
        default = service.ensure_default_thread(session_id)
        db.commit()
        threads = [default]
    return {
        "threads": [
            {
                "id": t.id,
                "session_id": t.session_id,
                "title": t.title,
                "created_at": t.created_at,
                "updated_at": t.updated_at,
                "message_count": service.get_message_count(t.id),
            }
            for t in threads
        ]
    }


@router.post("/{session_id}/threads")
def create_thread(
    session_id: str,
    payload: CreateThreadRequest,
    db: DbSession = Depends(_get_db_session),
) -> dict:
    session = db.get(SessionModel, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    service = ThreadService(db)
    thread = service.create_thread(session_id, title=payload.title)
    db.commit()
    return {
        "id": thread.id,
        "session_id": thread.session_id,
        "title": thread.title,
        "created_at": thread.created_at,
        "updated_at": thread.updated_at,
        "message_count": 0,
    }


@router.delete("/{session_id}/threads/{thread_id}")
def delete_thread(
    session_id: str,
    thread_id: str,
    db: DbSession = Depends(_get_db_session),
) -> dict:
    session = db.get(SessionModel, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    service = ThreadService(db)
    thread = service.get_thread(thread_id)
    if thread is None or thread.session_id != session_id:
        raise HTTPException(status_code=404, detail="Thread not found")
    # Don't allow deleting the last thread
    all_threads = service.list_threads(session_id)
    if len(all_threads) <= 1:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete the last thread",
        )
    service.delete_thread(thread_id)
    db.commit()
    return {"deleted": True}


@router.patch("/{session_id}/threads/{thread_id}")
def update_thread(
    session_id: str,
    thread_id: str,
    payload: UpdateThreadRequest,
    db: DbSession = Depends(_get_db_session),
) -> dict:
    session = db.get(SessionModel, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    service = ThreadService(db)
    thread = service.get_thread(thread_id)
    if thread is None or thread.session_id != session_id:
        raise HTTPException(status_code=404, detail="Thread not found")
    if payload.title is not None:
        service.update_title(thread_id, payload.title)
    db.commit()
    return {
        "id": thread.id,
        "session_id": thread.session_id,
        "title": thread.title,
        "created_at": thread.created_at,
        "updated_at": thread.updated_at,
        "message_count": service.get_message_count(thread.id),
    }


@router.get("/{session_id}/cost")
def get_session_cost(
    session_id: str,
    db: DbSession = Depends(_get_db_session),
) -> dict:
    """Get token usage and cost summary for a session."""
    if db.get(SessionModel, session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")

    service = TokenTrackerService(db)
    summary = service.summarize_session(session_id)

    return {
        "session_id": session_id,
        "input_tokens": summary["total"]["input_tokens"],
        "output_tokens": summary["total"]["output_tokens"],
        "total_tokens": summary["total"]["total_tokens"],
        "cost_usd": round(summary["total"]["cost_usd"], 4),
        "by_agent": summary["by_agent"],
    }


@router.get("/cost")
def get_all_sessions_cost(
    db: DbSession = Depends(_get_db_session),
    limit: int = Query(50, ge=1, le=100),
) -> dict:
    """Get cost summary for all sessions, sorted by most recent."""
    from ..db.models import Session as SessionModel

    sessions = (
        db.query(SessionModel)
        .order_by(SessionModel.updated_at.desc())
        .limit(limit)
        .all()
    )

    service = TokenTrackerService(db)
    results = []

    for session in sessions:
        summary = service.summarize_session(session.id)
        results.append({
            "session_id": session.id,
            "title": session.title,
            "updated_at": session.updated_at,
            "input_tokens": summary["total"]["input_tokens"],
            "output_tokens": summary["total"]["output_tokens"],
            "total_tokens": summary["total"]["total_tokens"],
            "cost_usd": round(summary["total"]["cost_usd"], 4),
        })

    return {"sessions": results}


# ── Undo / Branch endpoints ──────────────────────────────────

class RollbackRequest(BaseModel):
    turns: int = 1


class BranchRequest(BaseModel):
    name: str


@router.post("/{session_id}/undo")
def undo_turn(session_id: str):
    """Undo the last turn in the conversation."""
    from ..engine.registry import engine_registry

    orch = engine_registry.get(session_id)
    if not orch or not orch._engine:
        raise HTTPException(404, "No active engine for this session")

    ok = orch._engine.context.undo()
    return {"success": ok, "message": "Undid last turn." if ok else "Nothing to undo."}


@router.post("/{session_id}/rollback")
def rollback_turns(session_id: str, body: RollbackRequest):
    """Rollback the last N turns."""
    from ..engine.registry import engine_registry

    orch = engine_registry.get(session_id)
    if not orch or not orch._engine:
        raise HTTPException(404, "No active engine for this session")

    removed = orch._engine.context.rollback(body.turns)
    return {"removed": removed, "message": f"Rolled back {removed} turn(s)."}


@router.post("/{session_id}/branch")
def create_branch(session_id: str, body: BranchRequest):
    """Save current conversation state as a named branch."""
    from ..engine.registry import engine_registry

    orch = engine_registry.get(session_id)
    if not orch or not orch._engine:
        raise HTTPException(404, "No active engine for this session")

    orch._engine.context.fork(body.name)
    return {"success": True, "branch": body.name}


@router.post("/{session_id}/switch-branch")
def switch_branch(session_id: str, body: BranchRequest):
    """Switch to a named branch."""
    from ..engine.registry import engine_registry

    orch = engine_registry.get(session_id)
    if not orch or not orch._engine:
        raise HTTPException(404, "No active engine for this session")

    ok = orch._engine.context.switch_branch(body.name)
    if not ok:
        available = orch._engine.context.list_branches()
        raise HTTPException(404, f"Branch '{body.name}' not found. Available: {available}")
    return {"success": True, "branch": body.name}


@router.get("/{session_id}/branches")
def list_branches(session_id: str):
    """List all saved branches for a session."""
    from ..engine.registry import engine_registry

    orch = engine_registry.get(session_id)
    if not orch or not orch._engine:
        raise HTTPException(404, "No active engine for this session")

    branches = orch._engine.context.list_branches()
    return {"branches": branches}


__all__ = ["router"]
