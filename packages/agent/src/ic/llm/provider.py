"""LLM provider using OpenAI-compatible API."""

from __future__ import annotations

import asyncio
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

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"role": self.role}
        if self.content is not None:
            d["content"] = self.content
        if self.tool_calls is not None:
            d["tool_calls"] = self.tool_calls
        if self.tool_call_id is not None:
            d["tool_call_id"] = self.tool_call_id
        if self.name is not None:
            d["name"] = self.name
        return d


class LLMProvider:
    """OpenAI-compatible LLM provider with streaming support."""

    def __init__(self, config: ModelConfig):
        self.config = config
        self._client = AsyncOpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
        )

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
        params: dict[str, Any] = {
            "model": self.config.model,
            "messages": [m.to_dict() for m in messages],
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
            response = await self._client.chat.completions.create(**params)
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
                },
            }

    async def _stream_chat(self, params: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
        """Handle streaming response from OpenAI-compatible API."""
        import json

        stream = await self._client.chat.completions.create(**params)
        tool_calls_acc: dict[int, dict[str, Any]] = {}
        text_acc = ""

        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            finish_reason = chunk.choices[0].finish_reason if chunk.choices else None

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
                    "data": {"usage": usage_data, "finish_reason": finish_reason},
                }


def create_provider(config: ModelConfig) -> LLMProvider:
    """Factory to create an LLM provider from config."""
    return LLMProvider(config)
