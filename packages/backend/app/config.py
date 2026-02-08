from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from typing import Any

try:
    from dotenv import find_dotenv, load_dotenv
except Exception:  # pragma: no cover - optional dependency
    find_dotenv = None
    load_dotenv = None

from .llm.model_catalog import (
    get_default_base_url,
    get_default_model_id,
    get_model_catalog as _get_model_catalog,
    get_model_entry,
)


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


def _get_json(key: str, default: Any) -> Any:
    value = os.getenv(key)
    if value is None or value == "":
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def _get_str_list(key: str, default: list[str]) -> list[str]:
    value = os.getenv(key)
    if value is None or value.strip() == "":
        return list(default)
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            result = [str(item).strip() for item in parsed if str(item).strip()]
            return result or list(default)
    except json.JSONDecodeError:
        pass
    result = [item.strip() for item in value.split(",") if item.strip()]
    return result or list(default)


def _resolve_default_model_id() -> str:
    return _get_env("MODEL") or _get_env("DEFAULT_MODEL") or get_default_model_id()


def _resolve_default_base_url() -> str:
    entry = get_model_entry(_resolve_default_model_id())
    if entry and entry.get("base_url"):
        return entry["base_url"]
    return get_default_base_url()


DEFAULT_MODEL_POOLS: dict[str, Any] = {
    "classifier": ["gpt-5-mini", "gemini-3-flash-preview", "grok-code-fast-1"],
    "writer": {
        "default": ["glm-4.7", "DeepSeek-V3.2", "qwen-max-latest", "hunyuan-2.0-instruct-20251111"],
        "landing": ["gemini-3-flash-preview", "gpt-5-mini", "glm-4.7"],
        "card": ["gemini-3-flash-preview", "gpt-5-mini", "glm-4.7"],
        "invitation": ["gemini-3-flash-preview", "gpt-5-mini", "glm-4.7"],
        "ecommerce": ["glm-4.7", "DeepSeek-V3.2", "qwen-max-latest", "hunyuan-2.0-instruct-20251111"],
        "booking": ["glm-4.7", "DeepSeek-V3.2", "qwen-max-latest", "hunyuan-2.0-instruct-20251111"],
        "dashboard": ["glm-4.7", "DeepSeek-V3.2", "qwen-max-latest", "hunyuan-2.0-instruct-20251111"],
    },
    "expander": ["gpt-5-mini", "gemini-3-flash-preview", "glm-4.7", "DeepSeek-V3.2"],
    "validator": ["glm-4.7", "DeepSeek-V3.2", "qwen-max-latest"],
    "style_refiner": {
        "default": ["gemini-3-flash-preview", "gpt-5-mini", "kimi-k2.5"],
        "landing": ["gemini-3-flash-preview", "kimi-k2.5", "gpt-5-mini"],
        "card": ["gemini-3-flash-preview", "kimi-k2.5", "gpt-5-mini"],
        "invitation": ["gemini-3-flash-preview", "kimi-k2.5", "gpt-5-mini"],
    },
}


TOOL_POLICY_DEFAULT_ALLOWED_CMD_PREFIXES = [
    "npm",
    "npx",
    "node",
    "python",
    "pip",
    "git",
    "ls",
    "cat",
    "echo",
    "mkdir",
    "cp",
]


