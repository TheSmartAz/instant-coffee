"""Configuration management for IC agent.

Model-centric config: each entry is a model, not a provider.
Same api_key/base_url can be shared across multiple models.
Config stored in ~/.ic/config.toml, with .env fallback.
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


# Known models available through DMXAPI proxy (same key, same base_url)
DMXAPI_MODELS = [
    ("kimi-k2.5", 256000),
    ("DeepSeek-V3.2", 128000),
    ("gpt-5-mini", 128000),
    ("glm-4.7", 202752),
    ("qwen3-max-2026-01-23", 131072),
    ("MiniMax-M2.1", 204800),
    ("hunyuan-2.0-instruct-20251111", 256000),
    ("gemini-3-flash-preview", 128000),
    ("grok-code-fast-1", 128000),
]

DMXAPI_BASE_URL = "https://www.dmxapi.cn/v1"


@dataclass
class ModelConfig:
    """Configuration for a model. name is the user-facing alias."""

    name: str
    model: str = ""          # actual model ID sent to API; defaults to name
    api_key: str = ""
    base_url: str | None = None
    max_tokens: int = 32768
    temperature: float = 0.0

    def __post_init__(self):
        if not self.model:
            self.model = self.name


@dataclass
class AgentConfig:
    """Configuration for an agent."""

    name: str = "main"
    system_prompt: str = ""
    model: str = "default"
    tools: list[str] = field(default_factory=list)
    max_turns: int = 50


DEFAULT_TOOLS_MAIN = [
    "ic.tools.file:ReadFile",
    "ic.tools.file:WriteFile",
    "ic.tools.file:EditFile",
    "ic.tools.file:GlobFiles",
    "ic.tools.file:GrepFiles",
    "ic.tools.shell:Shell",
    "ic.tools.think:Think",
    "ic.tools.todo:Todo",
    "ic.tools.ask:AskUser",
    "ic.tools.subagent:CreateSubAgent",
]

DEFAULT_TOOLS_SUB = [
    "ic.tools.file:ReadFile",
    "ic.tools.file:WriteFile",
    "ic.tools.file:EditFile",
    "ic.tools.file:GlobFiles",
    "ic.tools.file:GrepFiles",
    "ic.tools.shell:Shell",
    "ic.tools.think:Think",
]


@dataclass
class Config:
    """Global configuration."""

    data_dir: Path = field(default_factory=lambda: Path.home() / ".ic")
    models: dict[str, ModelConfig] = field(default_factory=dict)
    agents: dict[str, AgentConfig] = field(default_factory=dict)
    default_model: str = ""

    def __post_init__(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)

    @property
    def config_path(self) -> Path:
        return self.data_dir / "config.toml"

    # ── Loading ──────────────────────────────────────────────

    @classmethod
    def load(cls) -> Config:
        """Load config: TOML > .env > environment variables."""
        cfg = cls()
        cfg._load_dotenv()
        if cfg.config_path.exists():
            cfg._load_from_toml()
        else:
            cfg._load_from_env()
        cfg._ensure_agents()
        return cfg

    def _load_dotenv(self):
        """Load .env files into os.environ (won't override existing).

        Searches: cwd, parent dirs (up to 5 levels), and ~/.ic/.env.
        """
        found: list[Path] = []

        # Walk up from cwd looking for .env
        d = Path.cwd()
        for _ in range(6):
            candidate = d / ".env"
            if candidate.exists():
                found.append(candidate)
            # Also check packages/backend/.env at this level
            backend_env = d / "packages" / "backend" / ".env"
            if backend_env.exists() and backend_env not in found:
                found.append(backend_env)
            parent = d.parent
            if parent == d:
                break
            d = parent

        # Also check ~/.ic/.env
        ic_env = self.data_dir / ".env"
        if ic_env.exists() and ic_env not in found:
            found.append(ic_env)

        for p in found:
            self._parse_dotenv(p)

    @staticmethod
    def _parse_dotenv(path: Path):
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip().strip("'\"")
            if key and key not in os.environ:
                os.environ[key] = value

    def _load_from_toml(self):
        """Load from ~/.ic/config.toml."""
        data = tomllib.loads(self.config_path.read_bytes().decode())
        self.default_model = data.get("default_model", "")

        for name, m in data.get("models", {}).items():
            self.models[name] = ModelConfig(
                name=name,
                model=m.get("model", ""),
                api_key=m.get("api_key", ""),
                base_url=m.get("base_url"),
                max_tokens=m.get("max_tokens", 4096),
                temperature=m.get("temperature", 0.0),
            )

        if not self.default_model and self.models:
            self.default_model = next(iter(self.models))

        for name, a in data.get("agents", {}).items():
            self.agents[name] = AgentConfig(
                name=name,
                model=a.get("model", self.default_model),
                max_turns=a.get("max_turns", 50 if name == "main" else 30),
            )

    def _load_from_env(self):
        """Auto-detect models from env vars. Model-centric: each model is its own entry."""
        # DMXAPI key → register all known DMXAPI models
        dmx_key = (
            os.environ.get("DMXAPI_API_KEY")
            or os.environ.get("DMX_API_KEY")
            or os.environ.get("DEFAULT_KEY")
        )
        if dmx_key:
            base = os.environ.get("DEFAULT_BASE_URL", DMXAPI_BASE_URL)
            for model_id, max_tok in DMXAPI_MODELS:
                self.models[model_id] = ModelConfig(
                    name=model_id, api_key=dmx_key, base_url=base, max_tokens=max_tok,
                )

        # OpenAI key → register common OpenAI models
        if oai_key := os.environ.get("OPENAI_API_KEY"):
            for mid in ["gpt-4o", "gpt-4o-mini", "o3-mini"]:
                if mid not in self.models:
                    self.models[mid] = ModelConfig(name=mid, api_key=oai_key)

        # Anthropic key
        if ant_key := os.environ.get("ANTHROPIC_API_KEY"):
            for mid in ["claude-sonnet-4-20250514", "claude-haiku-4-20250514"]:
                if mid not in self.models:
                    self.models[mid] = ModelConfig(
                        name=mid, api_key=ant_key,
                        base_url="https://api.anthropic.com/v1/",
                    )

        # DeepSeek key
        if ds_key := os.environ.get("DEEPSEEK_API_KEY"):
            for mid in ["deepseek-chat", "deepseek-reasoner"]:
                if mid not in self.models:
                    self.models[mid] = ModelConfig(
                        name=mid, api_key=ds_key,
                        base_url="https://api.deepseek.com/v1",
                    )

        # Pick default
        if self.models and not self.default_model:
            # Prefer the MODEL env var, then first available
            env_model = os.environ.get("MODEL") or os.environ.get("DEFAULT_MODEL")
            if env_model and env_model in self.models:
                self.default_model = env_model
            else:
                self.default_model = next(iter(self.models))

    # ── Agents ───────────────────────────────────────────────

    def _ensure_agents(self):
        if "main" not in self.agents:
            self.agents["main"] = AgentConfig(
                name="main",
                system_prompt="You are an expert coding assistant.",
                model=self.default_model,
                tools=DEFAULT_TOOLS_MAIN,
                max_turns=50,
            )
        else:
            a = self.agents["main"]
            if not a.tools:
                a.tools = DEFAULT_TOOLS_MAIN
            if not a.system_prompt:
                a.system_prompt = "You are an expert coding assistant."

        if "sub" not in self.agents:
            self.agents["sub"] = AgentConfig(
                name="sub",
                system_prompt="You are a focused sub-agent. Complete the assigned task efficiently.",
                model=self.default_model,
                tools=DEFAULT_TOOLS_SUB,
                max_turns=30,
            )
        else:
            a = self.agents["sub"]
            if not a.tools:
                a.tools = DEFAULT_TOOLS_SUB
            if not a.system_prompt:
                a.system_prompt = "You are a focused sub-agent. Complete the assigned task efficiently."

    # ── Accessors ────────────────────────────────────────────

    def get_model(self, name: str | None = None) -> ModelConfig:
        name = name or self.default_model
        if name not in self.models:
            raise ValueError(f"Model '{name}' not found. Available: {list(self.models.keys())}")
        return self.models[name]

    def save_model(self, name: str, api_key: str, base_url: str, model: str):
        """Add/update a model and persist to config.toml."""
        self.models[name] = ModelConfig(
            name=name, model=model or name, api_key=api_key, base_url=base_url or None,
        )
        if not self.default_model:
            self.default_model = name
        self._write_toml()

    def _write_toml(self):
        lines = [f'default_model = "{self.default_model}"', ""]
        for name, m in self.models.items():
            # Quote names with special chars for valid TOML
            key = f'"{name}"' if any(c in name for c in ".-/") else name
            lines.append(f"[models.{key}]")
            lines.append(f'api_key = "{m.api_key}"')
            if m.base_url:
                lines.append(f'base_url = "{m.base_url}"')
            if m.model != m.name:
                lines.append(f'model = "{m.model}"')
            lines.append(f"max_tokens = {m.max_tokens}")
            lines.append(f"temperature = {m.temperature}")
            lines.append("")
        self.config_path.write_text("\n".join(lines))


# ── Setup wizard ─────────────────────────────────────────────

def run_setup(config: Config) -> bool:
    """Interactive first-time setup. Returns True if a model was configured."""
    print("\n  IC Agent - First Time Setup")
    print("  " + "=" * 35)
    print()
    print("  No models configured. Let's add one.")
    print()

    model = input("  Model ID (e.g. gpt-4o, deepseek-chat, kimi-k2.5): ").strip()
    if not model:
        model = "gpt-4o"

    api_key = input("  API Key: ").strip()
    if not api_key:
        print("  API key is required.")
        return False

    base_url = input("  Base URL (Enter for OpenAI default): ").strip()

    name = input(f"  Short name [{model}]: ").strip() or model

    config.save_model(name, api_key, base_url, model)
    print(f"\n  Saved to {config.config_path}")
    print(f"  Default model: {name}")
    print()
    return True
