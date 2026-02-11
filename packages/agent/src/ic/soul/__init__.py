"""Soul package - agent engine core."""

from ic.soul.context import Context
from ic.soul.context_injector import ContextInjector, ContextConfig, InjectedContext
from ic.soul.engine import Engine
from ic.soul.skills import SkillLoader, Skill, SkillMetadata
from ic.soul.toolset import Toolset

__all__ = [
    "Engine",
    "Context",
    "Toolset",
    "ContextInjector",
    "ContextConfig",
    "InjectedContext",
    "SkillLoader",
    "Skill",
    "SkillMetadata",
]
