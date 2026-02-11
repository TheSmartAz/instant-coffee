from __future__ import annotations

from typing import Generator

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from ..config import get_model_catalog, get_settings, update_runtime_overrides
from ..llm.model_catalog import get_model_entry
from ..db.utils import get_db

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsPayload(BaseModel):
    api_key: str | None = None
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    output_dir: str | None = None
    auto_save: bool | None = None


def _get_db_session() -> Generator[DbSession, None, None]:
    with get_db() as session:
        yield session


def _resolve_settings() -> dict:
    settings = get_settings()
    catalog = get_model_catalog()
    available_models = [
        {"id": entry["id"], "label": entry.get("label") or entry["id"]}
        for entry in catalog
    ]
    if settings.model and all(entry["id"] != settings.model for entry in available_models):
        available_models.append({"id": settings.model, "label": settings.model})
    return {
        "api_key": settings.default_key or "",
        "model": settings.model,
        "temperature": settings.temperature,
        "max_tokens": settings.max_tokens,
        "output_dir": settings.output_dir,
        "auto_save": settings.auto_save,
        "available_models": available_models,
    }


@router.get("")
def get_settings_endpoint(db: DbSession = Depends(_get_db_session)) -> dict:
    return _resolve_settings()


@router.put("")
def update_settings(payload: SettingsPayload, db: DbSession = Depends(_get_db_session)) -> dict:
    if hasattr(payload, "model_dump"):
        data = payload.model_dump(exclude_unset=True)
    else:  # pragma: no cover - pydantic v1 compatibility
        data = payload.dict(exclude_unset=True)
    overrides: dict[str, object] = {}
    api_key_value = data.get("api_key")
    has_api_key = api_key_value is not None and str(api_key_value).strip() != ""

    if "model" in data and data.get("model"):
        overrides["model"] = data["model"]
        model_option = get_model_entry(data["model"])
        if model_option and model_option.get("base_url"):
            overrides["default_base_url"] = model_option["base_url"]
            overrides["openai_base_url"] = model_option["base_url"]

    if has_api_key:
        overrides["default_key"] = api_key_value
        overrides["openai_api_key"] = api_key_value

    if "temperature" in data:
        overrides["temperature"] = data["temperature"]
    if "max_tokens" in data:
        overrides["max_tokens"] = data["max_tokens"]
    if "output_dir" in data:
        overrides["output_dir"] = data["output_dir"]
    if "auto_save" in data:
        overrides["auto_save"] = data["auto_save"]

    update_runtime_overrides(overrides)
    return _resolve_settings()


class CleanupRequest(BaseModel):
    max_session_age_days: int = 90
    max_sessions: int = 500
    max_messages_per_session: int = 1000
    dry_run: bool = True


@router.post("/cleanup")
def run_cleanup(
    payload: CleanupRequest,
    db: DbSession = Depends(_get_db_session),
) -> dict:
    from ..services.cleanup import CleanupPolicy, CleanupService

    policy = CleanupPolicy(
        max_session_age_days=payload.max_session_age_days,
        max_sessions=payload.max_sessions,
        max_messages_per_session=payload.max_messages_per_session,
        dry_run=payload.dry_run,
    )
    service = CleanupService(db, policy)
    results = service.run_all()
    return {"dry_run": payload.dry_run, "deleted": results}


__all__ = ["router"]
