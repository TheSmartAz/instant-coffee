from __future__ import annotations

import inspect
import json
import logging
from dataclasses import dataclass
from typing import Any, Callable, Optional

from ..events.models import (
    AgentEndEvent,
    AgentProgressEvent,
    AgentStartEvent,
    ToolCallEvent,
    ToolResultEvent,
    TokenUsageEvent,
)
from ..llm.openai_client import LLMResponse, OpenAIClient
from ..services.token_tracker import TokenTrackerService

logger = logging.getLogger(__name__)


class APIError(Exception):
    """Generic API error."""


class RateLimitError(APIError):
    """Rate limit exceeded."""


@dataclass
class AgentResult:
    message: str
    is_complete: bool = True
    confidence: Optional[float] = None
    context: Optional[str] = None
    rounds_used: Optional[int] = None
    questions: Optional[list[dict]] = None
    missing_info: Optional[list[str]] = None


class BaseAgent:
    def __init__(
        self,
        db,
        session_id: str,
        settings,
        event_emitter=None,
        agent_id=None,
        task_id=None,
        token_tracker: TokenTrackerService | None = None,
        emit_lifecycle_events: bool = True,
    ) -> None:
        self.db = db
        self.session_id = session_id
        self.settings = settings
        self.event_emitter = event_emitter
        resolved_agent_type = getattr(self, "agent_type", "agent")
        self.agent_id = agent_id or f"{resolved_agent_type}_1"
        self.task_id = task_id
        self.emit_lifecycle_events = emit_lifecycle_events
        if token_tracker is not None:
            self.token_tracker = token_tracker
        elif db is not None:
            self.token_tracker = TokenTrackerService(db)
        else:
            self.token_tracker = None
        self._llm_client: OpenAIClient | None = None
        self._warned_responses_fallback = False

    def _get_llm_client(self) -> OpenAIClient:
        if self._llm_client is None:
            self._llm_client = OpenAIClient(settings=self.settings, token_tracker=self.token_tracker)
        return self._llm_client

    def _use_chat_completions(self, client: OpenAIClient | None = None) -> bool:
        mode = getattr(self.settings, "openai_api_mode", "responses") or "responses"
        normalized = str(mode).strip().lower()
        if normalized in {"chat", "chat_completions", "chat-completions", "completions"}:
            return True
        resolved_client = client or self._get_llm_client()
        if not resolved_client.supports_responses():
            if not self._warned_responses_fallback:
                logger.warning(
                    "OpenAI SDK lacks Responses API support; falling back to chat completions. "
                    "Set OPENAI_API_MODE=chat or upgrade the openai package."
                )
                self._warned_responses_fallback = True
            return True
        return False

    async def _call_llm(
        self,
        messages: list[dict],
        *,
        agent_type: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        tools: Optional[list[Any]] = None,
        stream: bool = False,
        emit_progress: bool = True,
        context: Optional[str] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        resolved_agent_type = agent_type or getattr(self, "agent_type", "agent")
        self._emit_agent_start(context=context, agent_type=resolved_agent_type)
        client = self._get_llm_client()

        try:
            if stream:
                full_response = ""
                last_progress = 0
                stream_iter = (
                    client.chat_completion_stream
                    if self._use_chat_completions(client)
                    else client.responses_stream
                )
                async for chunk in stream_iter(
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                ):
                    if not chunk:
                        continue
                    full_response += chunk
                    if emit_progress:
                        progress = min(90, 10 + len(full_response) // 200)
                        if progress > last_progress:
                            last_progress = progress
                            self._emit_agent_progress(
                                message=chunk[-200:],
                                progress=progress,
                                agent_type=resolved_agent_type,
                            )
                response = LLMResponse(content=full_response)
            else:
                if self._use_chat_completions(client):
                    response = await client.chat_completion(
                        messages=messages,
                        model=model,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        tools=tools,
                        **kwargs,
                    )
                else:
                    response = await client.responses_create(
                        messages=messages,
                        model=model,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        tools=tools,
                        **kwargs,
                    )

            if response.token_usage and self.token_tracker is not None:
                self.token_tracker.record_usage(
                    session_id=self.session_id,
                    agent_type=resolved_agent_type,
                    model=model or self.settings.model,
                    input_tokens=response.token_usage.input_tokens,
                    output_tokens=response.token_usage.output_tokens,
                    cost_usd=response.token_usage.cost_usd,
                )
                self._emit_token_usage(
                    input_tokens=response.token_usage.input_tokens,
                    output_tokens=response.token_usage.output_tokens,
                    total_tokens=response.token_usage.total_tokens,
                    cost_usd=response.token_usage.cost_usd,
                    agent_type=resolved_agent_type,
                )

            summary = response.content[:200] if response.content else None
            self._emit_agent_end(status="success", summary=summary, agent_type=resolved_agent_type)
            return response
        except Exception as exc:
            self._emit_agent_end(status="failed", summary=str(exc), agent_type=resolved_agent_type)
            raise

    async def _call_llm_with_tools(
        self,
        messages: list[dict],
        tools: list[Any],
        tool_handlers: dict[str, Callable[..., Any]],
        *,
        agent_type: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_iterations: int = 10,
        context: Optional[str] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        resolved_agent_type = agent_type or getattr(self, "agent_type", "agent")
        self._emit_agent_start(context=context, agent_type=resolved_agent_type)
        wrapped_handlers = {
            name: self._wrap_tool_handler(name, handler)
            for name, handler in tool_handlers.items()
        }
        client = self._get_llm_client()
        try:
            if self._use_chat_completions(client):
                response = await client.chat_with_tools(
                    messages=messages,
                    tools=tools,
                    tool_handlers=wrapped_handlers,
                    model=model,
                    temperature=temperature,
                    max_iterations=max_iterations,
                    **kwargs,
                )
            else:
                response = await client.responses_with_tools(
                    messages=messages,
                    tools=tools,
                    tool_handlers=wrapped_handlers,
                    model=model,
                    temperature=temperature,
                    max_iterations=max_iterations,
                    **kwargs,
                )
            if response.token_usage and self.token_tracker is not None:
                self.token_tracker.record_usage(
                    session_id=self.session_id,
                    agent_type=resolved_agent_type,
                    model=model or self.settings.model,
                    input_tokens=response.token_usage.input_tokens,
                    output_tokens=response.token_usage.output_tokens,
                    cost_usd=response.token_usage.cost_usd,
                )
                self._emit_token_usage(
                    input_tokens=response.token_usage.input_tokens,
                    output_tokens=response.token_usage.output_tokens,
                    total_tokens=response.token_usage.total_tokens,
                    cost_usd=response.token_usage.cost_usd,
                    agent_type=resolved_agent_type,
                )
            summary = response.content[:200] if response.content else None
            self._emit_agent_end(status="success", summary=summary, agent_type=resolved_agent_type)
            return response
        except Exception as exc:
            self._emit_agent_end(status="failed", summary=str(exc), agent_type=resolved_agent_type)
            raise

    def _wrap_tool_handler(self, tool_name: str, handler: Callable[..., Any]) -> Callable[..., Any]:
        async def wrapped(*args: Any, **kwargs: Any) -> Any:
            tool_input = self._format_tool_input(args, kwargs)
            logger.info(
                "Tool call: name=%s agent_id=%s task_id=%s input=%s",
                tool_name,
                self.agent_id or "unknown",
                self.task_id,
                self._log_value(tool_input),
            )
            self._emit_tool_call(tool_name, tool_input)
            try:
                result = handler(*args, **kwargs)
                if inspect.isawaitable(result):
                    result = await result
                result_payload = self._normalize_tool_result(result)
            except Exception as exc:
                error_message = str(exc)
                logger.warning(
                    "Tool error: name=%s agent_id=%s task_id=%s error=%s",
                    tool_name,
                    self.agent_id or "unknown",
                    self.task_id,
                    error_message,
                )
                self._emit_tool_result(tool_name, success=False, error=error_message)
                return {"success": False, "output": None, "error": error_message}

            success = bool(result_payload.get("success", True))
            output = result_payload.get("output") if success else None
            error = result_payload.get("error") if not success else None
            if success:
                logger.info(
                    "Tool result: name=%s agent_id=%s task_id=%s output=%s",
                    tool_name,
                    self.agent_id or "unknown",
                    self.task_id,
                    self._log_value(output),
                )
            else:
                logger.warning(
                    "Tool failed: name=%s agent_id=%s task_id=%s error=%s",
                    tool_name,
                    self.agent_id or "unknown",
                    self.task_id,
                    error or "unknown error",
                )
            self._emit_tool_result(tool_name, success=success, output=output, error=error)
            return result_payload

        return wrapped

    def _format_tool_input(self, args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any:
        if kwargs:
            return kwargs
        if len(args) == 1:
            return args[0]
        if args:
            return {"args": list(args)}
        return None

    def _normalize_tool_result(self, result: Any) -> dict[str, Any]:
        if hasattr(result, "to_dict"):
            payload = result.to_dict()
            if isinstance(payload, dict):
                return self._ensure_json_dict(payload)
        if isinstance(result, dict) and "success" in result:
            return self._ensure_json_dict(result)
        return self._ensure_json_dict({"success": True, "output": result})

    def _ensure_json_dict(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._json_safe(payload)

    def _json_safe(self, value: Any) -> Any:
        if value is None:
            return None
        try:
            json.dumps(value, ensure_ascii=False)
            return value
        except TypeError:
            if isinstance(value, dict):
                return {str(key): self._json_safe(item) for key, item in value.items()}
            if isinstance(value, (list, tuple, set)):
                return [self._json_safe(item) for item in value]
            if hasattr(value, "model_dump"):
                return self._json_safe(value.model_dump())
            if hasattr(value, "dict"):
                return self._json_safe(value.dict())
            return str(value)

    def _log_value(self, value: Any, limit: int = 500) -> str:
        if value is None:
            return "null"
        redacted = self._redact_for_log(value)
        try:
            text = json.dumps(redacted, ensure_ascii=False)
        except TypeError:
            text = str(redacted)
        if len(text) > limit:
            return f"{text[:limit]}...<truncated>"
        return text

    def _redact_for_log(self, value: Any) -> Any:
        if isinstance(value, dict):
            redacted = {}
            for key, item in value.items():
                lowered = str(key).lower()
                if lowered in {"content", "html", "prompt", "message", "data"}:
                    redacted[str(key)] = "<redacted>"
                else:
                    redacted[str(key)] = self._redact_for_log(item)
            return redacted
        if isinstance(value, (list, tuple, set)):
            return [self._redact_for_log(item) for item in value]
        return value

    def _emit_tool_call(self, tool_name: str, tool_input: Any) -> None:
        if not self.event_emitter:
            return
        normalized_input = (
            tool_input if isinstance(tool_input, dict) or tool_input is None else {"value": tool_input}
        )
        normalized_input = self._json_safe(normalized_input)
        payload = {
            "task_id": self.task_id,
            "agent_id": self.agent_id or "unknown",
            "agent_type": getattr(self, "agent_type", "agent"),
            "tool_name": tool_name,
            "tool_input": normalized_input,
        }
        self.event_emitter.emit(ToolCallEvent(**payload))

    def _emit_agent_start(self, *, context: Optional[str] = None, agent_type: Optional[str] = None) -> None:
        if not self.event_emitter or not self.emit_lifecycle_events:
            return
        payload = {
            "task_id": self.task_id,
            "agent_id": self.agent_id or "unknown",
            "agent_type": agent_type or getattr(self, "agent_type", "agent"),
        }
        if context:
            payload["context"] = context
        self.event_emitter.emit(AgentStartEvent(**payload))

    def _emit_agent_progress(
        self,
        *,
        message: str,
        progress: Optional[int] = None,
        agent_type: Optional[str] = None,
    ) -> None:
        if not self.event_emitter:
            return
        payload = {
            "task_id": self.task_id,
            "agent_id": self.agent_id or "unknown",
            "message": message,
            "progress": progress,
        }
        if agent_type:
            payload["agent_type"] = agent_type
        self.event_emitter.emit(AgentProgressEvent(**payload))

    def _emit_agent_end(
        self,
        *,
        status: str,
        summary: Optional[str] = None,
        agent_type: Optional[str] = None,
    ) -> None:
        if not self.event_emitter or not self.emit_lifecycle_events:
            return
        payload = {
            "task_id": self.task_id,
            "agent_id": self.agent_id or "unknown",
            "status": status,
            "summary": summary,
        }
        if agent_type:
            payload["agent_type"] = agent_type
        self.event_emitter.emit(AgentEndEvent(**payload))

    def _emit_tool_result(
        self,
        tool_name: str,
        *,
        success: bool,
        output: Any = None,
        error: Optional[str] = None,
    ) -> None:
        if not self.event_emitter:
            return
        normalized_output = (
            output if isinstance(output, dict) or output is None else {"value": output}
        )
        normalized_output = self._json_safe(normalized_output)
        payload = {
            "task_id": self.task_id,
            "agent_id": self.agent_id or "unknown",
            "agent_type": getattr(self, "agent_type", "agent"),
            "tool_name": tool_name,
            "success": success,
            "tool_output": normalized_output if normalized_output is not None else None,
            "error": error,
        }
        self.event_emitter.emit(ToolResultEvent(**payload))

    def _emit_token_usage(
        self,
        *,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        cost_usd: float,
        agent_type: Optional[str] = None,
    ) -> None:
        if not self.event_emitter:
            return
        payload = {
            "task_id": self.task_id,
            "agent_type": agent_type or getattr(self, "agent_type", "agent"),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "cost_usd": cost_usd,
        }
        self.event_emitter.emit(TokenUsageEvent(**payload))


__all__ = ["APIError", "RateLimitError", "AgentResult", "BaseAgent"]
