"""Sub-agent tool - enables multi-agent collaboration."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from ic.tools.base import BaseTool, ToolParam, ToolResult

if TYPE_CHECKING:
    from ic.soul.engine import Engine


class CreateSubAgent(BaseTool):
    name = "create_sub_agent"
    description = (
        "Create a sub-agent to handle a specific task autonomously. "
        "Use this for complex tasks that benefit from focused execution, "
        "parallel work, or specialized expertise. The sub-agent has access "
        "to file, shell, and think tools but cannot create further sub-agents."
    )
    parameters = [
        ToolParam(name="task", description="Clear description of the task for the sub-agent"),
        ToolParam(
            name="model", description="Model to use (default: same as parent)",
            required=False,
        ),
        ToolParam(
            name="max_turns", type="integer",
            description="Max turns for the sub-agent (default: 30)",
            required=False,
        ),
    ]

    def __init__(self, engine: Engine | None = None):
        self._engine = engine

    async def execute(self, **kwargs: Any) -> ToolResult:
        if not self._engine:
            return ToolResult(error="Sub-agent engine not available", is_error=True)

        task = kwargs["task"]
        model_name = kwargs.get("model")
        max_turns = int(kwargs.get("max_turns", 30))

        try:
            result = await self._engine.run_sub_agent(
                task=task,
                model_name=model_name,
                max_turns=max_turns,
            )
            return ToolResult(output=result)
        except Exception as e:
            return ToolResult(error=f"Sub-agent failed: {e}", is_error=True)
