"""Background task service for managing persistent shell tasks.

This service provides a web API interface to the agent's background task manager,
allowing the frontend to list, start, stop, and poll output from background tasks.
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session as DbSession

from ..db.models import Session as SessionModel


class TaskStatus(str, Enum):
    """Status of a background task."""
    STARTING = "starting"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"


@dataclass
class BackgroundTaskInfo:
    """Serializable info about a background task."""
    id: str
    command: str
    status: str
    pid: int | None
    exit_code: int | None
    created_at: str
    output_lines: int
    output_preview: list[str]  # Last 20 lines

    @classmethod
    def from_task(cls, task) -> BackgroundTaskInfo:
        """Create from BackgroundTask object."""
        return cls(
            id=task.id,
            command=task.command,
            status=task.status.value,
            pid=task.pid,
            exit_code=task.exit_code,
            created_at=task.created_at.isoformat(),
            output_lines=len(task.output_buffer),
            output_preview=task.output_buffer[-20:],
        )


class BackgroundTaskService:
    """Service for managing background tasks across sessions.

    Note: This is a thin wrapper around the agent's BackgroundTaskManager.
    The actual task processes are managed by the agent engine.
    """

    def __init__(self, db: DbSession):
        self.db = db
        # Reference to agent's task manager will be set when engine starts
        self._task_manager = None

    def set_task_manager(self, manager):
        """Set reference to the agent's task manager."""
        self._task_manager = manager

    def list_tasks(self, session_id: str) -> list[dict]:
        """List all background tasks for a session."""
        if self._task_manager is None:
            return []

        tasks = []
        for task in self._task_manager.list_tasks():
            # Filter by session (would need to add session_id to BackgroundTask)
            # For now, return all tasks
            tasks.append(asdict(BackgroundTaskInfo.from_task(task)))

        return tasks

    def get_task(self, session_id: str, task_id: str) -> dict | None:
        """Get a specific task."""
        if self._task_manager is None:
            return None

        task = self._task_manager.get(task_id)
        if task:
            return asdict(BackgroundTaskInfo.from_task(task))
        return None

    def stop_task(self, session_id: str, task_id: str) -> bool:
        """Stop a running task."""
        if self._task_manager is None:
            return False
        return self._task_manager.stop(task_id)

    def get_task_output(self, session_id: str, task_id: str, since: int | None = None) -> dict:
        """Get task output."""
        if self._task_manager is None:
            return {"error": "Task manager not available"}

        task = self._task_manager.get(task_id)
        if not task:
            return {"error": "Task not found"}

        output_lines = task.get_output(since)
        return {
            "task_id": task_id,
            "status": task.status.value,
            "output": "\n".join(output_lines),
            "output_lines": len(output_lines),
        }


# Global task manager reference (will be set by engine)
_global_task_manager = None


def get_global_task_manager():
    """Get the global background task manager."""
    return _global_task_manager


def set_global_task_manager(manager):
    """Set the global background task manager."""
    global _global_task_manager
    _global_task_manager = manager
