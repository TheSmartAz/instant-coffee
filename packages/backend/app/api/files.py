from __future__ import annotations

from typing import Generator

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DbSession

from ..db.models import Session as SessionModel
from ..db.utils import get_db
from ..schemas.files import FileContentResponse, FileTreeResponse
from ..services.file_tree import FileTreeService

router = APIRouter(prefix="/api/sessions", tags=["files"])


def _get_db_session() -> Generator[DbSession, None, None]:
    with get_db() as session:
        yield session


@router.get("/{session_id}/files", response_model=FileTreeResponse)
def get_files_tree(
    session_id: str,
    db: DbSession = Depends(_get_db_session),
) -> FileTreeResponse:
    if db.get(SessionModel, session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")
    service = FileTreeService(db)
    tree = service.get_tree(session_id)
    return FileTreeResponse(tree=tree)


@router.get("/{session_id}/files/{path:path}", response_model=FileContentResponse)
def get_file_content(
    session_id: str,
    path: str,
    db: DbSession = Depends(_get_db_session),
) -> FileContentResponse:
    if db.get(SessionModel, session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")
    service = FileTreeService(db)
    payload = service.get_file_content(session_id, path)
    if payload is None:
        raise HTTPException(status_code=404, detail="File not found")
    return FileContentResponse(
        path=payload.path,
        content=payload.content,
        language=payload.language,
        size=payload.size,
    )


__all__ = ["router"]
