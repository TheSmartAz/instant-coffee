"""Registry — in-memory registry of active EngineOrchestrator instances.

Used to route user answers back to the correct pending engine when
a new chat message arrives for a session that has a blocked ``ask_user``.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .orchestrator import EngineOrchestrator

logger = logging.getLogger(__name__)


class _EngineRegistry:
    """Thread-safe (single-process) registry of active engine instances."""

    def __init__(self) -> None:
        self._active: dict[str, "EngineOrchestrator"] = {}

    def register(self, session_id: str, orchestrator: "EngineOrchestrator") -> None:
        self._active[session_id] = orchestrator
        logger.debug("Registered engine for session %s", session_id)

    def unregister(self, session_id: str) -> None:
        removed = self._active.pop(session_id, None)
        if removed:
            logger.debug("Unregistered engine for session %s", session_id)

    def get(self, session_id: str) -> Optional["EngineOrchestrator"]:
        return self._active.get(session_id)

    def has_pending_question(self, session_id: str) -> bool:
        orch = self._active.get(session_id)
        if orch is None:
            return False
        return orch.has_pending_question


engine_registry = _EngineRegistry()
