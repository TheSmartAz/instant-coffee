"""Sub-agent tools - enables multi-agent collaboration."""

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


class CreateParallelSubAgents(BaseTool):
    name = "create_parallel_sub_agents"
    description = (
        "Spawn multiple sub-agents that run concurrently. Each sub-agent "
        "executes its task independently and in parallel. Use this for "
        "multi-page generation where each page can be built independently. "
        "All sub-agents share the same workspace and have access to file, "
        "shell, and think tools."
    )
    parameters = [
        ToolParam(
            name="tasks",
            type="array",
            description=(
                "Array of task objects. Each object has: "
                "'task' (string, required) — description of what to build; "
                "'model' (string, optional) — model override; "
                "'max_turns' (integer, optional, default 30) — turn limit."
            ),
        ),
    ]
    is_concurrent_safe = False
    timeout_seconds = 600.0  # 10 minutes for parallel page generation

    def __init__(self, engine: Engine | None = None):
        self._engine = engine

    async def execute(self, **kwargs: Any) -> ToolResult:
        if not self._engine:
            return ToolResult(error="Sub-agent engine not available", is_error=True)

        tasks = kwargs.get("tasks", [])
        if not tasks or not isinstance(tasks, list):
            return ToolResult(error="'tasks' must be a non-empty array", is_error=True)

        try:
            results = await self._engine.run_sub_agents_parallel(tasks)
        except Exception as e:
            return ToolResult(error=f"Parallel sub-agents failed: {e}", is_error=True)

        # Format summary
        lines = [f"Parallel execution complete — {len(results)} sub-agents ran.\n"]
        for i, r in enumerate(results, 1):
            task_desc = r["task"][:80]
            if r["error"]:
                lines.append(f"### Agent {i}: FAILED\nTask: {task_desc}\nError: {r['error']}\n")
            else:
                summary = (r["result"] or "")[:500]
                lines.append(f"### Agent {i}: OK\nTask: {task_desc}\nResult: {summary}\n")

        return ToolResult(output="\n".join(lines))
