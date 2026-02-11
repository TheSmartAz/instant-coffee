"""Base tool class for the agent tool system with streaming support."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, Awaitable


@dataclass
class ToolParam:
    """A single tool parameter."""

    name: str
    type: str = "string"
    description: str = ""
    required: bool = True
    enum: list[str] | None = None


@dataclass
class ToolResult:
    """Result from a tool execution."""

    output: str = ""
    error: str | None = None
    is_error: bool = False

    def to_content(self) -> str:
        if self.is_error:
            return f"Error: {self.error}"
        return self.output


# Tool execution event types
@dataclass
class ToolProgressEvent:
    """Progress update during tool execution."""

    message: str
    percent: int | None = None  # 0-100, or None for indeterminate


@dataclass
class ToolCompleteEvent:
    """Tool execution completed successfully."""

    output: str


@dataclass
class ToolErrorEvent:
    """Tool execution failed."""

    error: str
    details: str | None = None


ToolEvent = ToolProgressEvent | ToolCompleteEvent | ToolErrorEvent


def validate_tool_args(params: list[ToolParam], args: dict[str, Any]) -> str | None:
    """Validate tool arguments against parameter definitions.

    Returns an error message string if validation fails, or None if valid.
    """
    errors: list[str] = []

    # Check required params
    for p in params:
        if p.required and p.name not in args:
            errors.append(f"Missing required parameter: '{p.name}'")

    # Type check provided params
    type_checks = {
        "string": (str, "a string"),
        "integer": ((int,), "an integer"),
        "number": ((int, float), "a number"),
        "boolean": (bool, "a boolean"),
        "array": (list, "an array"),
        "object": (dict, "an object"),
    }

    for p in params:
        if p.name not in args:
            continue
        val = args[p.name]
        if val is None:
            continue

        expected = type_checks.get(p.type)
        if expected:
            types, label = expected
            if not isinstance(val, types):
                # Auto-coerce string→int for integer params
                if p.type == "integer" and isinstance(val, str):
                    try:
                        args[p.name] = int(val)
                        continue
                    except ValueError:
                        pass
                # Auto-coerce string→bool for boolean params
                if p.type == "boolean" and isinstance(val, str):
                    args[p.name] = val.lower() in ("true", "1", "yes")
                    continue
                errors.append(
                    f"Parameter '{p.name}' should be {label}, got {type(val).__name__}"
                )

        # Enum check
        if p.enum and val not in p.enum:
            errors.append(
                f"Parameter '{p.name}' must be one of {p.enum}, got '{val}'"
            )

    if errors:
        return "Validation errors:\n" + "\n".join(f"  - {e}" for e in errors)
    return None


class BaseTool(ABC):
    """Base class for all tools with streaming support.

    Tools can implement either:
    1. execute() - Simple sync-style execution (backward compatible)
    2. execute_stream() - Async streaming with progress updates
    """

    name: str = ""
    description: str = ""
    parameters: list[ToolParam] = []
    is_concurrent_safe: bool = False  # True for read-only tools with no side effects
    timeout_seconds: float = 60.0  # Per-tool timeout; override in subclasses
    max_retries: int = 0  # Number of automatic retries on transient errors

    # Progress callback (optional, for backward compatibility)
    _on_progress: Callable[[ToolProgressEvent], Awaitable[None] | None] | None = None

    def set_progress_callback(
        self,
        callback: Callable[[ToolProgressEvent], Awaitable[None] | None],
    ):
        """Set a callback for progress updates."""
        self._on_progress = callback

    async def _emit_progress(self, message: str, percent: int | None = None):
        """Emit a progress event if callback is set."""
        if self._on_progress:
            event = ToolProgressEvent(message=message, percent=percent)
            result = self._on_progress(event)
            if hasattr(result, "__await__"):
                await result

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the tool with given arguments.

        This is the simple synchronous-style interface.
        Default implementation wraps execute_stream().
        """
        # Default: collect all stream events into a final result
        async for event in self.execute_stream(**kwargs):
            if isinstance(event, ToolCompleteEvent):
                return ToolResult(output=event.output)
            elif isinstance(event, ToolErrorEvent):
                return ToolResult(error=event.error, is_error=True)
        return ToolResult(output="")

    async def execute_stream(self, **kwargs: Any) -> AsyncIterator[ToolEvent]:
        """Execute the tool with streaming progress updates.

        Yield ToolProgressEvent for progress updates,
        ToolCompleteEvent on success, or ToolErrorEvent on failure.

        Default implementation delegates to execute() for backward compatibility.
        """
        result = await self.execute(**kwargs)
        if result.is_error:
            yield ToolErrorEvent(error=result.error or "Unknown error")
        else:
            yield ToolCompleteEvent(output=result.output)

    def to_openai_schema(self) -> dict[str, Any]:
        """Convert to OpenAI function calling schema."""
        properties = {}
        required = []
        for p in self.parameters:
            prop: dict[str, Any] = {"type": p.type, "description": p.description}
            if p.enum:
                prop["enum"] = p.enum
            properties[p.name] = prop
            if p.required:
                required.append(p.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }
