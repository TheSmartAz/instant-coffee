from __future__ import annotations

from typing import Generator

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from ..config import get_model_catalog, get_settings, update_runtime_overrides
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


def _find_model_option(model_id: str | None) -> dict | None:
    if not model_id:
        return None
    for entry in get_model_catalog():
        if entry.get("id") == model_id:
            return entry
    return None


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
        model_option = _find_model_option(data["model"])
        if model_option:
            if not has_api_key and model_option.get("key"):
                overrides["default_key"] = model_option["key"]
                overrides["openai_api_key"] = model_option["key"]
            if model_option.get("base_url"):
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


__all__ = ["router"]
