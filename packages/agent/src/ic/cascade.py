"""Cascading configuration management for IC agent.

Configuration priority (highest first):
1. Environment variables
2. .instant-coffee/config.local.toml (git-ignored, per-machine overrides)
3. .instant-coffee/config.toml (project-specific)
4. ~/.ic/config.toml (user defaults)

This allows:
- User defaults across all projects
- Project-specific overrides (committed to git)
- Local overrides (not committed, for dev differences)
- Environment variables for CI/CD
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:
    import tomli as tomllib


@dataclass
class ConfigLayer:
    """A single layer in the configuration cascade."""

    name: str
    path: Path | None
    data: dict[str, Any] = field(default_factory=dict)
    source: str = ""

    @classmethod
    def from_file(cls, path: Path) -> ConfigLayer:
        """Load a config layer from a TOML file."""
        if not path.exists():
            return cls(name=path.stem, path=path, data={}, source="file")

        try:
            data = tomllib.loads(path.read_bytes().decode())
            return cls(name=path.stem, path=path, data=data, source="file")
        except Exception as e:
            print(f"Warning: Failed to load {path}: {e}")
            return cls(name=path.stem, path=path, data={}, source="file")

    @classmethod
    def from_env(cls) -> ConfigLayer:
        """Load config from environment variables."""
        data = {}

        # DMXAPI key → register all known DMXAPI models
        dmx_key = (
            os.getenv("DMXAPI_API_KEY")
            or os.getenv("DMX_API_KEY")
            or os.getenv("DEFAULT_KEY")
        )
        if dmx_key:
            base = os.getenv("DEFAULT_BASE_URL", "https://www.dmxapi.cn/v1")
            models = data.setdefault("models", {})
            for mid in [
                "kimi-k2.5", "DeepSeek-V3.2", "gpt-5-mini", "glm-4.7",
                "qwen3-max-2026-01-23", "MiniMax-M2.1",
                "hunyuan-2.0-instruct-20251111", "gemini-3-flash-preview",
                "grok-code-fast-1",
            ]:
                models[mid] = {"api_key": dmx_key, "base_url": base}

        # Model configs from env
        if api_key := os.getenv("ANTHROPIC_API_KEY"):
            models = data.setdefault("models", {})
            for mid in ["claude-sonnet-4-20250514", "claude-haiku-4-20250514"]:
                models[mid] = {
                    "api_key": api_key,
                    "base_url": "https://api.anthropic.com/v1/",
                }

        if api_key := os.getenv("OPENAI_API_KEY"):
            models = data.setdefault("models", {})
            for mid in ["gpt-4o", "gpt-4o-mini", "o3-mini"]:
                models[mid] = {"api_key": api_key}

        if api_key := os.getenv("DEEPSEEK_API_KEY"):
            models = data.setdefault("models", {})
            for mid in ["deepseek-chat", "deepseek-reasoner"]:
                models[mid] = {
                    "api_key": api_key,
                    "base_url": "https://api.deepseek.com/v1",
                }

        if default_model := (os.getenv("MODEL") or os.getenv("DEFAULT_MODEL")):
            data["default_model"] = default_model

        return cls(name="environment", path=None, data=data, source="env")

    def get(self, key: str, default: Any = None) -> Any:
        """Get a nested value using dot notation."""
        parts = key.split(".")
        current = self.data
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
                if current is None:
                    return default
            else:
                return default
        return current


class CascadingConfig:
    """Manages multiple configuration layers with proper override behavior."""

    def __init__(self, workspace: Path | None = None):
        self.workspace = workspace
        self.layers: list[ConfigLayer] = []
        self._merged: dict[str, Any] = {}
        self._load_layers()

    def _load_layers(self):
        """Load all config layers in priority order (lowest first)."""
        self.layers = []

        # 1. User defaults (~/.ic/config.toml)
        user_config = Path.home() / ".ic" / "config.toml"
        self.layers.append(ConfigLayer.from_file(user_config))

        # 2. Project config (.instant-coffee/config.toml)
        if self.workspace:
            project_config = self.workspace / ".instant-coffee" / "config.toml"
            self.layers.append(ConfigLayer.from_file(project_config))

            # 3. Local config (.instant-coffee/config.local.toml)
            local_config = self.workspace / ".instant-coffee" / "config.local.toml"
            self.layers.append(ConfigLayer.from_file(local_config))

        # 4. Environment variables (highest priority)
        self.layers.append(ConfigLayer.from_env())

        # Merge layers (later layers override earlier ones)
        self._merged = self._merge_layers()

    def _merge_layers(self) -> dict[str, Any]:
        """Merge all layers into a single config dict."""
        merged: dict[str, Any] = {}

        for layer in self.layers:
            self._deep_merge(merged, layer.data)

        return merged

    @staticmethod
    def _deep_merge(base: dict, updates: dict):
        """Deep merge two dicts."""
        for key, value in updates.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                CascadingConfig._deep_merge(base[key], value)
            else:
                base[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Get a config value using dot notation."""
        parts = key.split(".")
        current = self._merged
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
                if current is None:
                    return default
            else:
                return default
        return current

    def get_model_config(self, name: str) -> dict[str, Any]:
        """Get configuration for a specific model."""
        models = self.get("models", {})
        if name in models:
            return models[name]

        # Check for model alias
        aliases = self.get("model_aliases", {})
        if name in aliases:
            return models.get(aliases[name], {})

        return {}

    def list_models(self) -> list[str]:
        """List all available model names."""
        models = self.get("models", {})
        return list(models.keys())

    def get_sources(self, key: str) -> list[str]:
        """Find which config layers contributed to a key."""
        sources = []
        for layer in reversed(self.layers):  # Check highest priority first
            value = layer.get(key)
            if value is not None:
                sources.append(f"{layer.name} ({layer.source})")
        return sources

    def reload(self):
        """Reload all configuration layers."""
        self._load_layers()


def get_cascading_config(workspace: Path | None = None) -> CascadingConfig:
    """Get the cascading configuration for a workspace."""
    return CascadingConfig(workspace)