@dataclass
class Settings:
    database_url: str = field(default_factory=lambda: _get_env("DATABASE_URL", "sqlite:///./instant-coffee.db"))
    app_data_pg_pool_min_size: int = field(default_factory=lambda: _get_int("APP_DATA_PG_POOL_MIN_SIZE", 1))
    app_data_pg_pool_max_size: int = field(default_factory=lambda: _get_int("APP_DATA_PG_POOL_MAX_SIZE", 15))
    app_data_pg_pool_command_timeout: float = field(
        default_factory=lambda: _get_float("APP_DATA_PG_POOL_COMMAND_TIMEOUT", 30.0)
    )
    run_api_enabled: bool = field(default_factory=lambda: _get_bool("RUN_API_ENABLED", True))
    chat_use_run_adapter: bool = field(default_factory=lambda: _get_bool("CHAT_USE_RUN_ADAPTER", False))
    tool_policy_enabled: bool = field(default_factory=lambda: _get_bool("TOOL_POLICY_ENABLED", True))
    tool_policy_mode: str = field(default_factory=lambda: _get_env("TOOL_POLICY_MODE", "log_only") or "log_only")
    tool_policy_allowed_cmd_prefixes: list[str] = field(
        default_factory=lambda: _get_str_list(
            "TOOL_POLICY_ALLOWED_CMD_PREFIXES",
            TOOL_POLICY_DEFAULT_ALLOWED_CMD_PREFIXES,
        )
    )
    tool_policy_large_output_bytes: int = field(
        default_factory=lambda: _get_int("TOOL_POLICY_LARGE_OUTPUT_BYTES", 100 * 1024)
    )
    output_dir: str = field(default_factory=lambda: _get_env("OUTPUT_DIR", "instant-coffee-output"))
    cors_allow_origins: list[str] = field(default_factory=lambda: _get_str_list("CORS_ALLOW_ORIGINS", ["*"]))
    cors_allow_methods: list[str] = field(default_factory=lambda: _get_str_list("CORS_ALLOW_METHODS", ["*"]))
    cors_allow_headers: list[str] = field(default_factory=lambda: _get_str_list("CORS_ALLOW_HEADERS", ["*"]))
    cors_allow_credentials: bool = field(default_factory=lambda: _get_bool("CORS_ALLOW_CREDENTIALS", False))
    planner_provider: str | None = field(default_factory=lambda: _get_env("PLANNER_PROVIDER"))
    planner_model: str = field(
        default_factory=lambda: _get_env("PLANNER_MODEL") or "kimi-k2.5"
    )
    planner_timeout_seconds: float = field(default_factory=lambda: _get_float("PLANNER_TIMEOUT_SECONDS", 30.0))

    openai_api_key: str | None = field(
        default_factory=lambda: _get_env("OPENAI_API_KEY")
        or _get_env("DMX_API_KEY")
        or _get_env("DMXAPI_API_KEY")
        or _get_env("DEFAULT_KEY")
    )
    openai_base_url: str = field(default_factory=_resolve_default_base_url)
    openai_timeout_seconds: float = field(default_factory=lambda: _get_float("OPENAI_TIMEOUT_SECONDS", 60.0))
    openai_max_retries: int = field(default_factory=lambda: _get_int("OPENAI_MAX_RETRIES", 2))
    openai_base_delay: float = field(default_factory=lambda: _get_float("OPENAI_BASE_DELAY", 1.0))
    openai_api_mode: str = field(default_factory=lambda: _get_env("OPENAI_API_MODE", "responses") or "responses")

    anthropic_api_key: str | None = field(default_factory=lambda: _get_env("ANTHROPIC_API_KEY"))
    anthropic_base_url: str = field(default_factory=lambda: _get_env("ANTHROPIC_BASE_URL", "https://api.anthropic.com"))
    anthropic_api_version: str = field(default_factory=lambda: _get_env("ANTHROPIC_API_VERSION", "2023-06-01"))

    default_base_url: str | None = field(default_factory=lambda: _get_env("DEFAULT_BASE_URL"))
    default_key: str | None = field(
        default_factory=lambda: _get_env("DEFAULT_KEY")
        or _get_env("DMXAPI_API_KEY")
        or _get_env("DMX_API_KEY")
        or _get_env("OPENAI_API_KEY")
    )

    model: str = field(default_factory=_resolve_default_model_id)
    model_light: str | None = field(default_factory=lambda: _get_env("MODEL_LIGHT"))
    model_mid: str | None = field(default_factory=lambda: _get_env("MODEL_MID"))
    model_heavy: str | None = field(default_factory=lambda: _get_env("MODEL_HEAVY"))
    model_classifier: str | None = field(default_factory=lambda: _get_env("MODEL_CLASSIFIER"))
    model_writer: str | None = field(default_factory=lambda: _get_env("MODEL_WRITER"))
    model_expander: str | None = field(default_factory=lambda: _get_env("MODEL_EXPANDER"))
    model_validator: str | None = field(default_factory=lambda: _get_env("MODEL_VALIDATOR"))
    model_style_refiner: str | None = field(default_factory=lambda: _get_env("MODEL_STYLE_REFINER"))
    model_pools: dict[str, Any] = field(default_factory=lambda: _get_json("MODEL_POOLS", DEFAULT_MODEL_POOLS))
    model_failure_threshold: int = field(default_factory=lambda: _get_int("MODEL_FAILURE_THRESHOLD", 3))
    model_failure_ttl_seconds: int = field(default_factory=lambda: _get_int("MODEL_FAILURE_TTL_SECONDS", 900))
    model_fallback_attempts: int = field(default_factory=lambda: _get_int("MODEL_FALLBACK_ATTEMPTS", 3))
    temperature: float = field(default_factory=lambda: _get_float("TEMPERATURE", 0.7))
    max_tokens: int = field(default_factory=lambda: _get_int("MAX_TOKENS", 8000))
    auto_save: bool = field(default_factory=lambda: _get_bool("AUTO_SAVE", True))
    use_langgraph: bool = field(
        default_factory=lambda: _get_bool("USE_LANGGRAPH", _get_bool("FF_USE_LANGGRAPH", False))
    )
    use_engine: bool = field(
        default_factory=lambda: _get_bool("USE_ENGINE", True)
    )
    langgraph_checkpointer: str = field(
        default_factory=lambda: _get_env("LANGGRAPH_CHECKPOINTER", "sqlite") or "sqlite"
    )
    langgraph_checkpoint_url: str | None = field(default_factory=lambda: _get_env("LANGGRAPH_CHECKPOINT_URL"))
    mcp_enabled: bool = field(default_factory=lambda: _get_bool("ENABLE_MCP", _get_bool("USE_MCP", False)))
    mcp_servers: dict[str, Any] = field(default_factory=lambda: _get_json("MCP_SERVERS", {}))
    mcp_server_url: str | None = field(default_factory=lambda: _get_env("MCP_SERVER_URL"))
    style_extractor_enabled: bool = field(
        default_factory=lambda: _get_bool("ENABLE_STYLE_EXTRACTOR", True)
    )

    aesthetic_scoring_enabled: bool = field(
        default_factory=lambda: _get_bool("ENABLE_AESTHETIC_SCORING", False)
    )
    aesthetic_thresholds: dict[str, Any] = field(
        default_factory=lambda: _get_json("AESTHETIC_THRESHOLDS", {})
    )

    verify_gate_enabled: bool = field(default_factory=lambda: _get_bool("VERIFY_GATE_ENABLED", True))
    verify_gate_auto_fix_enabled: bool = field(
        default_factory=lambda: _get_bool("VERIFY_GATE_AUTO_FIX_ENABLED", True)
    )
    verify_gate_max_retry: int = field(default_factory=lambda: _get_int("VERIFY_GATE_MAX_RETRY", 1))

    max_concurrent_tasks: int = field(default_factory=lambda: _get_int("MAX_CONCURRENCY", 3))

    migrate_v04_on_startup: bool = field(default_factory=lambda: _get_bool("MIGRATE_V04_ON_STARTUP", False))

    task_timeout_seconds: float = field(default_factory=lambda: _get_float("TASK_TIMEOUT_SECONDS", 600.0))
    task_timeout_minutes: int = field(default_factory=lambda: _get_int("TASK_TIMEOUT_MINUTES", 30))
    task_cleanup_interval_seconds: float = field(
        default_factory=lambda: _get_float("TASK_TIMEOUT_CLEANUP_INTERVAL", 60.0)
    )
    interview_timeout_seconds: float = field(
        default_factory=lambda: _get_float("INTERVIEW_TIMEOUT_SECONDS", 180.0)
    )
    product_doc_timeout_seconds: float = field(
        default_factory=lambda: _get_float("PRODUCT_DOC_TIMEOUT_SECONDS", 180.0)
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


def get_model_catalog() -> list[dict[str, str | None]]:
    return _get_model_catalog()


def get_model_aliases(settings: Settings | None = None) -> dict[str, str]:
    resolved = settings or get_settings()
    default_model = resolved.model
    return {
        "light": resolved.model_light or default_model,
        "mid": resolved.model_mid or default_model,
        "heavy": resolved.model_heavy or default_model,
        "default": default_model,
    }


__all__ = [
    "Settings",
    "DEFAULT_MODEL_POOLS",
    "get_settings",
    "refresh_settings",
    "update_runtime_overrides",
    "get_runtime_overrides",
    "get_model_catalog",
    "get_model_aliases",
]
