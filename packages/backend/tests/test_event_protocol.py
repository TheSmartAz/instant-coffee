from __future__ import annotations

import asyncio

from app.agents.generation import GenerationProgress, GenerationResult
from app.agents.orchestrator import AgentOrchestrator
from app.db.database import Database
from app.db.migrations import init_db
from app.db.models import Session as SessionModel
from app.db.utils import get_db
from app.events.emitter import EventEmitter
from app.events.models import AgentProgressEvent, AgentStartEvent, DoneEvent, ToolCallEvent, ToolResultEvent
from app.events.types import EventType


def test_event_model_serialization() -> None:
    event = AgentStartEvent(agent_id="agent-1", agent_type="interview", session_id="session-1")
    payload = event.model_dump(mode="json")
    assert payload["type"] == EventType.AGENT_START.value
    assert "timestamp" in payload
    assert payload["session_id"] == "session-1"

    progress = AgentProgressEvent(agent_id="agent-1", message="中文提示")
    sse = progress.to_sse()
    assert sse.startswith("data: ")
    assert "中文提示" in sse


def test_event_emitter_emit_and_clear() -> None:
    emitter = EventEmitter()
    event = DoneEvent(summary="ok")
    emitter.emit(event)
    assert emitter.get_events() == [event]
    emitter.clear()
    assert emitter.get_events() == []


def test_orchestrator_stream_events(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "events.db"
    database = Database(f"sqlite:///{db_path}")
    init_db(database)

    class DummyGenerationAgent:
        agent_type = "generation"

        def __init__(
            self,
            db,
            session_id,
            settings,
            event_emitter=None,
            agent_id=None,
            task_id=None,
        ) -> None:
            self.event_emitter = event_emitter
            self.agent_id = agent_id or "generation_1"

        def progress_steps(self):
            return [
                GenerationProgress(message="step", progress=10),
                GenerationProgress(message="done", progress=100),
            ]

        async def generate(self, *, requirements, output_dir, history):
            if self.event_emitter:
                self.event_emitter.emit(
                    ToolCallEvent(agent_id=self.agent_id, tool_name="dummy", tool_input=None)
                )
                self.event_emitter.emit(
                    ToolResultEvent(
                        agent_id=self.agent_id,
                        tool_name="dummy",
                        success=True,
                        tool_output={"ok": True},
                    )
                )
            return GenerationResult(
                html="<p>ok</p>",
                preview_url="file://preview",
                filepath=str(tmp_path / "index.html"),
            )

    from app.agents import orchestrator as orchestrator_module

    monkeypatch.setattr(orchestrator_module, "GenerationAgent", DummyGenerationAgent)

    with get_db(database) as session:
        record = SessionModel(id="session-1", title="Test Session")
        session.add(record)
        session.flush()
        orchestrator = AgentOrchestrator(session, record)

        async def collect_events():
            events = []
            async for event in orchestrator.stream(
                user_message="hi",
                output_dir=str(tmp_path),
                skip_interview=True,
            ):
                events.append(event)
            return events

        events = asyncio.run(collect_events())

    event_types = [event.type.value for event in events]
    assert EventType.AGENT_START.value in event_types
    assert EventType.AGENT_PROGRESS.value in event_types
    assert EventType.TOOL_CALL.value in event_types
    assert EventType.TOOL_RESULT.value in event_types
    assert EventType.AGENT_END.value in event_types
    assert EventType.DONE.value in event_types
