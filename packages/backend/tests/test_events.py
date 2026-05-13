import asyncio

import pytest

from app.events.emitter import EventEmitter
from app.events.models import (
    AgentProgressEvent,
    AgentStartEvent,
    DoneEvent,
    run_lifecycle_event,
)
from app.events.types import EventType


def test_event_model_to_sse_contains_timestamp_and_message() -> None:
    event = AgentProgressEvent(agent_id="agent-1", message="Hello", progress=10)
    payload = event.model_dump(mode="json")
    assert payload["type"] == "agent_progress"
    assert "timestamp" in payload

    sse = event.to_sse()
    assert sse.startswith("data: ")
    assert "Hello" in sse


def test_event_emitter_stream_and_events_since() -> None:
    emitter = EventEmitter()
    emitter.emit(AgentStartEvent(agent_id="agent-1", agent_type="generation"))
    emitter.emit(DoneEvent(summary="ok"))

    events, index = emitter.events_since(0)
    assert len(events) == 2
    assert index == 2

    async def collect() -> list[str]:
        return [chunk async for chunk in emitter.stream()]

    chunks = asyncio.run(collect())
    assert chunks[-1] == "data: [DONE]\n\n"


def test_run_lifecycle_event_accepts_supported_phase_metadata() -> None:
    event = run_lifecycle_event(
        EventType.RUN_STARTED,
        phase="implement",
        status="running",
        payload={"checkpoint_thread": "thread-1"},
        page=None,
    )

    assert event.type == EventType.RUN_STARTED
    assert event.payload == {
        "checkpoint_thread": "thread-1",
        "phase": "implement",
        "status": "running",
    }


def test_run_lifecycle_event_rejects_unknown_phase() -> None:
    with pytest.raises(ValueError):
        run_lifecycle_event(EventType.RUN_STARTED, phase="langgraph", status="running")
