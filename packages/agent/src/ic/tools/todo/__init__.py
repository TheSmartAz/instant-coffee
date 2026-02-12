"""Plan tool - structured planning for complex tasks."""

from __future__ import annotations

from typing import Any

from ic.tools.base import BaseTool, ToolParam, ToolResult


class Todo(BaseTool):
    """Plan tool for creating and updating execution plans.

    Replaces the old Todo tool with a structured plan that fires
    callbacks for real-time UI updates.
    """

    name = "update_plan"
    description = (
        "Create or update the execution plan. Use this for complex tasks "
        "(multi-page sites, major redesigns, new features) to outline steps "
        "before executing. For simple refinements, execute directly without a plan."
    )
    parameters = [
        ToolParam(
            name="explanation",
            description="Brief explanation of the plan or what changed",
        ),
        ToolParam(
            name="steps",
            type="array",
            description=(
                "List of plan steps. Each step has 'step' (description) "
                "and 'status' (pending/in_progress/completed)."
            ),
        ),
    ]

    def __init__(self, engine: Any = None):
        self._engine = engine
        self._current_plan: dict[str, Any] = {}

    @property
    def current_plan(self) -> dict[str, Any]:
        return self._current_plan

    def to_openai_schema(self) -> dict[str, Any]:
        """Custom schema since steps has nested structure."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "explanation": {
                            "type": "string",
                            "description": "Brief explanation of the plan or what changed",
                        },
                        "steps": {
                            "type": "array",
                            "description": (
                                "List of plan steps. Each step has 'step' (description) "
                                "and 'status' (pending/in_progress/completed)."
                            ),
                            "items": {
                                "type": "object",
                                "properties": {
                                    "step": {
                                        "type": "string",
                                        "description": "Description of this step",
                                    },
                                    "status": {
                                        "type": "string",
                                        "enum": ["pending", "in_progress", "completed"],
                                        "description": "Current status of this step",
                                    },
                                },
                                "required": ["step", "status"],
                            },
                        },
                    },
                    "required": ["steps"],
                },
            },
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        explanation = kwargs.get("explanation", "")
        steps_raw = kwargs.get("steps", [])

        if not steps_raw:
            return ToolResult(error="At least one step is required", is_error=True)

        # Normalize steps
        steps = []
        for s in steps_raw:
            if isinstance(s, dict):
                # LLM may use various key names for the step description
                label = (
                    s.get("step")
                    or s.get("title")
                    or s.get("description")
                    or s.get("name")
                    or s.get("text")
                    or ""
                )
                steps.append({
                    "step": label,
                    "status": s.get("status", "pending"),
                })
            elif isinstance(s, str):
                steps.append({"step": s, "status": "pending"})

        self._current_plan = {
            "explanation": explanation,
            "steps": steps,
        }

        # Fire callback on engine if available
        if self._engine and hasattr(self._engine, "on_plan_update"):
            callback = getattr(self._engine, "on_plan_update", None)
            if callback:
                try:
                    result = callback(self._current_plan)
                    if hasattr(result, "__await__"):
                        await result
                except Exception:
                    pass

        # Format response
        lines = [f"Plan: {explanation}"]
        for i, s in enumerate(steps, 1):
            icon = {"pending": "○", "in_progress": "◉", "completed": "✓"}.get(
                s["status"], "○"
            )
            lines.append(f"  {icon} {i}. {s['step']}")

        completed = sum(1 for s in steps if s["status"] == "completed")
        lines.append(f"\nProgress: {completed}/{len(steps)} steps completed")

        return ToolResult(output="\n".join(lines))
