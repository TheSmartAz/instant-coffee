import json
import uuid

import pytest
from fastapi.testclient import TestClient

import app.db.database as db_module
from app.agents.orchestrator import AgentOrchestrator, OrchestratorResponse
from app.config import refresh_settings
from app.db.models import Session as SessionModel
from app.db.models import SessionRun
from app.db.utils import get_db
from app.services.run import RunService


@pytest.fixture(autouse=True)
def _reset_chat_adapter_settings(monkeypatch):
    yield
    monkeypatch.setenv("CHAT_USE_RUN_ADAPTER", "false")
    monkeypatch.setenv("USE_LANGGRAPH", "false")
    refresh_settings()
    monkeypatch.setattr(db_module, "_database", None)


def _create_app(tmp_path, monkeypatch, *, adapter_enabled: bool):
    db_path = tmp_path / ("chat-adapter-on.db" if adapter_enabled else "chat-adapter-off.db")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("DEFAULT_BASE_URL", "http://localhost")
    monkeypatch.setenv("DEFAULT_KEY", "test-key")
    monkeypatch.setenv("USE_LANGGRAPH", "false")
    monkeypatch.setenv("CHAT_USE_RUN_ADAPTER", "true" if adapter_enabled else "false")
    refresh_settings()
    monkeypatch.setattr(db_module, "_database", None)

    from app.main import create_app

    return create_app()


def _patch_orchestrator(monkeypatch, *, message: str = "ok", action: str = "direct_reply", is_complete: bool = True):
    async def fake_stream_responses(self, **kwargs):
        yield OrchestratorResponse(
            session_id=self.session.id,
            phase="generation",
            message=message,
            is_complete=is_complete,
            preview_url=None,
            progress=100,
            action=action,
        )

    monkeypatch.setattr(AgentOrchestrator, "stream_responses", fake_stream_responses)


def test_chat_adapter_off_uses_legacy_path(tmp_path, monkeypatch):
    _patch_orchestrator(monkeypatch)
    app = _create_app(tmp_path, monkeypatch, adapter_enabled=False)

    create_calls = {"count": 0}
    original_create_run = RunService.create_run

    def wrapped_create_run(self, *args, **kwargs):
        create_calls["count"] += 1
        return original_create_run(self, *args, **kwargs)

    monkeypatch.setattr(RunService, "create_run", wrapped_create_run)

    with TestClient(app) as client:
        response = client.post("/api/chat", json={"message": "hello"})

    assert response.status_code == 200
    assert response.json()["message"] == "ok"
    assert create_calls["count"] == 0



def test_chat_adapter_on_creates_and_completes_run(tmp_path, monkeypatch):
    _patch_orchestrator(monkeypatch)
    app = _create_app(tmp_path, monkeypatch, adapter_enabled=True)

    with TestClient(app) as client:
        response = client.post("/api/chat", json={"message": "hello", "generate_now": True})

    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "ok"

    with get_db() as db:
        runs = db.query(SessionRun).filter(SessionRun.session_id == data["session_id"]).all()

    assert len(runs) == 1
    assert runs[0].status == "completed"
    assert runs[0].metrics == {"generate_now": True, "target_pages": []}



def test_chat_adapter_on_resume_uses_existing_waiting_run(tmp_path, monkeypatch):
    _patch_orchestrator(monkeypatch)
    app = _create_app(tmp_path, monkeypatch, adapter_enabled=True)

    session_id = uuid.uuid4().hex
    with TestClient(app) as client:
        with get_db() as db:
            db.add(SessionModel(id=session_id, title="Resume Session"))
            db.commit()

            run_service = RunService(db)
            run = run_service.create_run(
                session_id=session_id,
                message="initial",
                generate_now=False,
                target_pages=["index"],
                trigger_source="chat",
            )
            run_service.start_run(run.id)
            run_service.persist_run_state(
                run.id,
                "waiting_input",
                latest_error={"waiting_reason": "Need feedback"},
            )
            db.commit()
            run_id = run.id

        response = client.post(
            "/api/chat",
            json={
                "session_id": session_id,
                "message": "continue",
                "resume": {"run_id": run_id, "user_feedback": "looks good"},
            },
        )

        assert response.status_code == 200

        with get_db() as db:
            runs = db.query(SessionRun).filter(SessionRun.session_id == session_id).all()
            resumed = db.get(SessionRun, run_id)

    assert len(runs) == 1
    assert resumed is not None
    assert resumed.status == "completed"
    assert resumed.resume_payload == {"run_id": run_id, "user_feedback": "looks good"}



def test_chat_stream_adapter_emits_run_lifecycle_events(tmp_path, monkeypatch):
    _patch_orchestrator(monkeypatch, message="stream-ok", action="direct_reply", is_complete=True)
    app = _create_app(tmp_path, monkeypatch, adapter_enabled=True)

    with TestClient(app) as client:
        with client.stream(
            "POST",
            "/api/chat/stream",
            json={"message": "hello"},
        ) as response:
            assert response.status_code == 200
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

    event_types = [payload.get("type") for payload in payloads if payload.get("type")]

    assert "run_created" in event_types
    assert "run_started" in event_types
    assert "run_completed" in event_types
    assert event_types.index("run_created") < event_types.index("run_started")
    assert event_types.index("run_started") < event_types.index("run_completed")
