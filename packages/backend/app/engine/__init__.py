"""Engine integration — bridges the agent Engine into the web backend.

Imports are lazy to avoid hard dependency on the ``ic`` agent package.
The engine feature is gated behind ``USE_ENGINE=true`` in settings.
"""

from .registry import engine_registry
from .web_user_io import WebUserIO

__all__ = [
    "EngineOrchestrator",
    "WebUserIO",
    "engine_registry",
]


def __getattr__(name: str):
    if name == "EngineOrchestrator":
        from .orchestrator import EngineOrchestrator

        return EngineOrchestrator
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
