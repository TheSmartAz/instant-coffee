from __future__ import annotations

import asyncio
import inspect
import json
import logging
from dataclasses import dataclass
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Sequence

import httpx
import openai
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageToolCall, ChatCompletionToolParam

from ..config import Settings, get_settings
from .retry import with_retry

logger = logging.getLogger(__name__)


class OpenAIClientError(Exception):
    """Base error for OpenAI client failures."""


class RateLimitError(OpenAIClientError):
    """Rate limit exceeded."""


class AuthenticationError(OpenAIClientError):
    """Authentication failed."""


class TimeoutError(OpenAIClientError):
    """Request timed out."""


class ContextLengthError(OpenAIClientError):
    """Context length exceeded."""


class APIError(OpenAIClientError):
    """Generic API error."""


@dataclass
class TokenUsage:
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float
    raw: Optional[Dict[str, Any]] = None


@dataclass
class LLMResponse:
    content: str
    tool_calls: Optional[List[ChatCompletionMessageToolCall]] = None
    token_usage: Optional[TokenUsage] = None


class OpenAIClient:
    _pricing: Dict[str, Dict[str, float]] = {
        "gpt-4o": {"input": 5.0, "output": 15.0},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4-turbo": {"input": 10.0, "output": 30.0},
        "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
    }

    def __init__(
        self,
        *,
        settings: Optional[Settings] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout_seconds: Optional[float] = None,
        max_retries: Optional[int] = None,
        base_delay: Optional[float] = None,
        token_tracker: Any | None = None,
    ) -> None:
        resolved_settings = settings or get_settings()
        resolved_api_key = api_key or resolved_settings.openai_api_key or resolved_settings.default_key
        resolved_base_url = base_url or resolved_settings.openai_base_url or resolved_settings.default_base_url
        if not resolved_api_key:
            raise OpenAIClientError("OPENAI_API_KEY is not configured")
        if not resolved_base_url:
            raise OpenAIClientError("OPENAI_BASE_URL is not configured")

        self._settings = resolved_settings
        self._timeout_seconds = (
            float(timeout_seconds)
            if timeout_seconds is not None
            else float(resolved_settings.openai_timeout_seconds)
        )
        self._max_retries = int(max_retries) if max_retries is not None else int(resolved_settings.openai_max_retries)
        self._base_delay = float(base_delay) if base_delay is not None else float(resolved_settings.openai_base_delay)
        self._retryable_errors = (RateLimitError, TimeoutError, APIError)
        self._client = AsyncOpenAI(
            api_key=resolved_api_key,
            base_url=resolved_base_url,
            timeout=self._timeout_seconds,
        )
        self._supports_responses = hasattr(self._client, "responses")
        self._default_model = model or resolved_settings.model
        self._default_temperature = temperature if temperature is not None else resolved_settings.temperature
        self._default_max_tokens = max_tokens if max_tokens is not None else resolved_settings.max_tokens
        self._token_tracker = token_tracker

    def _get_pricing(self, model: str) -> Dict[str, float]:
        default_pricing = {"input": 1.0, "output": 3.0}
        if not model:
            return default_pricing
        model_key = model.lower()
        if model_key in self._pricing:
            return self._pricing[model_key]
        for key in sorted(self._pricing.keys(), key=len, reverse=True):
            if model_key.startswith(key):
                return self._pricing[key]
        return default_pricing

    def _calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        pricing = self._get_pricing(model)
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        return float(input_cost + output_cost)

    def _usage_to_dict(self, usage: Any) -> Optional[Dict[str, Any]]:
        if not usage:
            return None
        if isinstance(usage, dict):
            return dict(usage)
        if hasattr(usage, "model_dump"):
            try:
                dumped = usage.model_dump()
                if isinstance(dumped, dict):
                    return dumped
            except Exception:
                pass
        data: Dict[str, Any] = {}
        for key in ("prompt_tokens", "completion_tokens", "total_tokens", "input_tokens", "output_tokens"):
            value = getattr(usage, key, None)
            if value is not None:
                data[key] = value
        return data or None

    def _build_usage(self, model: str, usage: Any) -> Optional[TokenUsage]:
        usage_data = self._usage_to_dict(usage)
        if not usage_data:
            return None
        input_tokens = int(usage_data.get("prompt_tokens", usage_data.get("input_tokens", 0)) or 0)
        output_tokens = int(usage_data.get("completion_tokens", usage_data.get("output_tokens", 0)) or 0)
        total_tokens = int(usage_data.get("total_tokens", input_tokens + output_tokens) or 0)
        cost_usd = self._calculate_cost(model, input_tokens, output_tokens)
        return TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost_usd=cost_usd,
            raw=usage_data,
        )

    def _read_attr(self, obj: Any, key: str, default: Any = None) -> Any:
        if obj is None:
            return default
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    def supports_responses(self) -> bool:
        return bool(self._supports_responses)

    def _responses_client(self) -> Any:
        responses = getattr(self._client, "responses", None)
        if responses is None:
            raise OpenAIClientError(
                "OpenAI SDK does not support the Responses API. "
                "Set OPENAI_API_MODE=chat or upgrade the openai package."
            )
        return responses

    def _normalize_input_messages(self, messages: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [dict(message) for message in messages]

    def _extract_response_text(self, response: Any) -> str:
        output_text = self._read_attr(response, "output_text")
        if callable(output_text):
            try:
                output_text = output_text()
            except Exception:
                output_text = None
        if output_text:
            return str(output_text)

        text_parts: List[str] = []
        output_items = self._read_attr(response, "output") or []
        for item in output_items:
            item_type = self._read_attr(item, "type")
            if item_type == "message":
                content_items = self._read_attr(item, "content") or []
                for content in content_items:
                    content_type = self._read_attr(content, "type")
                    if content_type in {"output_text", "text"}:
                        text = self._read_attr(content, "text") or self._read_attr(content, "value") or ""
                        if text:
                            text_parts.append(str(text))
            elif item_type in {"output_text", "text"}:
                text = self._read_attr(item, "text") or self._read_attr(item, "value") or ""
                if text:
                    text_parts.append(str(text))
        return "".join(text_parts)

    def _extract_response_tool_calls(self, response: Any) -> List[ChatCompletionMessageToolCall]:
        tool_calls: List[ChatCompletionMessageToolCall] = []
        output_items = self._read_attr(response, "output") or []
        for item in output_items:
            item_type = self._read_attr(item, "type")
            if item_type not in {"function_call", "tool_call", "custom_tool_call"}:
                continue
            name = self._read_attr(item, "name") or self._read_attr(item, "tool_name")
            arguments = self._read_attr(item, "arguments")
            if arguments is None:
                arguments = self._read_attr(item, "input")
            call_id = self._read_attr(item, "call_id") or self._read_attr(item, "id")
            if not call_id:
                call_id = f"call_{len(tool_calls) + 1}"
            if not isinstance(arguments, str):
                try:
                    arguments = json.dumps(arguments or {}, ensure_ascii=True)
                except TypeError:
                    arguments = str(arguments or "")
            tool_calls.append(
                ChatCompletionMessageToolCall(
                    id=call_id,
                    type="function",
                    function={"name": name or "unknown", "arguments": arguments or ""},
                )
            )
        return tool_calls

    def _normalize_tools(self, tools: Optional[Sequence[Any]]) -> Optional[List[ChatCompletionToolParam]]:
        if not tools:
            return None
        normalized: List[ChatCompletionToolParam] = []
        for tool in tools:
            if hasattr(tool, "to_openai_format"):
                normalized.append(tool.to_openai_format())
            else:
                normalized.append(tool)
        return normalized

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Any]] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        resolved_model = model or self._default_model
        payload = {
            "model": resolved_model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self._default_temperature,
            "max_tokens": max_tokens if max_tokens is not None else self._default_max_tokens,
        }
        normalized_tools = self._normalize_tools(tools)
        if normalized_tools is not None:
            payload["tools"] = normalized_tools
        payload.update(kwargs)

        async def _request() -> Any:
            try:
                return await self._client.chat.completions.create(**payload)
            except Exception as exc:  # pragma: no cover - relies on SDK
                raise self._handle_error(exc) from exc

        response = await with_retry(
            _request,
            max_retries=self._max_retries,
            base_delay=self._base_delay,
            retry_on=self._retryable_errors,
        )

        content = ""
        tool_calls: Optional[List[ChatCompletionMessageToolCall]] = None
        if response.choices:
            message = response.choices[0].message
            content = message.content or ""
            tool_calls = message.tool_calls
        token_usage = self._build_usage(resolved_model, response.usage)
        return LLMResponse(content=content, tool_calls=tool_calls, token_usage=token_usage)

    async def chat_completion_stream(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream_options: Optional[dict] = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        resolved_model = model or self._default_model
        payload = {
            "model": resolved_model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self._default_temperature,
            "max_tokens": max_tokens if max_tokens is not None else self._default_max_tokens,
            "stream": True,
        }
        if stream_options is not None:
            payload["stream_options"] = stream_options
        payload.update(kwargs)

        async def _create_stream() -> Any:
            try:
                return await self._client.chat.completions.create(**payload)
            except Exception as exc:  # pragma: no cover - relies on SDK
                raise self._handle_error(exc) from exc

        attempts = max(1, int(self._max_retries))
        for attempt in range(1, attempts + 1):
            yielded_any = False
            try:
                stream = await _create_stream()
                async for chunk in stream:
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta
                    if delta is None:
                        continue
                    if getattr(delta, "content", None):
                        yielded_any = True
                        yield delta.content
                return
            except Exception as exc:  # pragma: no cover - depends on streaming
                handled = exc if isinstance(exc, OpenAIClientError) else self._handle_error(exc)
                retryable = isinstance(handled, self._retryable_errors)
                if not retryable or yielded_any or attempt >= attempts:
                    raise handled
                delay = float(self._base_delay) * (2 ** (attempt - 1))
                logger.warning(
                    "Attempt %s/%s failed: %s. Retrying in %.2fs...",
                    attempt,
                    attempts,
                    handled,
                    delay,
                )
                await asyncio.sleep(delay)

    def _build_responses_payload(
        self,
        *,
        input_items: Sequence[Dict[str, Any]],
        model: str,
        temperature: Optional[float],
        max_tokens: Optional[int],
        max_output_tokens: Optional[int],
        tools: Optional[List[Any]],
        reasoning_effort: Optional[str],
        extra: Dict[str, Any],
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": model,
            "input": list(input_items),
            "temperature": temperature if temperature is not None else self._default_temperature,
        }
        resolved_max_output = (
            max_output_tokens
            if max_output_tokens is not None
            else (max_tokens if max_tokens is not None else self._default_max_tokens)
        )
        if resolved_max_output is not None and "max_output_tokens" not in extra:
            payload["max_output_tokens"] = resolved_max_output
        normalized_tools = self._normalize_tools(tools)
        if normalized_tools is not None:
            payload["tools"] = normalized_tools
        if reasoning_effort and "reasoning" not in extra:
            payload["reasoning"] = {"effort": reasoning_effort}
        payload.update(extra)
        return payload

    async def responses_create(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        max_output_tokens: Optional[int] = None,
        tools: Optional[List[Any]] = None,
        reasoning_effort: Optional[str] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        resolved_model = model or self._default_model
        payload = self._build_responses_payload(
            input_items=self._normalize_input_messages(messages),
            model=resolved_model,
            temperature=temperature,
            max_tokens=max_tokens,
            max_output_tokens=max_output_tokens,
            tools=tools,
            reasoning_effort=reasoning_effort,
            extra=dict(kwargs),
        )
        responses = self._responses_client()

        async def _request() -> Any:
            try:
                return await responses.create(**payload)
            except Exception as exc:  # pragma: no cover - relies on SDK
                raise self._handle_error(exc) from exc

        response = await with_retry(
            _request,
            max_retries=self._max_retries,
            base_delay=self._base_delay,
            retry_on=self._retryable_errors,
        )

        content = self._extract_response_text(response)
        tool_calls = self._extract_response_tool_calls(response) or None
        token_usage = self._build_usage(resolved_model, self._read_attr(response, "usage"))
        return LLMResponse(content=content, tool_calls=tool_calls, token_usage=token_usage)

    async def responses_stream(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        max_output_tokens: Optional[int] = None,
        stream_options: Optional[dict] = None,
        reasoning_effort: Optional[str] = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        resolved_model = model or self._default_model
        base_payload = self._build_responses_payload(
            input_items=self._normalize_input_messages(messages),
            model=resolved_model,
            temperature=temperature,
            max_tokens=max_tokens,
            max_output_tokens=max_output_tokens,
            tools=None,
            reasoning_effort=reasoning_effort,
            extra=dict(kwargs),
        )
        if stream_options is not None:
            base_payload["stream_options"] = stream_options
        responses = self._responses_client()

        async def _create_stream() -> Any:
            try:
                if hasattr(responses, "stream"):
                    payload = dict(base_payload)
                    payload.pop("stream", None)
                    return responses.stream(**payload)
                payload = dict(base_payload)
                payload["stream"] = True
                return await responses.create(**payload)
            except Exception as exc:  # pragma: no cover - relies on SDK
                raise self._handle_error(exc) from exc

        attempts = max(1, int(self._max_retries))
        for attempt in range(1, attempts + 1):
            yielded_any = False
            try:
                stream = await _create_stream()
                if hasattr(stream, "__aenter__"):
                    async with stream as active_stream:
                        async for event in active_stream:
                            event_type = self._read_attr(event, "type") or ""
                            if event_type == "response.output_text.delta":
                                delta = self._read_attr(event, "delta")
                                if isinstance(delta, dict):
                                    delta = delta.get("text") or delta.get("value") or delta.get("content")
                                if delta:
                                    yielded_any = True
                                    yield str(delta)
                    return
                async for event in stream:
                    event_type = self._read_attr(event, "type") or ""
                    if event_type == "response.output_text.delta":
                        delta = self._read_attr(event, "delta")
                        if isinstance(delta, dict):
                            delta = delta.get("text") or delta.get("value") or delta.get("content")
                        if delta:
                            yielded_any = True
                            yield str(delta)
                return
            except Exception as exc:  # pragma: no cover - depends on streaming
                handled = exc if isinstance(exc, OpenAIClientError) else self._handle_error(exc)
                retryable = isinstance(handled, self._retryable_errors)
                if not retryable or yielded_any or attempt >= attempts:
                    raise handled
                delay = float(self._base_delay) * (2 ** (attempt - 1))
                logger.warning(
                    "Attempt %s/%s failed: %s. Retrying in %.2fs...",
                    attempt,
                    attempts,
                    handled,
                    delay,
                )
                await asyncio.sleep(delay)

    async def responses_with_tools(
        self,
        messages: List[Dict[str, str]],
        tools: List[Any],
        tool_handlers: Dict[str, Callable[..., Any]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        max_output_tokens: Optional[int] = None,
        max_iterations: int = 10,
        reasoning_effort: Optional[str] = None,
        parallel_tools: bool = True,
        **kwargs: Any,
    ) -> LLMResponse:
        resolved_model = model or self._default_model
        total_input = 0
        total_output = 0
        total_cost = 0.0
        raw_usage: List[Dict[str, Any]] = []
        last_response: Optional[Any] = None
        final_text_parts: List[str] = []
        previous_response_id: Optional[str] = None

        base_payload = self._build_responses_payload(
            input_items=self._normalize_input_messages(messages),
            model=resolved_model,
            temperature=temperature,
            max_tokens=max_tokens,
            max_output_tokens=max_output_tokens,
            tools=tools,
            reasoning_effort=reasoning_effort,
            extra=dict(kwargs),
        )
        responses = self._responses_client()
        fallback_input = list(base_payload.get("input") or [])

        for _ in range(max_iterations):
            payload = dict(base_payload)
            if previous_response_id:
                payload["previous_response_id"] = previous_response_id
                payload["input"] = payload.get("input") or []

            async def _request() -> Any:
                try:
                    return await responses.create(**payload)
                except Exception as exc:  # pragma: no cover - relies on SDK
                    raise self._handle_error(exc) from exc

            response = await with_retry(
                _request,
                max_retries=self._max_retries,
                base_delay=self._base_delay,
                retry_on=self._retryable_errors,
            )
            last_response = response
            previous_response_id = self._read_attr(response, "id") or previous_response_id

            usage = self._build_usage(resolved_model, self._read_attr(response, "usage"))
            if usage:
                total_input += usage.input_tokens
                total_output += usage.output_tokens
                total_cost += usage.cost_usd
                if usage.raw:
                    raw_usage.append(usage.raw)

            content = self._extract_response_text(response)
            if content:
                final_text_parts.append(content)

            tool_calls = self._extract_response_tool_calls(response)
            if not tool_calls:
                break

            if parallel_tools and len(tool_calls) > 1:
                results = await asyncio.gather(
                    *(self._execute_tool_call(tool_call, tool_handlers) for tool_call in tool_calls)
                )
            else:
                results = []
                for tool_call in tool_calls:
                    results.append(await self._execute_tool_call(tool_call, tool_handlers))

            tool_outputs: List[Dict[str, Any]] = []
            for tool_call, tool_result in zip(tool_calls, results):
                tool_outputs.append(
                    {
                        "type": "function_call_output",
                        "call_id": tool_call.id,
                        "output": json.dumps(tool_result, ensure_ascii=True),
                    }
                )
            if previous_response_id:
                base_payload["input"] = tool_outputs
            else:
                fallback_input = list(fallback_input) + tool_outputs
                base_payload["input"] = fallback_input

        token_usage: Optional[TokenUsage] = None
        if total_input or total_output:
            token_usage = TokenUsage(
                input_tokens=total_input,
                output_tokens=total_output,
                total_tokens=total_input + total_output,
                cost_usd=total_cost,
                raw={"steps": raw_usage} if raw_usage else None,
            )
        final_content = "".join(final_text_parts) if final_text_parts else ""
        if last_response is None:
            return LLMResponse(content=final_content, tool_calls=None, token_usage=token_usage)
        return LLMResponse(
            content=final_content or self._extract_response_text(last_response),
            tool_calls=self._extract_response_tool_calls(last_response) or None,
            token_usage=token_usage,
        )

    async def chat_with_tools(
        self,
        messages: List[Dict[str, str]],
        tools: List[Any],
        tool_handlers: Dict[str, Callable[..., Any]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_iterations: int = 10,
        **kwargs: Any,
    ) -> LLMResponse:
        history: List[Dict[str, Any]] = list(messages)
        total_input = 0
        total_output = 0
        total_cost = 0.0
        last_response: Optional[LLMResponse] = None

        for _ in range(max_iterations):
            response = await self.chat_completion(
                history,
                model=model,
                temperature=temperature,
                tools=tools,
                **kwargs,
            )
            last_response = response
            if response.token_usage:
                total_input += response.token_usage.input_tokens
                total_output += response.token_usage.output_tokens
                total_cost += response.token_usage.cost_usd

            tool_calls = response.tool_calls or []
            if not tool_calls:
                break

            assistant_message = {
                "role": "assistant",
                "content": response.content or "",
                "tool_calls": [tool_call.model_dump() for tool_call in tool_calls],
            }
            history.append(assistant_message)

            for tool_call in tool_calls:
                tool_result = await self._execute_tool_call(tool_call, tool_handlers)
                history.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(tool_result, ensure_ascii=True),
                    }
                )
        token_usage: Optional[TokenUsage] = None
        if total_input or total_output:
            token_usage = TokenUsage(
                input_tokens=total_input,
                output_tokens=total_output,
                total_tokens=total_input + total_output,
                cost_usd=total_cost,
            )
        if last_response is None:
            return LLMResponse(content="", tool_calls=None, token_usage=token_usage)
        return LLMResponse(
            content=last_response.content,
            tool_calls=last_response.tool_calls,
            token_usage=token_usage,
        )

    async def _execute_tool_call(
        self,
        tool_call: ChatCompletionMessageToolCall,
        tool_handlers: Dict[str, Callable[..., Any]],
    ) -> Dict[str, Any]:
        tool_name = tool_call.function.name
        handler = tool_handlers.get(tool_name)
        if handler is None:
            return {
                "success": False,
                "output": None,
                "error": f"No handler registered for tool '{tool_name}'",
            }
        try:
            arguments = tool_call.function.arguments
            parsed_args: Any = json.loads(arguments) if arguments else {}
        except json.JSONDecodeError as exc:
            return {"success": False, "output": None, "error": f"Invalid JSON arguments: {exc}"}

        try:
            result = await self._invoke_handler(handler, parsed_args)
            if hasattr(result, "to_dict"):
                return result.to_dict()
            if isinstance(result, dict) and "success" in result:
                return result
            return {"success": True, "output": result}
        except Exception as exc:  # pragma: no cover - depends on handler
            return {"success": False, "output": None, "error": str(exc)}

    async def _invoke_handler(self, handler: Callable[..., Any], parsed_args: Any) -> Any:
        if isinstance(parsed_args, dict):
            try:
                result = handler(**parsed_args)
            except TypeError:
                result = handler(parsed_args)
        else:
            result = handler(parsed_args)
        if inspect.isawaitable(result):
            return await result
        return result

    def _handle_error(self, exc: Exception) -> OpenAIClientError:
        code, message = self._extract_error_details(exc)
        if isinstance(exc, openai.RateLimitError):
            return RateLimitError(message or "Rate limit exceeded")
        if isinstance(exc, openai.AuthenticationError):
            return AuthenticationError(message or "Authentication failed")
        if isinstance(exc, (openai.APITimeoutError, httpx.TimeoutException)):
            return TimeoutError(message or "Request timed out")
        if isinstance(exc, openai.BadRequestError):
            if self._is_context_length_error(code, message):
                return ContextLengthError(message or "Context length exceeded")
            return OpenAIClientError(message or "Bad request")
        if isinstance(
            exc,
            (
                openai.PermissionDeniedError,
                openai.NotFoundError,
                openai.ConflictError,
                openai.UnprocessableEntityError,
            ),
        ):
            return OpenAIClientError(message or str(exc))
        if isinstance(exc, (openai.APIConnectionError, openai.APIResponseValidationError)):
            return APIError(message or str(exc))
        if isinstance(exc, (openai.InternalServerError, openai.APIStatusError, openai.APIError)):
            return APIError(message or str(exc))
        return APIError(str(exc))

    def _extract_error_details(self, exc: Exception) -> tuple[Optional[str], str]:
        message = str(exc)
        code: Optional[str] = None
        body = getattr(exc, "body", None)
        if isinstance(body, dict):
            error = body.get("error")
            if isinstance(error, dict):
                code = error.get("code") or error.get("type")
                message = error.get("message") or message
        elif isinstance(body, str) and body:
            message = body
        return code, message

    def _is_context_length_error(self, code: Optional[str], message: str) -> bool:
        if code and code.lower() in {"context_length_exceeded", "context_length"}:
            return True
        lower = message.lower()
        if "maximum context length" in lower:
            return True
        return "context length" in lower and "exceed" in lower


__all__ = [
    "APIError",
    "AuthenticationError",
    "ContextLengthError",
    "LLMResponse",
    "OpenAIClient",
    "OpenAIClientError",
    "RateLimitError",
    "TimeoutError",
    "TokenUsage",
]
