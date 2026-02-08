"""Config bridge — converts backend Settings to agent Config/ModelConfig."""

from __future__ import annotations

import logging
from typing import Optional

from ..config import Settings, get_settings

logger = logging.getLogger(__name__)


def backend_settings_to_agent_config(
    settings: Optional[Settings] = None,
) -> "Config":
    """Build an agent ``Config`` from backend ``Settings``.

    This avoids duplicating API key / model configuration.  The backend
    already has all the credentials in its Settings dataclass; we just
    translate them into the agent's Config format.
    """
    from ic.config import Config, ModelConfig, AgentConfig

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
            )

    default_model = model_id if model_id in models else (next(iter(models)) if models else "")

    cfg = Config.__new__(Config)
    cfg.data_dir = Config.__dataclass_fields__["data_dir"].default_factory()
    cfg.models = models
    cfg.agents = {}
    cfg.default_model = default_model
    cfg._ensure_agents()

    return cfg
