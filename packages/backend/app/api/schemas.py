from __future__ import annotations

from typing import Generator

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DbSession

from ..db.models import Session as SessionModel
from ..db.utils import get_db
from ..services.state_store import StateStoreService

router = APIRouter(prefix="/api/sessions", tags=["schemas"])


def _get_db_session() -> Generator[DbSession, None, None]:
    with get_db() as session:
        yield session


def _get_state(session_id: str, db: DbSession) -> dict:
    if db.get(SessionModel, session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")
    metadata = StateStoreService(db).get_metadata(session_id)
    if metadata is None:
        raise HTTPException(status_code=404, detail="Session not found")
    state = metadata.graph_state
    return state if isinstance(state, dict) else {}


@router.get("/{session_id}/schemas")
async def get_page_schemas(
    session_id: str,
    db: DbSession = Depends(_get_db_session),
) -> list[dict]:
    state = _get_state(session_id, db)
    schemas = state.get("page_schemas") or []
    if not isinstance(schemas, list):
        return []
    return schemas


@router.get("/{session_id}/schemas/{page_slug}")
async def get_page_schema(
    session_id: str,
    page_slug: str,
    db: DbSession = Depends(_get_db_session),
) -> dict:
    state = _get_state(session_id, db)
    schemas = state.get("page_schemas") or []
    if not isinstance(schemas, list):
        raise HTTPException(status_code=404, detail="Page schema not found")
    for schema in schemas:
        if not isinstance(schema, dict):
            continue
        slug = (schema.get("slug") or "").lower()
        if slug == page_slug.lower():
            return schema
    raise HTTPException(status_code=404, detail="Page schema not found")


@router.get("/{session_id}/registry")
async def get_component_registry(
    session_id: str,
    db: DbSession = Depends(_get_db_session),
) -> dict:
    state = _get_state(session_id, db)
    registry = state.get("component_registry") or {}
    return registry if isinstance(registry, dict) else {}


@router.get("/{session_id}/tokens")
async def get_style_tokens(
    session_id: str,
    db: DbSession = Depends(_get_db_session),
) -> dict:
    state = _get_state(session_id, db)
    tokens = state.get("style_tokens") or {}
    return tokens if isinstance(tokens, dict) else {}


__all__ = ["router"]
