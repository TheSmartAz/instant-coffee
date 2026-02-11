from __future__ import annotations

import logging
from typing import Any, Generator

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session as DbSession

from ..db.models import Session as SessionModel
from ..db.utils import get_db
from ..services.app_data_store import get_app_data_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sessions", tags=["data"])


def _get_db_session() -> Generator[DbSession, None, None]:
    with get_db() as session:
        yield session


def _require_session(db: DbSession, session_id: str) -> None:
    if db.get(SessionModel, session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")


def _raise_store_error(exc: Exception, *, default_status: int = 422) -> None:
    if isinstance(exc, HTTPException):
        raise exc

    message = str(exc)
    lowered = message.lower()

    if isinstance(exc, RuntimeError):
        raise HTTPException(status_code=409, detail="App data store is unavailable") from exc

    if "order_by" in lowered:
        raise HTTPException(status_code=400, detail=message) from exc

    if "table" in lowered and (
        "not found" in lowered
        or "unknown" in lowered
        or "invalid" in lowered
        or "cannot contain" in lowered
    ):
        raise HTTPException(status_code=404, detail=message) from exc

    if "identifier" in lowered:
        raise HTTPException(status_code=400, detail=message) from exc

    if "sqlstate" in lowered and "23505" in lowered:
        raise HTTPException(status_code=409, detail="Duplicate key conflict") from exc

    sqlstate = getattr(exc, "sqlstate", None)
    if sqlstate == "23505":
        raise HTTPException(status_code=409, detail="Duplicate key conflict") from exc

    raise HTTPException(status_code=default_status, detail=message or "Invalid request") from exc


def _get_store_or_409():
    store = get_app_data_store()
    if not store.enabled:
        raise HTTPException(status_code=409, detail="App data store is unavailable")
    return store


@router.get("/{session_id}/data/tables")
async def list_data_tables(
    session_id: str,
    db: DbSession = Depends(_get_db_session),
) -> dict[str, Any]:
    _require_session(db, session_id)
    store = get_app_data_store()
    if not store.enabled:
        return {"schema": None, "tables": []}
    try:
        result = await store.list_tables(session_id)
    except Exception as exc:  # pragma: no cover - defensive mapping
        _raise_store_error(exc, default_status=500)
    return {
        "schema": result.get("schema"),
        "tables": result.get("tables") or [],
    }


@router.get("/{session_id}/data/{table}/stats")
async def get_table_stats(
    session_id: str,
    table: str,
    db: DbSession = Depends(_get_db_session),
) -> dict[str, Any]:
    _require_session(db, session_id)
    store = _get_store_or_409()
    try:
        stats = await store.get_table_stats(session_id, table)
    except Exception as exc:  # pragma: no cover - defensive mapping
        _raise_store_error(exc)
    return stats


@router.get("/{session_id}/data/{table}")
async def query_data_table(
    session_id: str,
    table: str,
    limit: int = Query(50, ge=1),
    offset: int = Query(0, ge=0),
    order_by: str | None = Query(default=None),
    db: DbSession = Depends(_get_db_session),
) -> dict[str, Any]:
    _require_session(db, session_id)
    store = _get_store_or_409()
    try:
        result = await store.query_table(
            session_id,
            table,
            limit=limit,
            offset=offset,
            order_by=order_by,
        )
    except Exception as exc:  # pragma: no cover - defensive mapping
        _raise_store_error(exc)

    records = result.get("rows") or []
    return {
        "records": records,
        "total": int(result.get("total", len(records))),
        "limit": int(result.get("limit", min(limit, 200))),
        "offset": int(result.get("offset", offset)),
        "order_by": result.get("order_by"),
    }


@router.post("/{session_id}/data/{table}")
async def insert_data_record(
    session_id: str,
    table: str,
    payload: Any = Body(...),
    db: DbSession = Depends(_get_db_session),
) -> dict[str, Any]:
    _require_session(db, session_id)
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="Request body must be an object")

    store = _get_store_or_409()
    try:
        record = await store.insert_record(session_id, table, payload)
    except Exception as exc:  # pragma: no cover - defensive mapping
        _raise_store_error(exc)
    return {"record": record}


@router.delete("/{session_id}/data/{table}/{row_id}")
async def delete_data_record(
    session_id: str,
    table: str,
    row_id: int,
    db: DbSession = Depends(_get_db_session),
) -> dict[str, Any]:
    _require_session(db, session_id)
    store = _get_store_or_409()
    try:
        deleted = await store.delete_record(session_id, table, row_id)
    except Exception as exc:  # pragma: no cover - defensive mapping
        _raise_store_error(exc)

    if not deleted:
        raise HTTPException(status_code=404, detail="Record not found")
    return {"deleted": True}


__all__ = ["router"]
