"""Todo tool - task tracking for the agent."""

from __future__ import annotations

import json
from typing import Any

from ic.tools.base import BaseTool, ToolParam, ToolResult


class Todo(BaseTool):
    name = "todo"
    description = "Manage a task list. Actions: add, list, update, remove."
    parameters = [
        ToolParam(name="action", description="Action to perform", enum=["add", "list", "update", "remove"]),
        ToolParam(name="task", description="Task description (for add)", required=False),
        ToolParam(name="task_id", type="integer", description="Task ID (for update/remove)", required=False),
        ToolParam(name="status", description="New status (for update)", required=False, enum=["pending", "in_progress", "done"]),
    ]

    _tasks: list[dict[str, Any]] = []
    _next_id: int = 1

    def __init__(self):
        self._tasks = []
        self._next_id = 1

    async def execute(self, **kwargs: Any) -> ToolResult:
        action = kwargs["action"]
        if action == "add":
            task_desc = kwargs.get("task", "")
            if not task_desc:
                return ToolResult(error="Task description required", is_error=True)
            task = {"id": self._next_id, "task": task_desc, "status": "pending"}
            self._tasks.append(task)
            self._next_id += 1
            return ToolResult(output=f"Added task #{task['id']}: {task_desc}")

        elif action == "list":
            if not self._tasks:
                return ToolResult(output="No tasks.")
            lines = []
            for t in self._tasks:
                icon = {"pending": "○", "in_progress": "◑", "done": "●"}.get(t["status"], "?")
                lines.append(f"  {icon} #{t['id']} [{t['status']}] {t['task']}")
            return ToolResult(output="\n".join(lines))

        elif action == "update":
            tid = int(kwargs.get("task_id", 0))
            status = kwargs.get("status", "")
            task = next((t for t in self._tasks if t["id"] == tid), None)
            if not task:
                return ToolResult(error=f"Task #{tid} not found", is_error=True)
            task["status"] = status
            return ToolResult(output=f"Updated task #{tid} → {status}")

        elif action == "remove":
            tid = int(kwargs.get("task_id", 0))
            self._tasks = [t for t in self._tasks if t["id"] != tid]
            return ToolResult(output=f"Removed task #{tid}")

        return ToolResult(error=f"Unknown action: {action}", is_error=True)
