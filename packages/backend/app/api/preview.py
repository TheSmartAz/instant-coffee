from __future__ import annotations

from pathlib import Path
from typing import Generator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session as DbSession

from ..db.models import Session as SessionModel
from ..db.utils import get_db
from ..services.build_runner import build_artifact_dist_dir
from ..services.state_store import StateStoreService

router = APIRouter(tags=["preview"])


def _get_db_session() -> Generator[DbSession, None, None]:
    with get_db() as session:
        yield session


def _resolve_dist_dir(session_id: str, db: DbSession | None = None) -> Path:
    if db is not None and db.get(SessionModel, session_id) is not None:
        metadata = StateStoreService(db).get_metadata(session_id)
        artifacts = metadata.build_artifacts if metadata is not None else None
        if isinstance(artifacts, dict):
            dist_path = artifacts.get("dist_path")
            if isinstance(dist_path, str) and dist_path.strip():
                return Path(dist_path).expanduser().resolve()
    return build_artifact_dist_dir(session_id).resolve()


def _safe_resolve(dist_dir: Path, path: str) -> Path:
    candidate = (dist_dir / path).resolve()
    if candidate != dist_dir and dist_dir not in candidate.parents:
        raise HTTPException(status_code=400, detail="Invalid path")
    return candidate


@router.get("/preview/{session_id}")
async def preview_index(session_id: str):
    return RedirectResponse(f"/preview/{session_id}/index.html")


@router.get("/preview/{session_id}/{path:path}")
async def serve_preview(
    session_id: str,
    path: str,
    db: DbSession = Depends(_get_db_session),
):
    dist_dir = _resolve_dist_dir(session_id, db)
    if not dist_dir.exists():
        raise HTTPException(status_code=404, detail="Build output not found")

    file_path = _safe_resolve(dist_dir, path)

    if file_path.is_dir() or not file_path.exists():
        file_path = _safe_resolve(file_path, "index.html")

    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)

    raise HTTPException(status_code=404, detail="File not found")


@router.get("/share/{session_id}")
async def share_preview(session_id: str):
    return RedirectResponse(f"/preview/{session_id}/index.html")


__all__ = ["router"]
