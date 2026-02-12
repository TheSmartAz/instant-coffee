"""Configuration management for IC agent.

Model-centric config: each entry is a model, not a provider.
Same api_key/base_url can be shared across multiple models.

Config loading priority (highest first):
1. Environment variables
2. .instant-coffee/config.local.toml (git-ignored, per-machine)
3. .instant-coffee/config.toml (project-specific)
4. ~/.ic/config.toml (user defaults)
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
    ("MiniMax-M2.5", 204800),
    ("glm-5", 202752),
    ("kimi-k2.5", 256000),
    ("DeepSeek-V3.2", 128000),
    ("gpt-5-mini", 128000),
    ("qwen3-max-2026-01-23", 131072),
    ("gemini-3-flash-preview", 128000),
    ("grok-code-fast-1", 128000),
]

DMXAPI_BASE_URL = "https://www.dmxapi.cn/v1"


# Per-model token pricing (USD per 1M tokens): (input, output)
# Source: provider pricing pages as of 2025-06
MODEL_PRICING: dict[str, tuple[float, float]] = {
    # DMXAPI / Chinese models
    "MiniMax-M2.5":                 (1.00, 4.00),
    "kimi-k2.5":                    (2.00, 8.00),
    "DeepSeek-V3.2":                (0.27, 1.10),
    "gpt-5-mini":                   (1.50, 6.00),
    "glm-5":                      (1.00, 4.00),
    "qwen3-max-2026-01-23":         (1.60, 6.40),
    "gemini-3-flash-preview":       (0.15, 0.60),
    "grok-code-fast-1":             (2.00, 10.00),
}


@dataclass
class ModelConfig:
    """Configuration for a model. name is the user-facing alias."""

    name: str
    model: str = ""          # actual model ID sent to API; defaults to name
    api_key: str = ""
    base_url: str | None = None
    max_tokens: int = 32768
    temperature: float = 0.0
    timeout: float = 120.0   # timeout in seconds for API requests

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
    "ic.tools.file:MultiEditFile",
    "ic.tools.file:GlobFiles",
    "ic.tools.file:GrepFiles",
    "ic.tools.shell:Shell",
    "ic.tools.think:Think",
    "ic.tools.todo:Todo",
    "ic.tools.ask:AskUser",
    "ic.tools.subagent:CreateSubAgent",
    "ic.tools.subagent:CreateParallelSubAgents",
    "ic.tools.web:WebSearch",
    "ic.tools.web:WebFetch",
    "ic.tools.skill:ExecuteSkill",
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
class ModelPointers:
    """Model pointers for different purposes. Each points to a model name in Config.models."""

    main: str = ""      # Primary model for main agent conversations
    sub: str = ""       # Model for sub-agents (can be cheaper)
    compact: str = ""   # Model for context summarization (should be fast & cheap)

    def resolve(self, role: str, fallback: str = "") -> str:
        """Get the model name for a given role, falling back to main or default."""
        value = getattr(self, role, "") if role in ("main", "sub", "compact") else ""
        return value or self.main or fallback


@dataclass
class Config:
    """Global configuration."""

    data_dir: Path = field(default_factory=lambda: Path.home() / ".ic")
    models: dict[str, ModelConfig] = field(default_factory=dict)
    agents: dict[str, AgentConfig] = field(default_factory=dict)
    default_model: str = ""
    model_pointers: ModelPointers = field(default_factory=ModelPointers)

    def __post_init__(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)

    @property
    def config_path(self) -> Path:
        return self.data_dir / "config.toml"

    # ── Loading ──────────────────────────────────────────────

    @classmethod
    def load(cls, workspace: "Path | None" = None) -> Config:
        """Load config: cascade layers > TOML > .env > environment variables.

        When workspace is provided, uses CascadingConfig for 4-layer priority:
        env > config.local.toml > config.toml > ~/.ic/config.toml
        """
        cfg = cls()
        cfg._load_dotenv()

        # Try cascading config first (supports project-level overrides)
        from ic.cascade import CascadingConfig
        cascade = CascadingConfig(workspace=workspace)
        merged_models = cascade.get("models", {})

        if merged_models:
            cfg._apply_cascade(cascade)
        elif cfg.config_path.exists():
            cfg._load_from_toml()
        else:
            cfg._load_from_env()

        cfg._ensure_agents()
        return cfg

    def _apply_cascade(self, cascade: Any):
        """Apply merged CascadingConfig data to this Config."""
        merged_models = cascade.get("models", {})
        for name, m in merged_models.items():
            self.models[name] = ModelConfig(
                name=name,
                model=m.get("model", ""),
                api_key=m.get("api_key", ""),
                base_url=m.get("base_url"),
                max_tokens=m.get("max_tokens", 32768),
                temperature=m.get("temperature", 0.0),
                timeout=self._parse_positive_float(m.get("timeout"), 120.0),
            )

        self.default_model = cascade.get("default_model", "")
        if not self.default_model and self.models:
            self.default_model = next(iter(self.models))

        # Load model pointers
        ptrs = cascade.get("model_pointers", {}) or {}
        self.model_pointers = ModelPointers(
            main=ptrs.get("main", ""),
            sub=ptrs.get("sub", ""),
            compact=ptrs.get("compact", ""),
        )
        self._auto_select_pointers()

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
    def _parse_positive_float(value: Any, default: float) -> float:
        """Parse a positive float with safe fallback."""
        try:
            parsed = float(value)
            if parsed > 0:
                return parsed
        except (TypeError, ValueError):
            pass
        return default

    def _env_model_timeout(self) -> float:
        """Get model timeout from env with sensible defaults."""
        raw = os.environ.get("MODEL_TIMEOUT") or os.environ.get("LLM_TIMEOUT")
        return self._parse_positive_float(raw, 120.0)

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
                timeout=self._parse_positive_float(m.get("timeout"), 120.0),
            )

        if not self.default_model and self.models:
            self.default_model = next(iter(self.models))

        # Load model pointers
        ptrs = data.get("model_pointers", {})
        self.model_pointers = ModelPointers(
            main=ptrs.get("main", ""),
            sub=ptrs.get("sub", ""),
            compact=ptrs.get("compact", ""),
        )

        for name, a in data.get("agents", {}).items():
            self.agents[name] = AgentConfig(
                name=name,
                model=a.get("model", self.default_model),
                max_turns=a.get("max_turns", 50 if name == "main" else 30),
            )

    def _load_from_env(self):
        """Auto-detect models from env vars. Model-centric: each model is its own entry."""
        model_timeout = self._env_model_timeout()

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
                    name=model_id,
                    api_key=dmx_key,
                    base_url=base,
                    max_tokens=max_tok,
                    timeout=model_timeout,
                )

        # OpenAI key → register common OpenAI models
        if oai_key := os.environ.get("OPENAI_API_KEY"):
            for mid in ["gpt-4o", "gpt-4o-mini", "o3-mini"]:
                if mid not in self.models:
                    self.models[mid] = ModelConfig(
                        name=mid, api_key=oai_key, timeout=model_timeout
                    )

        # Anthropic key
        if ant_key := os.environ.get("ANTHROPIC_API_KEY"):
            for mid in ["claude-sonnet-4-20250514", "claude-haiku-4-20250514"]:
                if mid not in self.models:
                    self.models[mid] = ModelConfig(
                        name=mid, api_key=ant_key,
                        base_url="https://api.anthropic.com/v1/",
                        timeout=model_timeout,
                    )

        # DeepSeek key
        if ds_key := os.environ.get("DEEPSEEK_API_KEY"):
            for mid in ["deepseek-chat", "deepseek-reasoner"]:
                if mid not in self.models:
                    self.models[mid] = ModelConfig(
                        name=mid, api_key=ds_key,
                        base_url="https://api.deepseek.com/v1",
                        timeout=model_timeout,
                    )

        # Pick default
        if self.models and not self.default_model:
            # Prefer the MODEL env var, then first available
            env_model = os.environ.get("MODEL") or os.environ.get("DEFAULT_MODEL")
            if env_model and env_model in self.models:
                self.default_model = env_model
            else:
                self.default_model = next(iter(self.models))

        # Auto-select model pointers if not set
        self._auto_select_pointers()

    # ── Model Pointers ─────────────────────────────────────────

    def _auto_select_pointers(self):
        """Auto-select cheap models for sub/compact if not explicitly set."""
        if not self.models:
            return

        # main always defaults to default_model
        if not self.model_pointers.main:
            self.model_pointers.main = self.default_model

        # For compact/sub, prefer the cheapest available model
        if not self.model_pointers.compact or not self.model_pointers.sub:
            cheapest = self._find_cheapest_model()
            if not self.model_pointers.compact:
                self.model_pointers.compact = cheapest or self.default_model
            if not self.model_pointers.sub:
                self.model_pointers.sub = cheapest or self.default_model

    def _find_cheapest_model(self) -> str:
        """Find the cheapest available model by input token price."""
        best_name = ""
        best_price = float("inf")
        for name in self.models:
            pricing = MODEL_PRICING.get(name)
            if pricing and pricing[0] < best_price:
                best_price = pricing[0]
                best_name = name
        return best_name

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

    def save_model(
        self,
        name: str,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float | str | None = None,
    ):
        """Add/update a model and persist to config.toml."""
        existing_timeout = self.models[name].timeout if name in self.models else 120.0
        model_timeout = (
            self._parse_positive_float(timeout, 120.0)
            if timeout is not None
            else existing_timeout
        )
        self.models[name] = ModelConfig(
            name=name,
            model=model or name,
            api_key=api_key,
            base_url=base_url or None,
            timeout=model_timeout,
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
            lines.append(f"timeout = {m.timeout}")
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
    timeout_input = input("  Timeout seconds [120]: ").strip()
    timeout = Config._parse_positive_float(timeout_input, 120.0)

    name = input(f"  Short name [{model}]: ").strip() or model

    config.save_model(name, api_key, base_url, model, timeout=timeout)
    print(f"\n  Saved to {config.config_path}")
    print(f"  Default model: {name}")
    print()
    return True
