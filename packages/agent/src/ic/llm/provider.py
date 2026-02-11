"""LLM provider using OpenAI-compatible API."""

from __future__ import annotations

import asyncio
import httpx
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from openai import AsyncOpenAI

from ic.config import ModelConfig


@dataclass
class Message:
    """A conversation message."""

    role: str  # system, user, assistant, tool
    content: str | list[dict[str, Any]] | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None
    name: str | None = None
    reasoning_content: str | None = None
    cache_control: dict[str, str] | None = None  # e.g. {"type": "ephemeral"}

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"role": self.role}
        if self.content is not None:
            # If cache_control is set, wrap content in content blocks format
            if self.cache_control and isinstance(self.content, str):
                d["content"] = [
                    {
                        "type": "text",
                        "text": self.content,
                        "cache_control": self.cache_control,
                    }
                ]
            else:
                d["content"] = self.content
        if self.tool_calls is not None:
            d["tool_calls"] = self.tool_calls
        if self.tool_call_id is not None:
            d["tool_call_id"] = self.tool_call_id
        if self.name is not None:
            d["name"] = self.name
        if self.reasoning_content is not None:
            d["reasoning_content"] = self.reasoning_content
        return d


def _clean_messages_for_api(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Strip Anthropic-specific fields from messages for OpenAI-compatible APIs.

    - Removes ``cache_control`` from content blocks (Anthropic prompt caching).
    - Unwraps single-element content block arrays back to plain strings.
    - Preserves ``reasoning_content`` — required by some proxies (e.g. DMXAPI)
      when thinking mode is enabled.
    """
    import logging
    _log = logging.getLogger("ic.llm")
    _stripped_count = 0
    cleaned: list[dict[str, Any]] = []
    for msg in messages:
        m = dict(msg)

        # Clean content blocks: strip cache_control and unwrap if possible
        content = m.get("content")
        if isinstance(content, list):
            new_blocks = []
            for block in content:
                if isinstance(block, dict):
                    if "cache_control" in block:
                        _stripped_count += 1
                    b = {k: v for k, v in block.items() if k != "cache_control"}
                    new_blocks.append(b)
                else:
                    new_blocks.append(block)
            # Unwrap single text block back to plain string
            if (
                len(new_blocks) == 1
                and isinstance(new_blocks[0], dict)
                and new_blocks[0].get("type") == "text"
            ):
                m["content"] = new_blocks[0]["text"]
            else:
                m["content"] = new_blocks

        cleaned.append(m)
    if _stripped_count:
        _log.debug("cleaned %d cache_control fields from %d messages", _stripped_count, len(messages))
    return cleaned


class LLMProvider:
    """OpenAI-compatible LLM provider with streaming support."""

    def __init__(self, config: ModelConfig, timeout: float = 120.0):
        self.config = config
        self.timeout = timeout
        self._client = AsyncOpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
            timeout=httpx.Timeout(timeout),
        )
        self._active_stream: Any = None  # For cancellation

    async def chat(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        stream: bool = True,
        **kwargs: Any,
    ) -> AsyncIterator[dict[str, Any]]:
        """Send messages to LLM and yield streaming chunks.

        Yields dicts with keys: type (text_delta|tool_call_delta|done), data.
        """
        raw_msgs = [m.to_dict() for m in messages]
        # Strip non-standard fields that OpenAI-compatible proxies don't understand.
        # cache_control (Anthropic-specific) and reasoning_content (thinking models)
        # can cause DMXAPI and similar proxies to return empty responses.
        cleaned = _clean_messages_for_api(raw_msgs)

        params: dict[str, Any] = {
            "model": self.config.model,
            "messages": cleaned,
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "temperature": kwargs.get("temperature", self.config.temperature),
            "stream": stream,
        }
        if tools:
            params["tools"] = tools
            params["tool_choice"] = "auto"

        if stream:
            async for chunk in self._stream_chat(params):
                yield chunk
        else:
            response = await self._create_chat_completion(params)
            choice = response.choices[0]
            if choice.message.content:
                yield {"type": "text", "data": choice.message.content}
            if choice.message.tool_calls:
                for tc in choice.message.tool_calls:
                    yield {
                        "type": "tool_call",
                        "data": {
                            "id": tc.id,
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
            yield {
                "type": "done",
                "data": {
                    "usage": {
                        "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                        "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    },
                    "finish_reason": choice.finish_reason,
                    "reasoning_content": getattr(choice.message, "reasoning_content", None),
                },
            }

    async def _create_chat_completion(self, params: dict[str, Any]) -> Any:
        try:
            return await self._client.chat.completions.create(**params)
        except Exception as error:
            if self._should_retry_with_temperature_one(error, params):
                retry_params = dict(params)
                retry_params["temperature"] = 1
                return await self._client.chat.completions.create(**retry_params)
            raise

    @staticmethod
    def _should_retry_with_temperature_one(error: Exception, params: dict[str, Any]) -> bool:
        current_temperature = params.get("temperature")
        if current_temperature in (1, 1.0):
            return False
        message = str(error).lower()
        return (
            "invalid temperature" in message
            and "only 1" in message
            and "allowed" in message
        )

    async def _stream_chat(self, params: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
        """Handle streaming response from OpenAI-compatible API."""
        stream = await self._create_chat_completion(params)
        self._active_stream = stream
        tool_calls_acc: dict[int, dict[str, Any]] = {}
        text_acc = ""
        reasoning_acc = ""
        _chunk_count = 0
        _got_finish = False

        try:
            async for chunk in stream:
                _chunk_count += 1
                delta = chunk.choices[0].delta if chunk.choices else None
                finish_reason = chunk.choices[0].finish_reason if chunk.choices else None

                reasoning_delta = getattr(delta, "reasoning_content", None) if delta else None
                if reasoning_delta:
                    reasoning_acc += reasoning_delta
                    yield {"type": "reasoning_delta", "data": reasoning_delta}

                if delta and delta.content:
                    text_acc += delta.content
                    yield {"type": "text_delta", "data": delta.content}

                if delta and delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        idx = tc_delta.index
                        if idx not in tool_calls_acc:
                            tool_calls_acc[idx] = {
                                "id": tc_delta.id or "",
                                "name": tc_delta.function.name if tc_delta.function and tc_delta.function.name else "",
                                "arguments": "",
                            }
                        else:
                            if tc_delta.id:
                                tool_calls_acc[idx]["id"] = tc_delta.id
                            if tc_delta.function and tc_delta.function.name:
                                tool_calls_acc[idx]["name"] = tc_delta.function.name
                        if tc_delta.function and tc_delta.function.arguments:
                            tool_calls_acc[idx]["arguments"] += tc_delta.function.arguments

                if finish_reason:
                    _got_finish = True
                    # Emit accumulated text
                    if text_acc:
                        yield {"type": "text", "data": text_acc}
                    # Emit accumulated tool calls
                    for idx in sorted(tool_calls_acc.keys()):
                        yield {"type": "tool_call", "data": tool_calls_acc[idx]}
                    # Done
                    usage_data = {}
                    if hasattr(chunk, "usage") and chunk.usage:
                        usage_data = {
                            "prompt_tokens": chunk.usage.prompt_tokens,
                            "completion_tokens": chunk.usage.completion_tokens,
                        }
                    yield {
                        "type": "done",
                        "data": {
                            "usage": usage_data,
                            "finish_reason": finish_reason,
                            "reasoning_content": reasoning_acc or None,
                        },
                    }

            # Stream ended without a finish_reason chunk — emit done anyway
            # so the engine doesn't hang waiting for it.
            if not _got_finish:
                import logging
                logging.getLogger("ic.llm").warning(
                    "stream_no_finish chunks=%d text=%d reasoning=%d tools=%d",
                    _chunk_count, len(text_acc), len(reasoning_acc),
                    len(tool_calls_acc),
                )
                if text_acc:
                    yield {"type": "text", "data": text_acc}
                for idx in sorted(tool_calls_acc.keys()):
                    yield {"type": "tool_call", "data": tool_calls_acc[idx]}
                yield {
                    "type": "done",
                    "data": {
                        "usage": {},
                        "finish_reason": "stop",
                        "reasoning_content": reasoning_acc or None,
                    },
                }

            # Log diagnostic when stream produced no content at all
            if not text_acc and not tool_calls_acc and not reasoning_acc:
                import logging
                logging.getLogger("ic.llm").warning(
                    "stream_empty chunks=%d model=%s — "
                    "the model returned no text, no tool calls, no reasoning",
                    _chunk_count, params.get("model", "?"),
                )
        finally:
            self._active_stream = None

    async def cancel_stream(self):
        """Cancel the active streaming response."""
        if self._active_stream is not None:
            try:
                await self._active_stream.close()
            except Exception:
                pass
            self._active_stream = None


def create_provider(config: ModelConfig) -> LLMProvider:
    """Factory to create an LLM provider from config."""
    return LLMProvider(config, timeout=config.timeout)
