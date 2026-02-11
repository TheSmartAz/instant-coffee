"""Shell command execution tool with background task support and safety guard."""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any, Callable, Awaitable

from ic.tools.base import (
    BaseTool,
    ToolParam,
    ToolResult,
    ToolCompleteEvent,
    ToolProgressEvent,
)
from ic.tools.shell.background import get_task_manager, BackgroundTaskManager


# Dangerous command patterns that should be blocked or require confirmation
DANGEROUS_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\brm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+|.*--force\s+).*(/|~|\$HOME|\.\.)"), "Recursive force delete on sensitive path"),
    (re.compile(r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*\s+(/\s|/\b)"), "Recursive delete on root"),
    (re.compile(r"\bgit\s+push\s+.*--force"), "Force push (may overwrite remote history)"),
    (re.compile(r"\bgit\s+reset\s+--hard"), "Hard reset (discards uncommitted changes)"),
    (re.compile(r"\bgit\s+clean\s+-[a-zA-Z]*f"), "Git clean force (deletes untracked files)"),
    (re.compile(r"\bchmod\s+-R\s+777\b"), "Recursive world-writable permissions"),
    (re.compile(r"\bcurl\s+.*\|\s*(sudo\s+)?bash"), "Piping remote script to shell"),
    (re.compile(r"\bwget\s+.*\|\s*(sudo\s+)?bash"), "Piping remote script to shell"),
    (re.compile(r"\bdd\s+.*of=/dev/"), "Direct disk write"),
    (re.compile(r"\bmkfs\b"), "Filesystem format"),
    (re.compile(r">\s*/dev/sd[a-z]"), "Direct device write"),
    (re.compile(r"\b:(){ :\|:& };:"), "Fork bomb"),
    (re.compile(r"\bDROP\s+(TABLE|DATABASE)\b", re.IGNORECASE), "SQL destructive operation"),
    (re.compile(r"\bTRUNCATE\s+TABLE\b", re.IGNORECASE), "SQL truncate"),
    (re.compile(r"\bsudo\s+rm\b"), "Sudo delete"),
    (re.compile(r"\bkillall\b"), "Kill all processes"),
    (re.compile(r"\bpkill\s+-9\b"), "Force kill processes"),
]


def check_command_safety(command: str) -> tuple[bool, str]:
    """Check if a command matches any dangerous patterns.

    Returns (is_safe, reason). If not safe, reason describes the risk.
    """
    for pattern, reason in DANGEROUS_PATTERNS:
        if pattern.search(command):
            return False, reason
    return True, ""


class Shell(BaseTool):
    """Execute shell commands with support for background tasks and streaming."""

    name = "shell"
    timeout_seconds = 120.0  # Shell commands get longer timeout
    description = (
        "Execute a shell command. "
        "Use background=True for long-running commands like 'npm run dev'. "
        "Use for git, npm, pip, and other CLI operations."
    )
    parameters = [
        ToolParam(name="command", description="The shell command to execute"),
        ToolParam(
            name="timeout",
            type="integer",
            description="Timeout in seconds for foreground commands (default 120)",
            required=False,
        ),
        ToolParam(
            name="background",
            description="Run as background task (for long-running processes)",
            required=False,
        ),
        ToolParam(
            name="task_action",
            description="Action on background tasks: list, stop, get_output",
            required=False,
        ),
        ToolParam(
            name="task_id",
            description="Task ID for task_action",
            required=False,
        ),
    ]

    def __init__(
        self,
        workspace: Path | None = None,
        on_before_execute: Callable[[str], Awaitable[bool] | bool] | None = None,
    ):
        super().__init__()
        self._workspace = workspace
        self._task_manager: BackgroundTaskManager | None = None
        # Callback invoked before executing a command.
        # Receives the command string. Return False to block execution.
        # In web app: can show a confirmation dialog.
        # In CLI: can prompt the user.
        # If None, dangerous commands are blocked outright.
        self._on_before_execute = on_before_execute

    @property
    def task_manager(self) -> BackgroundTaskManager:
        """Lazy load the task manager."""
        if self._task_manager is None:
            self._task_manager = get_task_manager()
        return self._task_manager

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute (simple interface)."""
        async for event in self.execute_stream(**kwargs):
            if isinstance(event, ToolCompleteEvent):
                return ToolResult(output=event.output)
        return ToolResult(output="")

    async def execute_stream(self, **kwargs):
        """Execute with streaming progress."""
        command = kwargs.get("command", "")
        task_action = kwargs.get("task_action")

        # Handle background task management actions (no safety check needed)
        if task_action:
            async for event in self._handle_task_action(kwargs):
                yield event
            return

        # Safety check for actual command execution
        is_safe, reason = check_command_safety(command)
        if not is_safe:
            if self._on_before_execute:
                # Let the callback decide (e.g. show confirmation dialog)
                allowed = self._on_before_execute(command)
                if asyncio.iscoroutine(allowed):
                    allowed = await allowed
                if not allowed:
                    yield ToolCompleteEvent(
                        output=f"Command blocked: {reason}. Command: {command}"
                    )
                    return
            else:
                # No callback configured — block dangerous commands outright
                yield ToolCompleteEvent(
                    output=f"Command blocked for safety: {reason}.\n"
                    f"Command: {command}\n"
                    f"If this is intentional, run it manually in your terminal."
                )
                return

        # Check if running in background mode
        background = kwargs.get("background", False)

        if background:
            async for event in self._start_background_task(command):
                yield event
        else:
            async for event in self._run_foreground_command(kwargs):
                yield event

    async def _handle_task_action(self, kwargs):
        """Handle actions on existing background tasks."""
        action = kwargs["task_action"]
        task_id = kwargs.get("task_id")

        if action == "list":
            tasks = self.task_manager.list_tasks()
            if not tasks:
                yield ToolCompleteEvent(output="No background tasks running.")
            else:
                lines = [
                    f"{t.id}: {t.command} - {t.status.value}"
                    for t in tasks
                ]
                yield ToolCompleteEvent(output="\n".join(lines))

        elif action == "stop":
            if not task_id:
                yield ToolCompleteEvent(output="Error: task_id required for stop action")
            else:
                if self.task_manager.stop(task_id):
                    yield ToolCompleteEvent(output=f"Task {task_id} stopped.")
                else:
                    yield ToolCompleteEvent(output=f"Task {task_id} not found or not running.")

        elif action == "get_output":
            if not task_id:
                yield ToolCompleteEvent(output="Error: task_id required for get_output action")
            else:
                task = self.task_manager.get(task_id)
                if not task:
                    yield ToolCompleteEvent(output=f"Task {task_id} not found.")
                else:
                    yield ToolCompleteEvent(
                        output=f"Task {task_id} ({task.status.value}):\n{task.get_output_text()}"
                    )

        else:
            yield ToolCompleteEvent(output=f"Unknown task_action: {action}")

    async def _start_background_task(self, command: str):
        """Start a background task."""
        task = await self.task_manager.start(command, self._workspace)
        yield ToolCompleteEvent(
            output=f"Started background task {task.id}: {command}\n"
            f"Use task_action='list' to see all tasks.\n"
            f"Use task_action='get_output' with task_id='{task.id}' to see output.\n"
            f"Use task_action='stop' with task_id='{task.id}' to stop it."
        )

    async def _run_foreground_command(self, kwargs):
        """Run a command in the foreground with timeout."""
        command = kwargs["command"]
        timeout = int(kwargs.get("timeout", 120))
        # Always use workspace as cwd if available (sandbox enforcement)
        cwd = str(self._workspace) if self._workspace else None

        try:
            await self._emit_progress(f"Running: {command[:50]}...", 10)

            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )

            await self._emit_progress("Command started...", 30)

            # Wait with timeout
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                yield ToolCompleteEvent(
                    output=f"Command timed out after {timeout}s and was killed."
                )
                return

            await self._emit_progress("Command completed.", 90)

            output_parts = []
            if stdout:
                output_parts.append(stdout.decode("utf-8", errors="replace"))
            if stderr:
                output_parts.append(f"STDERR:\n{stderr.decode('utf-8', errors='replace')}")

            output = "\n".join(output_parts)

            if proc.returncode != 0:
                output = f"Exit code: {proc.returncode}\n{output}"

            # Truncate very long output
            if len(output) > 30000:
                output = output[:15000] + "\n...[truncated]...\n" + output[-15000:]

            await self._emit_progress("Done.", 100)
            yield ToolCompleteEvent(output=output or "(no output)")

        except Exception as e:
            yield ToolCompleteEvent(output=f"Error: {e}")
