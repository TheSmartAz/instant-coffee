from fastapi.testclient import TestClient

from app.agents.orchestrator import AgentOrchestrator, OrchestratorResponse
import app.db.database as db_module


def test_chat_response_fields(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("DEFAULT_BASE_URL", "http://localhost")
    monkeypatch.setenv("DEFAULT_KEY", "test-key")
    monkeypatch.setattr(db_module, "_database", None)

    seen = {}

    async def fake_stream_responses(self, **kwargs):
        seen["generate_now"] = kwargs.get("generate_now")
        yield OrchestratorResponse(
            session_id=self.session.id,
            phase="product_doc",
            message="ok",
            is_complete=True,
            preview_html="<html></html>",
            action="product_doc_updated",
            product_doc_updated=True,
            affected_pages=["index"],
            active_page_slug="index",
        )

    monkeypatch.setattr(AgentOrchestrator, "stream_responses", fake_stream_responses)

    from app.main import create_app

    app = create_app()

    with TestClient(app) as client:
        response = client.post(
            "/api/chat",
            json={"message": "hi", "generate_now": True},
        )

    assert response.status_code == 200
    data = response.json()

    assert seen.get("generate_now") is True
    assert data["message"] == "ok"
    assert data["product_doc_updated"] is True
    assert data["affected_pages"] == ["index"]
    assert data["action"] == "product_doc_updated"
    assert data["tokens_used"] == 0
    assert data["active_page_slug"] == "index"
    assert data["preview_html"] == "<html></html>"
    assert data["preview_url"].endswith(f"/api/sessions/{data['session_id']}/preview")
