from __future__ import annotations

from typing import Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .parallel import ParallelExecutor


class ExecutorManager:
    """Manage active ParallelExecutor instances."""

    _instance: Optional["ExecutorManager"] = None

    def __init__(self) -> None:
        self._executors: Dict[str, ParallelExecutor] = {}

    @classmethod
    def get_instance(cls) -> "ExecutorManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, plan_id: str, executor: "ParallelExecutor") -> None:
        self._executors[plan_id] = executor

    def unregister(self, plan_id: str) -> None:
        self._executors.pop(plan_id, None)

    def get(self, plan_id: str) -> Optional["ParallelExecutor"]:
        return self._executors.get(plan_id)

    def abort(self, plan_id: str) -> bool:
        executor = self.get(plan_id)
        if executor is None:
            return False
        executor.abort()
        self.unregister(plan_id)
        return True


__all__ = ["ExecutorManager"]
