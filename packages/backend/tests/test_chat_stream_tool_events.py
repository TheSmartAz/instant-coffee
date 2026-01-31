import json

from fastapi.testclient import TestClient

from app.agents.generation import GenerationAgent, GenerationResult
from app.events.models import ToolCallEvent, ToolResultEvent
import app.db.database as db_module


def test_chat_stream_emits_tool_events(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("DEFAULT_BASE_URL", "http://localhost")
    monkeypatch.setenv("DEFAULT_KEY", "test-key")
    monkeypatch.setattr(db_module, "_database", None)

    async def fake_generate(
        self,
        *,
        requirements,
        output_dir,
        history,
        current_html=None,
        stream=True,
    ):
        if self.event_emitter:
            self.event_emitter.emit(
                ToolCallEvent(
                    agent_id=self.agent_id or "generation_1",
                    agent_type=self.agent_type,
                    tool_name="dummy",
                    tool_input={"path": "index.html"},
                )
            )
            self.event_emitter.emit(
                ToolResultEvent(
                    agent_id=self.agent_id or "generation_1",
                    agent_type=self.agent_type,
                    tool_name="dummy",
                    success=True,
                    tool_output={"ok": True},
                )
            )
        return GenerationResult(
            html="<p>ok</p>",
            preview_url="file://preview",
            filepath="/tmp/index.html",
        )

    monkeypatch.setattr(GenerationAgent, "generate", fake_generate)

    from app.main import create_app

    app = create_app()

    with TestClient(app) as client:
        with client.stream("GET", "/api/chat/stream?message=hi") as response:
            lines = []
            for line in response.iter_lines():
                if not line:
                    continue
                decoded = line.decode() if isinstance(line, bytes) else line
                lines.append(decoded)

    payloads = []
    for line in lines:
        if not line.startswith("data:") or "[DONE]" in line:
            continue
        raw = line.replace("data:", "").strip()
        payloads.append(json.loads(raw))

    types = [payload.get("type") for payload in payloads if "type" in payload]
    assert "tool_call" in types
    assert "tool_result" in types
    assert types.index("tool_call") < types.index("tool_result")


def test_chat_stream_multiple_tool_calls_order(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("DEFAULT_BASE_URL", "http://localhost")
    monkeypatch.setenv("DEFAULT_KEY", "test-key")
    monkeypatch.setattr(db_module, "_database", None)

    async def fake_generate(
        self,
        *,
        requirements,
        output_dir,
        history,
        current_html=None,
        stream=True,
    ):
        if self.event_emitter:
            self.event_emitter.emit(
                ToolCallEvent(
                    agent_id=self.agent_id or "generation_1",
                    agent_type=self.agent_type,
                    tool_name="first",
                    tool_input={"path": "index.html"},
                )
            )
            self.event_emitter.emit(
                ToolResultEvent(
                    agent_id=self.agent_id or "generation_1",
                    agent_type=self.agent_type,
                    tool_name="first",
                    success=True,
                    tool_output={"ok": True},
                )
            )
            self.event_emitter.emit(
                ToolCallEvent(
                    agent_id=self.agent_id or "generation_1",
                    agent_type=self.agent_type,
                    tool_name="second",
                    tool_input={"path": "index.html"},
                )
            )
            self.event_emitter.emit(
                ToolResultEvent(
                    agent_id=self.agent_id or "generation_1",
                    agent_type=self.agent_type,
                    tool_name="second",
                    success=True,
                    tool_output={"ok": True},
                )
            )
        return GenerationResult(
            html="<p>ok</p>",
            preview_url="file://preview",
            filepath="/tmp/index.html",
        )

    monkeypatch.setattr(GenerationAgent, "generate", fake_generate)

    from app.main import create_app

    app = create_app()

    with TestClient(app) as client:
        with client.stream("GET", "/api/chat/stream?message=hi") as response:
            lines = []
            for line in response.iter_lines():
                if not line:
                    continue
                decoded = line.decode() if isinstance(line, bytes) else line
                lines.append(decoded)

    payloads = []
    for line in lines:
        if not line.startswith("data:") or "[DONE]" in line:
            continue
        raw = line.replace("data:", "").strip()
        payloads.append(json.loads(raw))

    tool_events = [payload for payload in payloads if payload.get("type") in {"tool_call", "tool_result"}]
    names = [event.get("tool_name") for event in tool_events]
    assert names == ["first", "first", "second", "second"]
    assert tool_events[0]["type"] == "tool_call"
    assert tool_events[1]["type"] == "tool_result"
    assert tool_events[2]["type"] == "tool_call"
    assert tool_events[3]["type"] == "tool_result"
