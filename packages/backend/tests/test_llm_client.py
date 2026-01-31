import asyncio
import math

import httpx
import openai

from app.llm.openai_client import (
    APIError,
    AuthenticationError,
    ContextLengthError,
    LLMResponse,
    OpenAIClient,
    RateLimitError,
    TimeoutError,
    TokenUsage,
)
from openai.types.chat import ChatCompletionMessageToolCall


class DummyMessage:
    def __init__(self, content, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls


class DummyDelta:
    def __init__(self, content):
        self.content = content


class DummyChoice:
    def __init__(self, message=None, delta=None):
        self.message = message
        self.delta = delta


class DummyUsage:
    def __init__(self, prompt_tokens, completion_tokens, total_tokens):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens


class DummyResponse:
    def __init__(self, message, usage):
        self.choices = [DummyChoice(message=message)]
        self.usage = usage


class DummyChunk:
    def __init__(self, content):
        self.choices = [DummyChoice(delta=DummyDelta(content))]


class DummyStream:
    def __init__(self, chunks):
        self._chunks = list(chunks)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._chunks:
            raise StopAsyncIteration
        return self._chunks.pop(0)


class DummyCompletions:
    def __init__(self, response=None, stream=None):
        self._response = response
        self._stream = stream

    async def create(self, **kwargs):
        if kwargs.get("stream"):
            return self._stream
        return self._response


class DummyChat:
    def __init__(self, completions):
        self.completions = completions


class DummyClient:
    def __init__(self, response=None, stream=None):
        self.chat = DummyChat(DummyCompletions(response=response, stream=stream))


def test_pricing_lookup_exact_and_prefix():
    client = OpenAIClient(api_key="test", base_url="http://localhost")
    exact = client._get_pricing("gpt-4o")
    assert exact == {"input": 5.0, "output": 15.0}

    prefix = client._get_pricing("gpt-4o-mini-2024-07-18")
    assert prefix == {"input": 0.15, "output": 0.60}


def test_cost_calculation():
    client = OpenAIClient(api_key="test", base_url="http://localhost")
    cost = client._calculate_cost("gpt-4o", input_tokens=1000, output_tokens=2000)
    assert math.isclose(cost, 0.035, rel_tol=1e-6)


def test_error_classification():
    client = OpenAIClient(api_key="test", base_url="http://localhost")
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    response = httpx.Response(429, request=request)
    rate_err = openai.RateLimitError("rate", response=response, body=None)
    assert isinstance(client._handle_error(rate_err), RateLimitError)

    response = httpx.Response(401, request=request)
    auth_err = openai.AuthenticationError("auth", response=response, body=None)
    auth = client._handle_error(auth_err)
    assert isinstance(auth, AuthenticationError)
    assert "auth" in str(auth).lower() or "authentication" in str(auth).lower()

    timeout_err = openai.APITimeoutError("timeout")
    timeout = client._handle_error(timeout_err)
    assert isinstance(timeout, TimeoutError)
    assert "timeout" in str(timeout).lower() or "timed out" in str(timeout).lower()

    response = httpx.Response(400, request=request)
    body = {"error": {"code": "context_length_exceeded", "message": "Context length exceeded"}}
    bad_request = openai.BadRequestError("bad request", response=response, body=body)
    ctx_err = client._handle_error(bad_request)
    assert isinstance(ctx_err, ContextLengthError)


def test_chat_completion_parses_usage():
    client = OpenAIClient(api_key="test", base_url="http://localhost", model="gpt-4o-mini")
    response = DummyResponse(
        DummyMessage("hello"),
        DummyUsage(prompt_tokens=12, completion_tokens=8, total_tokens=20),
    )
    client._client = DummyClient(response=response)

    result = asyncio.run(client.chat_completion(messages=[{"role": "user", "content": "hi"}]))

    assert result.content == "hello"
    assert result.token_usage
    assert result.token_usage.input_tokens == 12
    assert result.token_usage.output_tokens == 8
    assert result.token_usage.total_tokens == 20


def test_chat_completion_stream_yields_chunks():
    client = OpenAIClient(api_key="test", base_url="http://localhost")
    stream = DummyStream([DummyChunk("hello"), DummyChunk(" "), DummyChunk("world")])
    client._client = DummyClient(stream=stream)

    async def collect():
        chunks = []
        async for chunk in client.chat_completion_stream(
            messages=[{"role": "user", "content": "hi"}],
        ):
            chunks.append(chunk)
        return "".join(chunks)

    output = asyncio.run(collect())
    assert output == "hello world"


def test_chat_with_tools_executes_handlers_and_accumulates_usage():
    client = OpenAIClient(api_key="test", base_url="http://localhost")
    tool_call = ChatCompletionMessageToolCall(
        id="call_1",
        type="function",
        function={"name": "test_tool", "arguments": "{\"foo\": \"bar\"}"},
    )

    responses = [
        LLMResponse(
            content="",
            tool_calls=[tool_call],
            token_usage=TokenUsage(input_tokens=5, output_tokens=3, total_tokens=8, cost_usd=0.0),
        ),
        LLMResponse(
            content="done",
            tool_calls=None,
            token_usage=TokenUsage(input_tokens=7, output_tokens=2, total_tokens=9, cost_usd=0.0),
        ),
    ]
    calls = []

    async def fake_chat_completion(messages, **kwargs):
        calls.append(list(messages))
        return responses[len(calls) - 1]

    client.chat_completion = fake_chat_completion

    captured = []

    async def handler(foo=None):
        captured.append(foo)
        return {"success": True, "output": {"ok": True}}

    result = asyncio.run(
        client.chat_with_tools(
            messages=[{"role": "user", "content": "hi"}],
            tools=[{"type": "function", "function": {"name": "test_tool", "parameters": {}}}],
            tool_handlers={"test_tool": handler},
        )
    )

    assert captured == ["bar"]
    assert result.content == "done"
    assert result.token_usage
    assert result.token_usage.input_tokens == 12
    assert result.token_usage.output_tokens == 5
    assert result.token_usage.total_tokens == 17

    assert len(calls) == 2
    tool_messages = [message for message in calls[1] if message.get("role") == "tool"]
    assert tool_messages
    assert tool_messages[0]["tool_call_id"] == "call_1"
