"""Shell command execution tool."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from ic.tools.base import BaseTool, ToolParam, ToolResult


class Shell(BaseTool):
    name = "shell"
    description = "Execute a shell command and return its output. Use for git, npm, pip, and other CLI operations."
    parameters = [
        ToolParam(name="command", description="The shell command to execute"),
        ToolParam(name="timeout", type="integer", description="Timeout in seconds (default 120)", required=False),
    ]

    def __init__(self, workspace: Path | None = None):
        self._workspace = workspace

    async def execute(self, **kwargs: Any) -> ToolResult:
        command = kwargs["command"]
        timeout = int(kwargs.get("timeout", 120))
        cwd = str(self._workspace) if self._workspace else None
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
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
            return ToolResult(output=output or "(no output)")
        except asyncio.TimeoutError:
            return ToolResult(error=f"Command timed out after {timeout}s", is_error=True)
        except Exception as e:
            return ToolResult(error=str(e), is_error=True)
