import uuid

from fastapi.testclient import TestClient

from app.config import refresh_settings
from app.db.migrations import init_db
from app.db.database import reset_database
from app.db.models import Session as SessionModel
from app.db.utils import get_db
from app.services.page import PageService
from app.services.page_version import PageVersionService
from app.services.product_doc import ProductDocService


def _create_app(tmp_path, monkeypatch):
    db_path = tmp_path / "files_api.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("DEFAULT_BASE_URL", "http://localhost")
    monkeypatch.setenv("DEFAULT_KEY", "test-key")
    refresh_settings()
    reset_database()
    init_db()
    from app.main import create_app

    return create_app()


def _seed_data(session_id: str) -> None:
    with get_db() as session:
        session.add(SessionModel(id=session_id, title="Files API Session"))
        session.flush()

        ProductDocService(session).create(
            session_id=session_id,
            content="# Doc",
            structured={"design_direction": {"style": "modern"}},
        )
        page = PageService(session).create(session_id=session_id, title="Index", slug="index")
        PageVersionService(session).create(page.id, "<html>index</html>")
        session.commit()


def test_files_endpoints_roundtrip(tmp_path, monkeypatch) -> None:
    app = _create_app(tmp_path, monkeypatch)
    session_id = uuid.uuid4().hex
    _seed_data(session_id)

    with TestClient(app) as client:
        tree_response = client.get(f"/api/sessions/{session_id}/files")
        assert tree_response.status_code == 200
        tree = tree_response.json()["tree"]
        assert any(node["path"] == "index.html" for node in tree)
        assert any(node["path"] == "assets" for node in tree)

        html_response = client.get(f"/api/sessions/{session_id}/files/index.html")
        assert html_response.status_code == 200
        html_payload = html_response.json()
        assert html_payload["language"] == "html"
        assert "index" in html_payload["content"]

        css_response = client.get(f"/api/sessions/{session_id}/files/assets/site.css")
        assert css_response.status_code == 200
        css_payload = css_response.json()
        assert css_payload["language"] == "css"
        assert "--primary-color" in css_payload["content"]

        missing_response = client.get(f"/api/sessions/{session_id}/files/pages/missing.html")
        assert missing_response.status_code == 404


def test_files_endpoint_404s(tmp_path, monkeypatch) -> None:
    app = _create_app(tmp_path, monkeypatch)
    missing_id = uuid.uuid4().hex

    with TestClient(app) as client:
        resp = client.get(f"/api/sessions/{missing_id}/files")
        assert resp.status_code == 404

        resp = client.get(f"/api/sessions/{missing_id}/files/index.html")
        assert resp.status_code == 404
