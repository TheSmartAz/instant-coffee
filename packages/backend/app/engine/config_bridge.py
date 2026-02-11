"""Config bridge — converts backend Settings to agent Config/ModelConfig."""

from __future__ import annotations

from dataclasses import MISSING
import logging
from typing import Optional

from ..config import Settings, get_settings

logger = logging.getLogger(__name__)


def _new_config_with_defaults(config_cls: type["Config"]) -> "Config":
    """Create a Config instance with all dataclass defaults initialized."""
    cfg = config_cls.__new__(config_cls)

    for field_name, field_def in config_cls.__dataclass_fields__.items():
        if field_def.default_factory is not MISSING:
            setattr(cfg, field_name, field_def.default_factory())
        elif field_def.default is not MISSING:
            setattr(cfg, field_name, field_def.default)

    return cfg


def backend_settings_to_agent_config(
    settings: Optional[Settings] = None,
) -> "Config":
    """Build an agent ``Config`` from backend ``Settings``.

    This avoids duplicating API key / model configuration.  The backend
    already has all the credentials in its Settings dataclass; we just
    translate them into the agent's Config format.
    """
    from ic.config import Config, ModelConfig

    s = settings or get_settings()

    models: dict[str, ModelConfig] = {}

    api_key = s.openai_api_key or s.default_key or ""
    base_url = s.default_base_url or s.openai_base_url or ""
    model_id = s.model or "gpt-4o"

    if api_key:
        models[model_id] = ModelConfig(
            name=model_id,
            model=model_id,
            api_key=api_key,
            base_url=base_url or None,
            max_tokens=s.max_tokens,
            temperature=s.temperature,
            timeout=s.openai_timeout_seconds,
        )

    if s.anthropic_api_key:
        for mid in ["claude-sonnet-4-20250514", "claude-haiku-4-20250514"]:
            models[mid] = ModelConfig(
                name=mid,
                model=mid,
                api_key=s.anthropic_api_key,
                base_url=f"{s.anthropic_base_url}/v1/",
                max_tokens=s.max_tokens,
                temperature=s.temperature,
                timeout=s.openai_timeout_seconds,
            )

    default_model = model_id if model_id in models else (next(iter(models)) if models else "")

    cfg = _new_config_with_defaults(Config)
    cfg.models = models
    cfg.agents = {}
    cfg.default_model = default_model
    cfg._auto_select_pointers()
    cfg._ensure_agents()

    return cfg
