from __future__ import annotations

from typing import Optional

from ..config import get_settings
from .anthropic_planner import AnthropicPlanner
from .base import BasePlanner
from .openai_planner import OpenAIPlanner


class PlannerFactory:
    @staticmethod
    def create(provider: Optional[str] = None) -> BasePlanner:
        settings = get_settings()
        resolved = (provider or settings.planner_provider or "openai").lower()

        if resolved == "openai":
            return OpenAIPlanner(model=settings.planner_model)
        if resolved == "anthropic":
            return AnthropicPlanner(model=settings.planner_model)

        raise ValueError(f"Unknown planner provider: {resolved}")


__all__ = ["PlannerFactory"]
