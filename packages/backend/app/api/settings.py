from __future__ import annotations

from typing import Generator

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from ..config import get_settings
from ..db.utils import get_db

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsPayload(BaseModel):
    api_key: str | None = None
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    output_dir: str | None = None
    auto_save: bool | None = None


_settings_state: dict = {}


def _get_db_session() -> Generator[DbSession, None, None]:
    with get_db() as session:
        yield session


def _resolve_settings() -> dict:
    settings = get_settings()
    state = {
        "api_key": _settings_state.get("api_key") or settings.default_key or "",
        "model": _settings_state.get("model") or settings.model,
        "temperature": _settings_state.get("temperature", settings.temperature),
        "max_tokens": _settings_state.get("max_tokens", settings.max_tokens),
        "output_dir": _settings_state.get("output_dir", settings.output_dir),
        "auto_save": _settings_state.get("auto_save", settings.auto_save),
    }
    return state


@router.get("")
def get_settings_endpoint(db: DbSession = Depends(_get_db_session)) -> dict:
    return _resolve_settings()


@router.put("")
def update_settings(payload: SettingsPayload, db: DbSession = Depends(_get_db_session)) -> dict:
    if hasattr(payload, "model_dump"):
        data = payload.model_dump(exclude_unset=True)
    else:  # pragma: no cover - pydantic v1 compatibility
        data = payload.dict(exclude_unset=True)
    _settings_state.update(data)
    return _resolve_settings()


__all__ = ["router"]
