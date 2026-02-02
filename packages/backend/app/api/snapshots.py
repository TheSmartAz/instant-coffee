from __future__ import annotations

from typing import Generator, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DbSession

from ..db.models import Page, ProjectSnapshot, Session as SessionModel, VersionSource
from ..db.utils import get_db
from ..services.project_snapshot import (
    PinnedLimitExceeded,
    ProjectSnapshotService,
    SnapshotUnavailableError,
)

router = APIRouter(prefix="/api", tags=["snapshots"])


class SnapshotCreateRequest(BaseModel):
    label: Optional[str] = Field(default=None, max_length=255)


def _get_db_session() -> Generator[DbSession, None, None]:
    with get_db() as session:
        yield session


def _snapshot_source_value(snapshot: ProjectSnapshot) -> str:
    source = snapshot.source
    if isinstance(source, VersionSource):
        return source.value
    return str(source)


def _snapshot_payload(snapshot: ProjectSnapshot) -> dict:
    return {
        "id": snapshot.id,
        "session_id": snapshot.session_id,
        "snapshot_number": snapshot.snapshot_number,
        "label": snapshot.label,
        "source": _snapshot_source_value(snapshot),
        "is_pinned": bool(snapshot.is_pinned),
        "is_released": bool(snapshot.is_released),
        "created_at": snapshot.created_at,
        "available": not bool(snapshot.is_released),
        "page_count": len(snapshot.pages),
    }


def _restored_pages(db: DbSession, snapshot: ProjectSnapshot) -> list[str]:
    restored: list[str] = []
    for snap_page in snapshot.pages:
        page = db.get(Page, snap_page.page_id)
        if page is None:
            continue
        restored.append(page.id)
    return restored


@router.get("/sessions/{session_id}/snapshots")
def list_snapshots(
    session_id: str,
    include_released: bool = Query(False, alias="include_released"),
    db: DbSession = Depends(_get_db_session),
) -> dict:
    if db.get(SessionModel, session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")
    service = ProjectSnapshotService(db)
    snapshots = service.get_snapshots(session_id, include_released=include_released)
    return {
        "snapshots": [_snapshot_payload(snapshot) for snapshot in snapshots],
        "total": len(snapshots),
    }


@router.get("/sessions/{session_id}/snapshots/{snapshot_id}")
def get_snapshot(
    session_id: str,
    snapshot_id: str,
    db: DbSession = Depends(_get_db_session),
) -> dict:
    service = ProjectSnapshotService(db)
    snapshot = service.get_snapshot(snapshot_id)
    if snapshot is None or snapshot.session_id != session_id:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return _snapshot_payload(snapshot)


@router.post("/sessions/{session_id}/snapshots")
def create_snapshot(
    session_id: str,
    payload: SnapshotCreateRequest,
    db: DbSession = Depends(_get_db_session),
) -> dict:
    if db.get(SessionModel, session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")
    service = ProjectSnapshotService(db)
    try:
        snapshot = service.create_snapshot(
            session_id,
            source=VersionSource.MANUAL,
            label=payload.label,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return _snapshot_payload(snapshot)


@router.post("/sessions/{session_id}/snapshots/{snapshot_id}/rollback")
def rollback_snapshot(
    session_id: str,
    snapshot_id: str,
    db: DbSession = Depends(_get_db_session),
) -> dict:
    service = ProjectSnapshotService(db)
    try:
        new_snapshot = service.rollback_to_snapshot(session_id, snapshot_id)
    except SnapshotUnavailableError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    return {
        "message": "Rolled back successfully",
        "new_snapshot": _snapshot_payload(new_snapshot),
        "restored_pages": _restored_pages(db, new_snapshot),
    }


@router.post("/sessions/{session_id}/snapshots/{snapshot_id}/pin")
def pin_snapshot(
    session_id: str,
    snapshot_id: str,
    db: DbSession = Depends(_get_db_session),
) -> dict:
    service = ProjectSnapshotService(db)
    snapshot = service.get_snapshot(snapshot_id)
    if snapshot is None or snapshot.session_id != session_id:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    try:
        snapshot = service.pin_snapshot(snapshot_id)
    except PinnedLimitExceeded as exc:
        db.rollback()
        return JSONResponse(
            status_code=409,
            content={
                "error": "pinned_limit_exceeded",
                "message": str(exc),
                "current_pinned": exc.current_pinned,
            },
        )
    except SnapshotUnavailableError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    return {
        "message": "Pinned successfully",
        "snapshot": _snapshot_payload(snapshot),
        "current_pinned": service.list_pinned_snapshot_ids(snapshot.session_id),
    }


@router.post("/sessions/{session_id}/snapshots/{snapshot_id}/unpin")
def unpin_snapshot(
    session_id: str,
    snapshot_id: str,
    db: DbSession = Depends(_get_db_session),
) -> dict:
    service = ProjectSnapshotService(db)
    snapshot = service.get_snapshot(snapshot_id)
    if snapshot is None or snapshot.session_id != session_id:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    try:
        snapshot = service.unpin_snapshot(snapshot_id)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    return {
        "message": "Unpinned successfully",
        "snapshot": _snapshot_payload(snapshot),
        "current_pinned": service.list_pinned_snapshot_ids(snapshot.session_id),
    }


__all__ = ["router"]
