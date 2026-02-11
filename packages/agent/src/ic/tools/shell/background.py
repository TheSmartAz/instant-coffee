"""Background task manager for persistent shell processes.

Manages long-running commands like npm run dev, python server.py, etc.
Tasks can be started, stopped, and their output streamed in real-time.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable


class TaskStatus(Enum):
    """Status of a background task."""
    STARTING = "starting"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"


@dataclass
class BackgroundTask:
    """A background shell task."""
    id: str
    command: str
    workspace: Path | None
    status: TaskStatus = TaskStatus.STARTING
    pid: int | None = None
    exit_code: int | None = None
    created_at: datetime = field(default_factory=datetime.now)
    output_buffer: list[str] = field(default_factory=list)
    max_buffer_lines: int = 1000

    # Async process reference
    proc: asyncio.subprocess.Process | None = None

    def add_output(self, line: str):
        """Add output line to buffer (with truncation)."""
        self.output_buffer.append(line)
        if len(self.output_buffer) > self.max_buffer_lines:
            self.output_buffer = self.output_buffer[-self.max_buffer_lines:]

    def get_output(self, since: int | None = None) -> list[str]:
        """Get output lines, optionally after a specific index."""
        if since is None:
            return self.output_buffer.copy()
        return self.output_buffer[since:]

    def get_output_text(self) -> str:
        """Get all output as a single string."""
        return "\n".join(self.output_buffer)


class BackgroundTaskManager:
    """
    Manages background shell tasks.

    Tasks run independently of the agent loop and can be polled for output.
    This enables commands like `npm run dev` that produce continuous output.
    """

    def __init__(self):
        self._tasks: dict[str, BackgroundTask] = {}
        self._output_tasks: dict[str, asyncio.Task] = {}
        # Lifecycle callbacks (set by orchestrator to emit events)
        self.on_task_started: Callable[[str, str], None] | None = None
        self.on_task_completed: Callable[[str, str, int | None], None] | None = None
        self.on_task_failed: Callable[[str, str], None] | None = None

    async def start(
        self,
        command: str,
        workspace: Path | None = None,
    ) -> BackgroundTask:
        """Start a background task and return its ID."""
        task_id = uuid.uuid4().hex[:8]

        task = BackgroundTask(
            id=task_id,
            command=command,
            workspace=workspace,
        )

        # Create output reader task
        reader = asyncio.create_task(
            self._read_output(task)
        )
        self._output_tasks[task_id] = reader
        self._tasks[task_id] = task

        return task

    async def _read_output(self, task: BackgroundTask):
        """Read output from the task process."""
        cwd = str(task.workspace) if task.workspace else None

        try:
            task.proc = await asyncio.create_subprocess_shell(
                task.command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,  # Combine stderr
                cwd=cwd,
            )

            task.pid = task.proc.pid
            task.status = TaskStatus.RUNNING

            if self.on_task_started:
                try:
                    self.on_task_started(task.id, task.command)
                except Exception:
                    pass

            # Read line by line
            while True:
                line = await task.proc.stdout.readline()
                if not line:
                    break

                text = line.decode("utf-8", errors="replace").rstrip("\n\r")
                task.add_output(text)

            # Process ended
            returncode = await task.proc.wait()
            task.exit_code = returncode

            if returncode == 0:
                task.status = TaskStatus.STOPPED
                if self.on_task_completed:
                    try:
                        self.on_task_completed(task.id, task.get_output_text(), returncode)
                    except Exception:
                        pass
            else:
                task.status = TaskStatus.FAILED
                if self.on_task_failed:
                    try:
                        self.on_task_failed(task.id, f"Exit code {returncode}: {task.get_output_text()[-500:]}")
                    except Exception:
                        pass

        except Exception as e:
            task.add_output(f"Task error: {e}")
            task.status = TaskStatus.FAILED
            if self.on_task_failed:
                try:
                    self.on_task_failed(task.id, str(e))
                except Exception:
                    pass
        finally:
            task.proc = None

    def stop(self, task_id: str) -> bool:
        """Stop a running task. Returns True if successful."""
        task = self._tasks.get(task_id)
        if not task:
            return False

        if task.proc and task.status == TaskStatus.RUNNING:
            task.proc.terminate()
            task.status = TaskStatus.STOPPED
            return True

        return False

    def get(self, task_id: str) -> BackgroundTask | None:
        """Get a task by ID."""
        return self._tasks.get(task_id)

    def list_tasks(self) -> list[BackgroundTask]:
        """List all tasks."""
        return list(self._tasks.values())

    def cleanup(self, task_id: str):
        """Remove a stopped task from the manager."""
        if task_id in self._tasks:
            del self._tasks[task_id]
        if task_id in self._output_tasks:
            reader = self._output_tasks.pop(task_id)
            if not reader.done():
                reader.cancel()

    def cleanup_stopped(self):
        """Remove all stopped tasks."""
        to_remove = [
            tid for tid, task in self._tasks.items()
            if task.status in (TaskStatus.STOPPED, TaskStatus.FAILED)
        ]
        for tid in to_remove:
            self.cleanup(tid)
        return len(to_remove)


# Global singleton
_global_manager: BackgroundTaskManager | None = None


def get_task_manager() -> BackgroundTaskManager:
    """Get the global background task manager."""
    global _global_manager
    if _global_manager is None:
        _global_manager = BackgroundTaskManager()
    return _global_manager
