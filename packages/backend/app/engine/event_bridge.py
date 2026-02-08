"""EventBridge — maps Engine callbacks to backend EventEmitter events."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from ..events.emitter import EventEmitter
from ..events.models import (
    AgentEndEvent,
    AgentStartEvent,
    ToolCallEvent,
    ToolResultEvent,
    TokenUsageEvent,
)

logger = logging.getLogger(__name__)

_AGENT_ID = "engine"
_AGENT_TYPE = "engine"


class EventBridge:
    """Translates Engine streaming callbacks into EventEmitter events.

    Usage::

        bridge = EventBridge(emitter, session_id)
        engine = Engine(
            ...,
            on_text_delta=bridge.on_text_delta,
            on_tool_call=bridge.on_tool_call,
            on_tool_result=bridge.on_tool_result,
            on_sub_agent_start=bridge.on_sub_agent_start,
            on_sub_agent_end=bridge.on_sub_agent_end,
        )
    """

    def __init__(self, emitter: EventEmitter, session_id: str) -> None:
        self._emitter = emitter
        self._session_id = session_id
        self._text_buffer: list[str] = []

    async def on_text_delta(self, delta: str) -> None:
        """Accumulate text deltas (no per-delta event needed)."""
        self._text_buffer.append(delta)

    async def on_tool_call(self, name: str, tc: dict[str, Any]) -> None:
        """Emit a ToolCallEvent when the engine invokes a tool."""
        tool_input = tc.get("arguments")
        if isinstance(tool_input, str):
            import json

            try:
                tool_input = json.loads(tool_input)
            except Exception:
                tool_input = {"raw": tool_input}

        self._emitter.emit(
            ToolCallEvent(
                session_id=self._session_id,
                agent_id=_AGENT_ID,
                agent_type=_AGENT_TYPE,
                tool_name=name,
                tool_input=tool_input,
            )
        )

    async def on_tool_result(self, name: str, result: str) -> None:
        """Emit a ToolResultEvent after tool execution."""
        is_error = result.startswith("Error")
        self._emitter.emit(
            ToolResultEvent(
                session_id=self._session_id,
                agent_id=_AGENT_ID,
                agent_type=_AGENT_TYPE,
                tool_name=name,
                success=not is_error,
                tool_output=result[:2000] if result else None,
                error=result if is_error else None,
            )
        )

    async def on_sub_agent_start(self, task: str) -> None:
        """Emit AgentStartEvent when a sub-agent is spawned."""
        self._emitter.emit(
            AgentStartEvent(
                session_id=self._session_id,
                agent_id=f"sub-{uuid.uuid4().hex[:8]}",
                agent_type="sub_agent",
            )
        )

    async def on_sub_agent_end(self, result: str) -> None:
        """Emit AgentEndEvent when a sub-agent finishes."""
        self._emitter.emit(
            AgentEndEvent(
                session_id=self._session_id,
                agent_id="sub-agent",
                status="success",
                summary=result[:500] if result else None,
            )
        )

    def emit_token_usage(self, usage: dict[str, int]) -> None:
        """Emit a TokenUsageEvent from the engine's accumulated usage."""
        prompt = usage.get("prompt_tokens", 0)
        completion = usage.get("completion_tokens", 0)
        total = prompt + completion
        if total == 0:
            return
        self._emitter.emit(
            TokenUsageEvent(
                session_id=self._session_id,
                agent_type=_AGENT_TYPE,
                input_tokens=prompt,
                output_tokens=completion,
                total_tokens=total,
                cost_usd=0.0,
            )
        )

    def get_accumulated_text(self) -> str:
        """Return and clear the accumulated text buffer."""
        text = "".join(self._text_buffer)
        self._text_buffer.clear()
        return text
