"""Think tool - allows the agent to reason through complex problems."""

from __future__ import annotations

from typing import Any

from ic.tools.base import BaseTool, ToolParam, ToolResult


class Think(BaseTool):
    name = "think"
    description = "Use this tool to think through complex problems step by step. The content is not shown to the user."
    parameters = [
        ToolParam(name="thought", description="Your reasoning and analysis"),
    ]

    async def execute(self, **kwargs: Any) -> ToolResult:
        return ToolResult(output="Thought recorded.")
