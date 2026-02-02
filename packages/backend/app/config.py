from __future__ import annotations

from dataclasses import dataclass, field
import os
from typing import Any

try:
    from dotenv import find_dotenv, load_dotenv
except Exception:  # pragma: no cover - optional dependency
    find_dotenv = None
    load_dotenv = None


def _load_env() -> None:
    if load_dotenv is None or find_dotenv is None:
        return
    env_path = find_dotenv(usecwd=True)
    if env_path:
        load_dotenv(env_path, override=False)


_load_env()


def _get_env(key: str, default: str | None = None) -> str | None:
    value = os.getenv(key)
    if value is None or value == "":
        return default
    return value


def _get_bool(key: str, default: bool = False) -> bool:
    value = os.getenv(key)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _get_int(key: str, default: int) -> int:
    value = os.getenv(key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _get_float(key: str, default: float) -> float:
    value = os.getenv(key)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


@dataclass
class Settings:
    database_url: str = field(default_factory=lambda: _get_env("DATABASE_URL", "sqlite:///./instant-coffee.db"))
    output_dir: str = field(default_factory=lambda: _get_env("OUTPUT_DIR", "instant-coffee-output"))
    planner_provider: str | None = field(default_factory=lambda: _get_env("PLANNER_PROVIDER"))
    planner_model: str = field(
        default_factory=lambda: _get_env("PLANNER_MODEL")
        or _get_env("MODEL")
        or _get_env("DEFAULT_MODEL", "gpt-4o-mini")
    )
    planner_timeout_seconds: float = field(default_factory=lambda: _get_float("PLANNER_TIMEOUT_SECONDS", 30.0))

    openai_api_key: str | None = field(
        default_factory=lambda: _get_env("OPENAI_API_KEY")
        or _get_env("DMX_API_KEY")
        or _get_env("DMXAPI_API_KEY")
        or _get_env("DEFAULT_KEY")
    )
    openai_base_url: str = field(
        default_factory=lambda: _get_env("OPENAI_BASE_URL")
        or _get_env("DMX_BASE_URL")
        or _get_env("DMXAPI_BASE_URL")
        or _get_env("DEFAULT_BASE_URL", "https://api.openai.com/v1")
    )
    openai_timeout_seconds: float = field(default_factory=lambda: _get_float("OPENAI_TIMEOUT_SECONDS", 60.0))
    openai_max_retries: int = field(default_factory=lambda: _get_int("OPENAI_MAX_RETRIES", 3))
    openai_base_delay: float = field(default_factory=lambda: _get_float("OPENAI_BASE_DELAY", 1.0))
    openai_api_mode: str = field(default_factory=lambda: _get_env("OPENAI_API_MODE", "responses") or "responses")

    anthropic_api_key: str | None = field(default_factory=lambda: _get_env("ANTHROPIC_API_KEY"))
    anthropic_base_url: str = field(default_factory=lambda: _get_env("ANTHROPIC_BASE_URL", "https://api.anthropic.com"))
    anthropic_api_version: str = field(default_factory=lambda: _get_env("ANTHROPIC_API_VERSION", "2023-06-01"))

    default_base_url: str | None = field(default_factory=lambda: _get_env("DEFAULT_BASE_URL"))
    default_key: str | None = field(default_factory=lambda: _get_env("DEFAULT_KEY"))

    model: str = field(default_factory=lambda: _get_env("MODEL") or _get_env("DEFAULT_MODEL", "gpt-4o-mini"))
    temperature: float = field(default_factory=lambda: _get_float("TEMPERATURE", 0.7))
    max_tokens: int = field(default_factory=lambda: _get_int("MAX_TOKENS", 8000))
    auto_save: bool = field(default_factory=lambda: _get_bool("AUTO_SAVE", True))

    max_concurrent_tasks: int = field(default_factory=lambda: _get_int("MAX_CONCURRENCY", 3))

    migrate_v04_on_startup: bool = field(default_factory=lambda: _get_bool("MIGRATE_V04_ON_STARTUP", False))

    task_timeout_minutes: int = field(default_factory=lambda: _get_int("TASK_TIMEOUT_MINUTES", 30))
    task_cleanup_interval_seconds: float = field(
        default_factory=lambda: _get_float("TASK_TIMEOUT_CLEANUP_INTERVAL", 60.0)
    )


_settings: Settings | None = None
_runtime_overrides: dict[str, Any] = {}


def _apply_runtime_overrides(settings: Settings) -> None:
    if not _runtime_overrides:
        return
    for key, value in _runtime_overrides.items():
        if value is None:
            continue
        if hasattr(settings, key):
            setattr(settings, key, value)


def update_runtime_overrides(overrides: dict[str, Any]) -> None:
    if not overrides:
        return
    for key, value in overrides.items():
        if value is None:
            continue
        _runtime_overrides[key] = value
    if _settings is not None:
        _apply_runtime_overrides(_settings)


def get_runtime_overrides() -> dict[str, Any]:
    return dict(_runtime_overrides)


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    _apply_runtime_overrides(_settings)
    return _settings


def refresh_settings() -> Settings:
    """Rebuild settings from environment variables."""
    global _settings
    _settings = Settings()
    _apply_runtime_overrides(_settings)
    return _settings


def _iter_env_keys_in_order() -> list[str]:
    if find_dotenv is None:
        return list(os.environ.keys())
    env_path = find_dotenv(usecwd=True)
    if not env_path:
        return list(os.environ.keys())
    keys: list[str] = []
    seen: set[str] = set()
    try:
        with open(env_path, "r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                if "=" not in stripped:
                    continue
                key = stripped.split("=", 1)[0].strip()
                if not key or key in seen:
                    continue
                keys.append(key)
                seen.add(key)
    except Exception:
        return list(os.environ.keys())

    for key in os.environ.keys():
        if key in seen:
            continue
        if key == "MODEL" or key.endswith("_MODEL"):
            keys.append(key)
            seen.add(key)
    return keys


def get_model_catalog() -> list[dict[str, str | None]]:
    keys = _iter_env_keys_in_order()
    models: list[dict[str, str | None]] = []
    seen: set[str] = set()
    for key in keys:
        if key != "MODEL" and not key.endswith("_MODEL"):
            continue
        value = os.getenv(key)
        if not value:
            continue
        model_id = value.strip()
        if not model_id or model_id.startswith("${"):
            continue
        if model_id in seen:
            continue
        prefix = key[: -len("_MODEL")] if key.endswith("_MODEL") else ""
        models.append(
            {
                "id": model_id,
                "label": model_id,
                "key": os.getenv(f"{prefix}_KEY") if prefix else None,
                "base_url": os.getenv(f"{prefix}_BASE_URL") if prefix else None,
            }
        )
        seen.add(model_id)
    return models


__all__ = [
    "Settings",
    "get_settings",
    "refresh_settings",
    "update_runtime_overrides",
    "get_runtime_overrides",
    "get_model_catalog",
]
