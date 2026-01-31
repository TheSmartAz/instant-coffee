from __future__ import annotations

from typing import Generator, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session as DbSession

from ..db.models import Message, Session as SessionModel, Version
from ..db.utils import get_db
from ..services.message import MessageService
from ..services.session import SessionService
from ..services.version import VersionService
from .utils import build_preview_url

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


class CreateSessionRequest(BaseModel):
    title: Optional[str] = None


class RollbackRequest(BaseModel):
    version: int


def _get_db_session() -> Generator[DbSession, None, None]:
    with get_db() as session:
        yield session


def _session_payload(db: DbSession, record: SessionModel) -> dict:
    message_count = (
        db.query(func.count(Message.id))
        .filter(Message.session_id == record.id)
        .scalar()
        or 0
    )
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
        "message_count": message_count,
        "version_count": version_count,
    }


@router.get("")
def list_sessions(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: DbSession = Depends(_get_db_session),
) -> dict:
    service = SessionService(db)
    sessions = service.list_sessions(limit=limit, offset=offset)
    total = db.query(func.count(SessionModel.id)).scalar() or 0
    return {
        "sessions": [_session_payload(db, record) for record in sessions],
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
    version = None
    if record.current_version is not None:
        version = (
            db.query(Version)
            .filter(Version.session_id == session_id)
            .filter(Version.version == record.current_version)
            .first()
        )
    if version is not None:
        payload["preview_html"] = version.html
    else:
        payload["preview_html"] = None
    payload["preview_url"] = build_preview_url(request, session_id)
    return payload


@router.get("/{session_id}/messages")
def get_messages(
    session_id: str,
    db: DbSession = Depends(_get_db_session),
) -> dict:
    service = MessageService(db)
    messages = service.get_messages(session_id)
    return {
        "messages": [
            {
                "id": message.id,
                "role": message.role,
                "content": message.content,
                "timestamp": message.timestamp,
            }
            for message in messages
        ]
    }


@router.get("/{session_id}/versions")
def get_versions(
    session_id: str,
    db: DbSession = Depends(_get_db_session),
) -> dict:
    service = VersionService(db)
    versions = service.get_versions(session_id)
    session = db.get(SessionModel, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "versions": [
            {
                "id": version.id,
                "version": version.version,
                "description": version.description,
                "created_at": version.created_at,
                "preview_html": version.html,
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
    version_service = VersionService(db)
    version = None
    if session.current_version is not None:
        version = version_service.get_version(session_id, session.current_version)
    if version is None:
        versions = version_service.get_versions(session_id, limit=1)
        version = versions[0] if versions else None
    if version is None:
        raise HTTPException(status_code=404, detail="No preview available")
    return HTMLResponse(content=version.html or "")


@router.post("/{session_id}/rollback")
def rollback_session(
    session_id: str,
    payload: RollbackRequest,
    request: Request,
    db: DbSession = Depends(_get_db_session),
) -> dict:
    service = VersionService(db)
    version = service.rollback(session_id, payload.version)
    if version is None:
        raise HTTPException(status_code=404, detail="Version not found")
    db.commit()
    return {
        "success": True,
        "current_version": payload.version,
        "preview_url": build_preview_url(request, session_id),
        "preview_html": version.html,
    }


@router.post("/{session_id}/versions/{version_id}/revert")
def revert_session_version(
    session_id: str,
    version_id: int,
    request: Request,
    db: DbSession = Depends(_get_db_session),
) -> dict:
    service = VersionService(db)
    version = service.rollback(session_id, int(version_id))
    if version is None:
        raise HTTPException(status_code=404, detail="Version not found")
    db.commit()
    return {
        "success": True,
        "current_version": int(version_id),
        "preview_url": build_preview_url(request, session_id),
        "preview_html": version.html,
    }


__all__ = ["router"]
