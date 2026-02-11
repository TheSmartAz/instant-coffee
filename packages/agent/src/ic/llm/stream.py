"""Stream event types and handler for LLM output."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Awaitable


class StreamEventType(Enum):
    TEXT_DELTA = "text_delta"
    TEXT = "text"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    TOOL_PROGRESS = "tool_progress"  # New: progress during tool execution
    DONE = "done"
    ERROR = "error"


@dataclass
class StreamEvent:
    type: StreamEventType
    data: Any = None


class StreamHandler:
    """Collects stream events and dispatches to callbacks."""

    def __init__(self):
        self._callbacks: dict[StreamEventType, list[Callable]] = {}

    def on(self, event_type: StreamEventType, callback: Callable) -> StreamHandler:
        self._callbacks.setdefault(event_type, []).append(callback)
        return self

    async def emit(self, event: StreamEvent):
        for cb in self._callbacks.get(event.type, []):
            result = cb(event)
            if hasattr(result, "__await__"):
                await result
