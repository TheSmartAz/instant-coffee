import asyncio

from app.agents.base import BaseAgent
from app.config import Settings
from app.events.emitter import EventEmitter
from app.events.types import EventType


def test_tool_call_and_result_events_success() -> None:
    emitter = EventEmitter()
    agent = BaseAgent(
        db=None,
        session_id="session-1",
        settings=Settings(),
        event_emitter=emitter,
        agent_id="agent-1",
        task_id="task-1",
    )

    async def handler(foo: str) -> dict:
        return {"success": True, "output": {"ok": foo}}

    wrapped = agent._wrap_tool_handler("dummy_tool", handler)
    result = asyncio.run(wrapped(foo="bar"))

    events = emitter.get_events()
    assert result["success"] is True
    assert len(events) == 2

    tool_call = events[0]
    assert tool_call.type == EventType.TOOL_CALL
    assert tool_call.agent_id == "agent-1"
    assert tool_call.agent_type == "agent"
    assert tool_call.tool_name == "dummy_tool"
    assert tool_call.tool_input == {"foo": "bar"}

    tool_result = events[1]
    assert tool_result.type == EventType.TOOL_RESULT
    assert tool_result.agent_id == "agent-1"
    assert tool_result.agent_type == "agent"
    assert tool_result.tool_name == "dummy_tool"
    assert tool_result.success is True
    assert tool_result.tool_output == {"ok": "bar"}


def test_tool_result_event_failure() -> None:
    emitter = EventEmitter()
    agent = BaseAgent(
        db=None,
        session_id="session-1",
        settings=Settings(),
        event_emitter=emitter,
        agent_id="agent-1",
        task_id="task-1",
    )

    async def handler() -> dict:
        raise ValueError("boom")

    wrapped = agent._wrap_tool_handler("dummy_tool", handler)
    result = asyncio.run(wrapped())

    events = emitter.get_events()
    assert result["success"] is False
    assert result["error"] == "boom"
    assert len(events) == 2

    tool_result = events[1]
    assert tool_result.type == EventType.TOOL_RESULT
    assert tool_result.success is False
    assert tool_result.error == "boom"
