"""EventBridge — maps Engine callbacks to backend EventEmitter events."""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from ..events.emitter import EventEmitter
from ..events.models import (
    AgentEndEvent,
    AgentStartEvent,
    AgentSpawnedEvent,
    BgTaskCompletedEvent,
    BgTaskFailedEvent,
    BgTaskStartedEvent,
    ContextCompactedEvent,
    CostUpdateEvent,
    FilesChangedEvent,
    PlanUpdateEvent,
    ShellApprovalEvent,
    TextDeltaEvent,
    ToolCallEvent,
    ToolProgressEvent,
    ToolResultEvent,
    TokenUsageEvent,
)

logger = logging.getLogger(__name__)

_AGENT_ID = "engine"
_AGENT_TYPE = "engine"


class _ThinkTagStripper:
    """Streaming-aware stripper for <think>...</think> blocks.

    Some models (DeepSeek, Qwen3, etc.) emit thinking content inside
    ``<think>`` tags in the regular content stream instead of using the
    ``reasoning_content`` field.  This class buffers incoming deltas and
    strips out everything between ``<think>`` and ``</think>`` (inclusive),
    returning only the visible portion for each ``feed()`` call.
    """

    def __init__(self) -> None:
        self._inside_think = False
        # Partial tag buffer — holds chars that *might* be the start of
        # ``<think>`` or ``</think>`` but we haven't seen enough yet.
        self._partial: str = ""

    def feed(self, delta: str) -> str:
        """Process *delta* and return the portion that should be visible."""
        out: list[str] = []
        buf = self._partial + delta
        self._partial = ""
        i = 0

        while i < len(buf):
            if self._inside_think:
                # Look for </think>
                close_idx = buf.find("</think>", i)
                if close_idx == -1:
                    # Might be a partial closing tag at the tail
                    # Keep up to 8 chars (len("</think>")) as partial
                    tail = buf[max(i, len(buf) - 8):]
                    if "<" in tail:
                        self._partial = tail[tail.index("<"):]
                    # Everything consumed — still inside think
                    break
                else:
                    # Skip past </think>
                    i = close_idx + len("</think>")
                    self._inside_think = False
            else:
                # Look for <think>
                open_idx = buf.find("<think>", i)
                if open_idx == -1:
                    # Might be a partial opening tag at the tail
                    tail = buf[max(i, len(buf) - 7):]  # len("<think>") == 7
                    if "<" in tail:
                        # Could be start of <think> — hold it back
                        cut = i + (len(buf) - i) - len(tail) + tail.index("<")
                        out.append(buf[i:cut])
                        self._partial = buf[cut:]
                    else:
                        out.append(buf[i:])
                    break
                else:
                    # Emit everything before <think>
                    out.append(buf[i:open_idx])
                    i = open_idx + len("<think>")
                    self._inside_think = True

        return "".join(out)


