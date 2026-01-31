import json

from fastapi.testclient import TestClient

from app.agents.orchestrator import AgentOrchestrator, OrchestratorResponse
import app.db.database as db_module


def test_chat_stream_legacy_compat(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("DEFAULT_BASE_URL", "http://localhost")
    monkeypatch.setenv("DEFAULT_KEY", "test-key")
    monkeypatch.setattr(db_module, "_database", None)

    async def fake_stream_responses(self, **kwargs):
        yield OrchestratorResponse(
            session_id=self.session.id,
            phase="generation",
            message="ok",
            is_complete=True,
            preview_url=None,
            progress=100,
        )

    monkeypatch.setattr(AgentOrchestrator, "stream_responses", fake_stream_responses)

    from app.main import create_app

    app = create_app()

    with TestClient(app) as client:
        with client.stream(
            "POST",
            "/api/chat",
            json={"message": "hi"},
            headers={"Accept": "text/event-stream"},
        ) as response:
            lines = []
            for line in response.iter_lines():
                if not line:
                    continue
                decoded = line.decode() if isinstance(line, bytes) else line
                lines.append(decoded)

    data_line = next(line for line in lines if line.startswith("data:") and "[DONE]" not in line)
    payload = json.loads(data_line.replace("data:", "").strip())

    assert "session_id" in payload
    assert "phase" in payload
    assert "message" in payload
    assert "is_complete" in payload
