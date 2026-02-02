from __future__ import annotations

from typing import Generator

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session as DbSession

from ..db.models import Page as PageModel, Session as SessionModel
from ..db.utils import get_db
from ..schemas.page import (
    PagePreviewResponse,
    PageResponse,
    PageVersionResponse,
)
from ..services.page import PageService
from ..services.page_version import (
    PageVersionNotFoundError,
    PageVersionReleasedError,
    PageVersionService,
    PinnedLimitExceeded,
)
from ..services.product_doc import ProductDocService
from ..utils.html import inject_hide_scrollbar_style
from ..utils.style import build_global_style_css

router = APIRouter(prefix="/api", tags=["pages"])


def _get_db_session() -> Generator[DbSession, None, None]:
    with get_db() as session:
        yield session


def _page_payload(record: PageModel) -> PageResponse:
    return PageResponse(
        id=record.id,
        session_id=record.session_id,
        title=record.title,
        slug=record.slug,
        description=record.description,
        order_index=record.order_index,
        current_version_id=record.current_version_id,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _version_payload(record) -> PageVersionResponse:
    return PageVersionResponse(
        id=record.id,
        page_id=record.page_id,
        version=record.version,
        description=record.description,
        source=getattr(record.source, "value", record.source),
        is_pinned=record.is_pinned,
        is_released=record.is_released,
        created_at=record.created_at,
        available=not record.is_released,
        fallback_used=record.fallback_used,
        previewable=not record.is_released and record.payload_pruned_at is None,
    )


def _accepts_html(request: Request) -> bool:
    accept = request.headers.get("accept", "")
    return "text/html" in accept or "application/xhtml+xml" in accept


def _build_preview_css(product_doc) -> str | None:
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


@router.get("/sessions/{session_id}/pages")
def list_pages(
    session_id: str,
    db: DbSession = Depends(_get_db_session),
) -> dict:
    if db.get(SessionModel, session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")
    service = PageService(db)
    pages = service.list_by_session(session_id)
    return {
        "pages": [_page_payload(record) for record in pages],
        "total": len(pages),
    }


@router.get("/pages/{page_id}")
def get_page(
    page_id: str,
    db: DbSession = Depends(_get_db_session),
) -> PageResponse:
    service = PageService(db)
    record = service.get_by_id(page_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Page not found")
    return _page_payload(record)


@router.get("/pages/{page_id}/versions")
def get_page_versions(
    page_id: str,
    include_released: bool = Query(False),
    db: DbSession = Depends(_get_db_session),
) -> dict:
    page_service = PageService(db)
    page = page_service.get_by_id(page_id)
    if page is None:
        raise HTTPException(status_code=404, detail="Page not found")
    version_service = PageVersionService(db)
    versions = version_service.get_versions(page_id, include_released=include_released)
    return {
        "versions": [_version_payload(record) for record in versions],
        "current_version_id": page.current_version_id,
    }


@router.get("/pages/{page_id}/preview", response_model=None)
def get_page_preview(
    page_id: str,
    request: Request,
    db: DbSession = Depends(_get_db_session),
) -> Response:
    page_service = PageService(db)
    page = page_service.get_by_id(page_id)
    if page is None:
        raise HTTPException(status_code=404, detail="Page not found")

    version_service = PageVersionService(db)
    product_doc = ProductDocService(db).get_by_session_id(page.session_id)
    global_style_css = _build_preview_css(product_doc)
    preview = version_service.build_preview(page_id, global_style_css=global_style_css)
    if preview is None:
        raise HTTPException(status_code=404, detail="No preview available")

    version, html = preview
    html = inject_hide_scrollbar_style(html or "")
    if _accepts_html(request):
        return HTMLResponse(content=html or "")
    return PagePreviewResponse(
        page_id=page.id,
        slug=page.slug,
        html=html,
        version=version.version,
    )

@router.get("/pages/{page_id}/versions/{version_id}/preview")
def preview_page_version(
    page_id: str,
    version_id: int,
    db: DbSession = Depends(_get_db_session),
) -> Response:
    page_service = PageService(db)
    page = page_service.get_by_id(page_id)
    if page is None:
        raise HTTPException(status_code=404, detail="Page not found")

    version_service = PageVersionService(db)
    try:
        record = version_service.preview_version(page_id, version_id)
    except PageVersionNotFoundError:
        raise HTTPException(status_code=404, detail="Version not found")
    except PageVersionReleasedError:
        return JSONResponse(
            status_code=410,
            content={
                "error": "version_released",
                "message": "This version has been released and is no longer available for preview",
            },
        )

    return {
        "id": record.id,
        "version": record.version,
        "html": record.html or "",
        "description": record.description,
        "fallback_used": record.fallback_used,
        "created_at": record.created_at,
    }


@router.post("/pages/{page_id}/versions/{version_id}/pin")
def pin_page_version(
    page_id: str,
    version_id: int,
    db: DbSession = Depends(_get_db_session),
) -> Response:
    page_service = PageService(db)
    page = page_service.get_by_id(page_id)
    if page is None:
        raise HTTPException(status_code=404, detail="Page not found")

    version_service = PageVersionService(db)
    record = version_service.get_by_id(version_id)
    if record is None or record.page_id != page_id:
        raise HTTPException(status_code=404, detail="Version not found")
    if record.is_released:
        return JSONResponse(
            status_code=410,
            content={
                "error": "version_released",
                "message": "This version has been released and is no longer available",
            },
        )

    try:
        record = version_service.pin_version(version_id)
    except PinnedLimitExceeded as exc:
        return JSONResponse(
            status_code=409,
            content={
                "error": "pinned_limit_exceeded",
                "message": "Maximum 2 versions can be pinned per page",
                "current_pinned": exc.current_pinned,
            },
        )
    except PageVersionReleasedError:
        return JSONResponse(
            status_code=410,
            content={
                "error": "version_released",
                "message": "This version has been released and is no longer available",
            },
        )
    except PageVersionNotFoundError:
        raise HTTPException(status_code=404, detail="Version not found")

    db.commit()
    return {"message": "Pinned successfully", "version": _version_payload(record)}


@router.post("/pages/{page_id}/versions/{version_id}/unpin")
def unpin_page_version(
    page_id: str,
    version_id: int,
    db: DbSession = Depends(_get_db_session),
) -> Response:
    page_service = PageService(db)
    page = page_service.get_by_id(page_id)
    if page is None:
        raise HTTPException(status_code=404, detail="Page not found")

    version_service = PageVersionService(db)
    record = version_service.get_by_id(version_id)
    if record is None or record.page_id != page_id:
        raise HTTPException(status_code=404, detail="Version not found")

    try:
        record = version_service.unpin_version(version_id)
    except PageVersionNotFoundError:
        raise HTTPException(status_code=404, detail="Version not found")

    db.commit()
    return {"message": "Unpinned successfully", "version": _version_payload(record)}


@router.post("/pages/{page_id}/rollback")
def rollback_page_version(
    page_id: str,
    db: DbSession = Depends(_get_db_session),
) -> Response:
    page_service = PageService(db)
    if page_service.get_by_id(page_id) is None:
        raise HTTPException(status_code=404, detail="Page not found")
    return JSONResponse(
        status_code=410,
        content={
            "error": "rollback_not_supported",
            "message": "Page rollback is no longer supported. Use ProjectSnapshot rollback instead.",
        },
    )


__all__ = ["router"]