class EventBridge:
    """Translates Engine streaming callbacks into EventEmitter events.

    Usage::

        bridge = EventBridge(emitter, session_id)
        engine = Engine(
            ...,
            on_text_delta=bridge.on_text_delta,
            on_tool_call=bridge.on_tool_call,
            on_tool_result=bridge.on_tool_result,
            on_tool_progress=bridge.on_tool_progress,
            on_sub_agent_start=bridge.on_sub_agent_start,
            on_sub_agent_end=bridge.on_sub_agent_end,
            on_cost_update=bridge.on_cost_update,
            on_before_shell_execute=bridge.on_before_shell_execute,
        )
    """

    def __init__(self, emitter: EventEmitter, session_id: str) -> None:
        self._emitter = emitter
        self._session_id = session_id
        self._text_buffer: list[str] = []
        self._think_stripper = _ThinkTagStripper()
        self._pending_approvals: dict[str, asyncio.Future] = {}
        self._active_sub_agents: dict[str, str] = {}  # agent_id → task description

    async def on_text_delta(self, delta: str) -> None:
        """Emit a TextDeltaEvent for real-time streaming and buffer for final text.

        Strips ``<think>...</think>`` blocks so thinking content from models
        like DeepSeek / Qwen3 never reaches the frontend.
        """
        self._text_buffer.append(delta)
        visible = self._think_stripper.feed(delta)
        if not visible:
            return
        self._emitter.emit(
            TextDeltaEvent(
                session_id=self._session_id,
                delta=visible,
            )
        )

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

    async def on_tool_progress(self, name: str, message: str, percent: int | None) -> None:
        """Emit a ToolProgressEvent during tool execution."""
        self._emitter.emit(
            ToolProgressEvent(
                session_id=self._session_id,
                agent_id=_AGENT_ID,
                agent_type=_AGENT_TYPE,
                tool_name=name,
                progress_message=message,
                progress_percent=percent,
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
        """Emit AgentSpawnedEvent + AgentStartEvent when a sub-agent is spawned."""
        agent_id = f"sub-{uuid.uuid4().hex[:8]}"
        self._active_sub_agents[agent_id] = task[:500] if task else ""
        self._emitter.emit(
            AgentSpawnedEvent(
                session_id=self._session_id,
                agent_id=agent_id,
                task_description=task[:500] if task else "",
            )
        )
        self._emitter.emit(
            AgentStartEvent(
                session_id=self._session_id,
                agent_id=agent_id,
                agent_type="sub_agent",
            )
        )

    async def on_sub_agent_end(self, result: str) -> None:
        """Emit AgentEndEvent when a sub-agent finishes."""
        # Pop the oldest active sub-agent (FIFO order for sequential calls,
        # and any-order is fine for concurrent since each gets its own id)
        if self._active_sub_agents:
            agent_id = next(iter(self._active_sub_agents))
            self._active_sub_agents.pop(agent_id, None)
        else:
            agent_id = "sub-agent"
        self._emitter.emit(
            AgentEndEvent(
                session_id=self._session_id,
                agent_id=agent_id,
                status="success",
                summary=result[:500] if result else None,
            )
        )

    async def on_cost_update(self, cost: dict[str, Any]) -> None:
        """Emit CostUpdateEvent with real-time cost tracking data."""
        self._emitter.emit(
            CostUpdateEvent(
                session_id=self._session_id,
                prompt_tokens=cost.get("prompt_tokens", 0),
                completion_tokens=cost.get("completion_tokens", 0),
                total_cost_usd=cost.get("total_cost_usd", 0.0),
            )
        )

    async def on_before_shell_execute(self, command: str) -> bool:
        """Emit ShellApprovalEvent and wait for user approval.

        Returns True if the command is approved, False if denied.
        In web app context, this sends an SSE event and waits for
        the frontend to respond via an API endpoint.
        """
        from ic.tools.shell import check_command_safety

        is_safe, reason = check_command_safety(command)
        if is_safe:
            return True

        approval_id = uuid.uuid4().hex[:12]
        future: asyncio.Future[bool] = asyncio.get_event_loop().create_future()
        self._pending_approvals[approval_id] = future

        self._emitter.emit(
            ShellApprovalEvent(
                session_id=self._session_id,
                command=command,
                reason=reason,
                approval_id=approval_id,
            )
        )

        try:
            # Wait up to 60 seconds for user response
            return await asyncio.wait_for(future, timeout=60.0)
        except asyncio.TimeoutError:
            return False
        finally:
            self._pending_approvals.pop(approval_id, None)

    def resolve_shell_approval(self, approval_id: str, approved: bool) -> bool:
        """Resolve a pending shell approval request (called from API endpoint).

        Returns True if the approval was found and resolved.
        """
        future = self._pending_approvals.get(approval_id)
        if future and not future.done():
            future.set_result(approved)
            return True
        return False

    def emit_token_usage(self, usage: dict[str, int], cost_usd: float = 0.0) -> None:
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
                cost_usd=cost_usd,
            )
        )

    def get_accumulated_text(self) -> str:
        """Return and clear the accumulated text buffer.

        Strips any ``<think>...</think>`` blocks from the final text so
        thinking content is never persisted in the assistant message.
        """
        import re

        text = "".join(self._text_buffer)
        self._text_buffer.clear()
        # Strip complete think blocks (dotall so . matches newlines)
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
        # Strip unclosed trailing <think> block (model was cut off mid-think)
        text = re.sub(r"<think>.*$", "", text, flags=re.DOTALL)
        return text.strip()

    # ── Phase 9: Agent improvement callbacks ──────────────────

    def emit_files_changed(self, files: list[dict]) -> None:
        """Emit FilesChangedEvent after a turn with file modifications."""
        if not files:
            return
        self._emitter.emit(
            FilesChangedEvent(
                session_id=self._session_id,
                files=files,
            )
        )

    async def on_context_compacted(self, compact_result: dict) -> None:
        """Emit ContextCompactedEvent when context is compacted."""
        self._emitter.emit(
            ContextCompactedEvent(
                session_id=self._session_id,
                tokens_saved=compact_result.get("tokens_saved", 0),
                turns_removed=compact_result.get("turns_removed", 0),
            )
        )

    async def on_plan_update(self, plan: dict) -> None:
        """Emit PlanUpdateEvent when the agent creates or updates a plan."""
        self._emitter.emit(
            PlanUpdateEvent(
                session_id=self._session_id,
                explanation=plan.get("explanation", ""),
                steps=plan.get("steps", []),
            )
        )

    def emit_bg_task_started(self, task_id: str, command: str) -> None:
        """Emit BgTaskStartedEvent when a background shell task starts."""
        self._emitter.emit(
            BgTaskStartedEvent(
                session_id=self._session_id,
                task_id=task_id,
                command=command,
            )
        )

    def emit_bg_task_completed(self, task_id: str, output: str, exit_code: int | None = None) -> None:
        """Emit BgTaskCompletedEvent when a background shell task completes."""
        self._emitter.emit(
            BgTaskCompletedEvent(
                session_id=self._session_id,
                task_id=task_id,
                output=output[:2000] if output else None,
                exit_code=exit_code,
            )
        )

    def emit_bg_task_failed(self, task_id: str, error: str) -> None:
        """Emit BgTaskFailedEvent when a background shell task fails."""
        self._emitter.emit(
            BgTaskFailedEvent(
                session_id=self._session_id,
                task_id=task_id,
                error=error[:1000] if error else "",
            )
        )
