from __future__ import annotations

from typing import Generator

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session as DbSession

from ..db.models import ProductDocHistory, ProductDocStatus, VersionSource
from ..db.utils import get_db
from ..exceptions import PinnedLimitExceeded
from ..schemas.product_doc import (
    ProductDocHistoryListItem,
    ProductDocHistoryListResponse,
    ProductDocHistoryPinResponse,
    ProductDocHistoryResponse,
    ProductDocResponse,
)
from ..services.product_doc import ProductDocService

router = APIRouter(prefix="/api/sessions", tags=["product-doc"])


def _get_db_session() -> Generator[DbSession, None, None]:
    with get_db() as session:
        yield session


def _status_value(status: str | ProductDocStatus) -> str:
    if isinstance(status, ProductDocStatus):
        return status.value
    return str(status)


def _source_value(source: str | VersionSource) -> str:
    if isinstance(source, VersionSource):
        return source.value
    return str(source)


def _history_available(record: ProductDocHistory) -> bool:
    return record.content is not None or record.structured is not None


def _history_payload(record: ProductDocHistory) -> ProductDocHistoryListItem:
    return ProductDocHistoryListItem(
        id=record.id,
        product_doc_id=record.product_doc_id,
        version=record.version,
        change_summary=record.change_summary or "",
        source=_source_value(record.source),
        is_pinned=bool(record.is_pinned),
        is_released=bool(record.is_released),
        created_at=record.created_at,
        available=_history_available(record),
    )


def _history_detail_payload(record: ProductDocHistory) -> ProductDocHistoryResponse:
    return ProductDocHistoryResponse(
        **_history_payload(record).model_dump(),
        content=record.content or "",
        structured=record.structured or {},
    )


@router.get("/{session_id}/product-doc", response_model=ProductDocResponse)
def get_product_doc(
    session_id: str,
    db: DbSession = Depends(_get_db_session),
) -> ProductDocResponse:
    service = ProductDocService(db)
    record = service.get_by_session_id(session_id)
    if record is None:
        raise HTTPException(status_code=404, detail="ProductDoc not found")
    return ProductDocResponse(
        id=record.id,
        session_id=record.session_id,
        content=record.content,
        structured=record.structured or {},
        version=record.version,
        status=_status_value(record.status),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@router.get(
    "/{session_id}/product-doc/history",
    response_model=ProductDocHistoryListResponse,
)
def get_product_doc_history(
    session_id: str,
    include_released: bool = Query(False, alias="include_released"),
    limit: int | None = Query(None, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: DbSession = Depends(_get_db_session),
) -> ProductDocHistoryListResponse:
    service = ProductDocService(db)
    doc = service.get_by_session_id(session_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="ProductDoc not found")
    total_query = (
        db.query(func.count(ProductDocHistory.id))
        .filter(ProductDocHistory.product_doc_id == doc.id)
    )
    if not include_released:
        total_query = total_query.filter(ProductDocHistory.is_released.is_(False))
    total = total_query.scalar() or 0
    history = service.get_history(
        doc.id,
        include_released=include_released,
        limit=limit,
        offset=offset,
    )
    pinned_count = (
        db.query(func.count(ProductDocHistory.id))
        .filter(ProductDocHistory.product_doc_id == doc.id)
        .filter(ProductDocHistory.is_pinned.is_(True))
        .scalar()
        or 0
    )
    return ProductDocHistoryListResponse(
        history=[_history_payload(record) for record in history],
        total=int(total),
        pinned_count=int(pinned_count),
    )


@router.get(
    "/{session_id}/product-doc/history/{history_id}",
    response_model=ProductDocHistoryResponse,
)
def get_product_doc_history_version(
    session_id: str,
    history_id: int,
    db: DbSession = Depends(_get_db_session),
) -> ProductDocHistoryResponse:
    service = ProductDocService(db)
    doc = service.get_by_session_id(session_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="ProductDoc not found")
    record = service.get_history_version(history_id)
    if record is None or record.product_doc_id != doc.id:
        raise HTTPException(status_code=404, detail="History not found")
    return _history_detail_payload(record)


@router.post(
    "/{session_id}/product-doc/history/{history_id}/pin",
    response_model=ProductDocHistoryPinResponse,
)
def pin_product_doc_history(
    session_id: str,
    history_id: int,
    db: DbSession = Depends(_get_db_session),
) -> ProductDocHistoryPinResponse:
    service = ProductDocService(db)
    doc = service.get_by_session_id(session_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="ProductDoc not found")
    record = service.get_history_version(history_id)
    if record is None or record.product_doc_id != doc.id:
        raise HTTPException(status_code=404, detail="History not found")
    try:
        pinned = service.pin_history(history_id)
    except PinnedLimitExceeded as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "message": str(exc),
                "current_pinned": exc.current_pinned,
            },
        ) from exc
    db.commit()
    return ProductDocHistoryPinResponse(history=_history_payload(pinned))


@router.post(
    "/{session_id}/product-doc/history/{history_id}/unpin",
    response_model=ProductDocHistoryPinResponse,
)
def unpin_product_doc_history(
    session_id: str,
    history_id: int,
    db: DbSession = Depends(_get_db_session),
) -> ProductDocHistoryPinResponse:
    service = ProductDocService(db)
    doc = service.get_by_session_id(session_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="ProductDoc not found")
    record = service.get_history_version(history_id)
    if record is None or record.product_doc_id != doc.id:
        raise HTTPException(status_code=404, detail="History not found")
    history = service.unpin_history(history_id)
    db.commit()
    return ProductDocHistoryPinResponse(history=_history_payload(history))


__all__ = ["router"]
