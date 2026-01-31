from __future__ import annotations

from dataclasses import dataclass, field
import os

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
        default_factory=lambda: _get_env("OPENAI_API_KEY") or _get_env("DEFAULT_KEY")
    )
    openai_base_url: str = field(
        default_factory=lambda: _get_env("OPENAI_BASE_URL")
        or _get_env("DEFAULT_BASE_URL", "https://api.openai.com/v1")
    )
    openai_timeout_seconds: float = field(default_factory=lambda: _get_float("OPENAI_TIMEOUT_SECONDS", 60.0))
    openai_max_retries: int = field(default_factory=lambda: _get_int("OPENAI_MAX_RETRIES", 3))
    openai_base_delay: float = field(default_factory=lambda: _get_float("OPENAI_BASE_DELAY", 1.0))

    anthropic_api_key: str | None = field(default_factory=lambda: _get_env("ANTHROPIC_API_KEY"))
    anthropic_base_url: str = field(default_factory=lambda: _get_env("ANTHROPIC_BASE_URL", "https://api.anthropic.com"))
    anthropic_api_version: str = field(default_factory=lambda: _get_env("ANTHROPIC_API_VERSION", "2023-06-01"))

    default_base_url: str | None = field(default_factory=lambda: _get_env("DEFAULT_BASE_URL"))
    default_key: str | None = field(default_factory=lambda: _get_env("DEFAULT_KEY"))

    model: str = field(default_factory=lambda: _get_env("MODEL") or _get_env("DEFAULT_MODEL", "gpt-4o-mini"))
    temperature: float = field(default_factory=lambda: _get_float("TEMPERATURE", 0.7))
    max_tokens: int = field(default_factory=lambda: _get_int("MAX_TOKENS", 1200))
    auto_save: bool = field(default_factory=lambda: _get_bool("AUTO_SAVE", True))

    max_concurrent_tasks: int = field(default_factory=lambda: _get_int("MAX_CONCURRENCY", 3))


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def refresh_settings() -> Settings:
    """Rebuild settings from environment variables."""
    global _settings
    _settings = Settings()
    return _settings


__all__ = ["Settings", "get_settings", "refresh_settings"]
