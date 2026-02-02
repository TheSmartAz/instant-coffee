import asyncio

from app.llm.openai_client import OpenAIClient


class DummyUsage:
    def __init__(self, input_tokens, output_tokens, total_tokens):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.total_tokens = total_tokens


class DummyOutputText:
    def __init__(self, text):
        self.type = "output_text"
        self.text = text


class DummyMessage:
    def __init__(self, content):
        self.type = "message"
        self.content = content


class DummyFunctionCall:
    def __init__(self, name, arguments, call_id):
        self.type = "function_call"
        self.name = name
        self.arguments = arguments
        self.call_id = call_id


class DummyResponse:
    def __init__(self, output, usage=None, response_id="resp_1"):
        self.output = output
        self.usage = usage
        self.id = response_id
        self.output_text = None


class DummyEvent:
    def __init__(self, event_type, delta=None):
        self.type = event_type
        self.delta = delta


class DummyStream:
    def __init__(self, events):
        self._events = list(events)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._events:
            raise StopAsyncIteration
        return self._events.pop(0)


class DummyResponses:
    def __init__(self, responses=None, stream=None):
        self._responses = list(responses or [])
        self._stream = stream
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get("stream"):
            return self._stream
        if not self._responses:
            raise AssertionError("No mocked responses available")
        return self._responses.pop(0)


class DummyClient:
    def __init__(self, responses):
        self.responses = responses


def test_responses_create_parses_text_and_usage():
    client = OpenAIClient(api_key="test", base_url="http://localhost", model="gpt-4o-mini")
    response = DummyResponse(
        output=[DummyMessage([DummyOutputText("hello")])],
        usage=DummyUsage(input_tokens=3, output_tokens=2, total_tokens=5),
    )
    client._client = DummyClient(responses=DummyResponses(responses=[response]))

    result = asyncio.run(client.responses_create(messages=[{"role": "user", "content": "hi"}]))

    assert result.content == "hello"
    assert result.token_usage
    assert result.token_usage.input_tokens == 3
    assert result.token_usage.output_tokens == 2
    assert result.token_usage.total_tokens == 5
    assert result.token_usage.raw["input_tokens"] == 3


def test_responses_stream_yields_deltas():
    client = OpenAIClient(api_key="test", base_url="http://localhost")
    stream = DummyStream(
        [
            DummyEvent("response.output_text.delta", "hello"),
            DummyEvent("response.output_text.delta", " "),
            DummyEvent("response.output_text.delta", "world"),
        ]
    )
    client._client = DummyClient(responses=DummyResponses(stream=stream))

    async def collect():
        chunks = []
        async for chunk in client.responses_stream(messages=[{"role": "user", "content": "hi"}]):
            chunks.append(chunk)
        return "".join(chunks)

    output = asyncio.run(collect())
    assert output == "hello world"


def test_responses_with_tools_executes_handlers_and_accumulates_usage():
    client = OpenAIClient(api_key="test", base_url="http://localhost")
    first_response = DummyResponse(
        output=[DummyFunctionCall(name="test_tool", arguments='{"foo": "bar"}', call_id="call_1")],
        usage=DummyUsage(input_tokens=4, output_tokens=1, total_tokens=5),
        response_id="resp_1",
    )
    second_response = DummyResponse(
        output=[DummyMessage([DummyOutputText("done")])],
        usage=DummyUsage(input_tokens=6, output_tokens=2, total_tokens=8),
        response_id="resp_2",
    )
    dummy_responses = DummyResponses(responses=[first_response, second_response])
    client._client = DummyClient(responses=dummy_responses)

    captured = []

    async def handler(foo=None):
        captured.append(foo)
        return {"success": True, "output": {"ok": True}}

    result = asyncio.run(
        client.responses_with_tools(
            messages=[{"role": "user", "content": "hi"}],
            tools=[{"type": "function", "function": {"name": "test_tool", "parameters": {}}}],
            tool_handlers={"test_tool": handler},
        )
    )

    assert captured == ["bar"]
    assert result.content == "done"
    assert result.token_usage
    assert result.token_usage.input_tokens == 10
    assert result.token_usage.output_tokens == 3
    assert result.token_usage.total_tokens == 13

    assert len(dummy_responses.calls) == 2
    second_call = dummy_responses.calls[1]
    assert second_call.get("previous_response_id") == "resp_1"
    input_items = second_call.get("input") or []
    assert input_items
    assert input_items[0]["type"] == "function_call_output"
    assert input_items[0]["call_id"] == "call_1"
