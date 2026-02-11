"""Page diff API endpoints."""

from __future__ import annotations

from typing import Generator, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session as DbSession

from ..db.models import Page, PageVersion
from ..db.utils import get_db
from ..services.diff import DiffService


def _get_db_session() -> Generator[DbSession, None, None]:
    with get_db() as session:
        yield session


router = APIRouter(prefix="/api/sessions", tags=["page-diff"])


@router.get("/{session_id}/pages/{page_id}/diff")
def get_page_diff(
    session_id: str,
    page_id: str,
    version_a: Optional[int] = Query(None, description="Source version (older)"),
    version_b: Optional[int] = Query(None, description="Target version (newer)"),
    db: DbSession = Depends(_get_db_session),
):
    """Get diff between two versions of a page."""
    # Verify page belongs to session
    page = db.query(Page).filter(
        Page.session_id == session_id,
        Page.id == page_id,
    ).first()

    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    service = DiffService(db)
    result = service.get_page_version_diff(
        session_id=session_id,
        page_id=page_id,
        version_a=version_a,
        version_b=version_b,
    )

    if not result:
        raise HTTPException(status_code=404, detail="Page versions not found")

    return result


@router.get("/{session_id}/pages/{page_id}/versions")
def list_page_versions(
    session_id: str,
    page_id: str,
    db: DbSession = Depends(_get_db_session),
):
    """List all versions of a page with metadata for diff selection."""
    page = db.query(Page).filter(
        Page.session_id == session_id,
        Page.id == page_id,
    ).first()

    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    versions = db.query(PageVersion).filter(
        PageVersion.page_id == page_id,
    ).order_by(PageVersion.version.desc()).all()

    return {
        "page_id": page_id,
        "page_slug": page.slug,
        "page_title": page.title,
        "versions": [
            {
                "id": v.id,
                "version": v.version,
                "description": v.description,
                "created_at": v.created_at.isoformat(),
            }
            for v in versions
        ],
    }


__all__ = ["router"]
