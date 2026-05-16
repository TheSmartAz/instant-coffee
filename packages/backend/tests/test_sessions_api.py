from fastapi.testclient import TestClient

from app.config import refresh_settings
from app.db.models import Session as SessionModel
from app.db.utils import get_db
from app.db.database import reset_database
from app.db.migrations import init_db
from app.services.page import PageService
from app.services.page_version import PageVersionService
from app.services.thumbnail import ThumbnailService


def _create_app(tmp_path, monkeypatch):
    db_path = tmp_path / "sessions_api.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("DEFAULT_BASE_URL", "http://localhost")
    monkeypatch.setenv("DEFAULT_KEY", "test-key")
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "output"))
    refresh_settings()
    reset_database()
    init_db()

    from app.main import create_app

    return create_app()


def test_create_session_uses_generated_title_for_initial_prompt(tmp_path, monkeypatch) -> None:
    app = _create_app(tmp_path, monkeypatch)

    async def fake_generate_title(prompt: str) -> str:
        assert "coffee subscription" in prompt
        return "Coffee Subscription Landing"

    monkeypatch.setattr("app.api.sessions._generate_session_title", fake_generate_title)

    with TestClient(app) as client:
        response = client.post(
            "/api/sessions",
            json={
                "initial_prompt": "Build a mobile landing page for a coffee subscription service.",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["title"] == "Coffee Subscription Landing"
    assert response.headers["cache-control"] == "no-store"


def test_create_session_same_initial_prompt_always_creates_new_session(tmp_path, monkeypatch) -> None:
    app = _create_app(tmp_path, monkeypatch)

    async def fake_generate_title(prompt: str) -> str:
        return "Product Launch Page"

    monkeypatch.setattr("app.api.sessions._generate_session_title", fake_generate_title)

    body = {
        "initial_prompt": "Create a mobile-first product launch page with a sharp hero.",
    }
    with TestClient(app) as client:
        first = client.post("/api/sessions", json=body)
        second = client.post("/api/sessions", json=body)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] != second.json()["id"]
    assert first.json()["title"] == "Product Launch Page"
    assert second.json()["title"] == "Product Launch Page"


def test_create_session_keeps_explicit_title_over_initial_prompt(tmp_path, monkeypatch) -> None:
    app = _create_app(tmp_path, monkeypatch)

    async def fail_if_called(prompt: str) -> str:
        raise AssertionError("initial_prompt title generator should not be called")

    monkeypatch.setattr("app.api.sessions._generate_session_title", fail_if_called)

    with TestClient(app) as client:
        response = client.post(
            "/api/sessions",
            json={
                "title": "Manual Project Title",
                "initial_prompt": "Build a mobile landing page.",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["title"] == "Manual Project Title"


def test_list_sessions_returns_thumbnail_url_when_cached(tmp_path, monkeypatch) -> None:
    app = _create_app(tmp_path, monkeypatch)

    with get_db() as session:
        session.add(SessionModel(id="thumb-session", title="Thumb Session"))
        session.commit()

    thumbnail_path = ThumbnailService().thumbnail_path("thumb-session")
    thumbnail_path.parent.mkdir(parents=True, exist_ok=True)
    thumbnail_path.write_bytes(b"fake-png")

    with TestClient(app) as client:
        response = client.get("/api/sessions")

    assert response.status_code == 200
    payload = response.json()
    assert payload["sessions"][0]["thumbnail"].endswith(
        "/api/sessions/thumb-session/thumbnail"
    )


def test_list_sessions_returns_lazy_thumbnail_url_for_previewable_session(tmp_path, monkeypatch) -> None:
    app = _create_app(tmp_path, monkeypatch)

    with get_db() as session:
        session.add(SessionModel(id="preview-session", title="Preview Session"))
        session.flush()
        page = PageService(session).create(
            session_id="preview-session",
            title="Home",
            slug="index",
        )
        PageVersionService(session).create(
            page_id=page.id,
            html="<!doctype html><html><body><main>Homepage</main></body></html>",
        )
        session.commit()

    with TestClient(app) as client:
        response = client.get("/api/sessions")

    assert response.status_code == 200
    payload = response.json()
    assert payload["sessions"][0]["thumbnail"].endswith(
        "/api/sessions/preview-session/thumbnail"
    )


def test_list_sessions_handles_sessions_without_current_version_field(tmp_path, monkeypatch) -> None:
    app = _create_app(tmp_path, monkeypatch)

    with get_db() as session:
        session.add(SessionModel(id="plain-session", title="Plain Session"))
        session.commit()

    with TestClient(app) as client:
        response = client.get("/api/sessions")

    assert response.status_code == 200
    payload = response.json()
    assert payload["sessions"][0]["id"] == "plain-session"
    assert payload["sessions"][0]["thumbnail"] is None


def test_thumbnail_endpoint_generates_from_session_preview(tmp_path, monkeypatch) -> None:
    app = _create_app(tmp_path, monkeypatch)

    with get_db() as session:
        session.add(SessionModel(id="legacy-session", title="Legacy Session"))
        session.flush()
        page = PageService(session).create(
            session_id="legacy-session",
            title="Home",
            slug="index",
        )
        PageVersionService(session).create(
            page_id=page.id,
            html="<!doctype html><html><body><main>Homepage</main></body></html>",
        )
        session.commit()

    async def fake_capture_html(self, session_id: str, html: str):
        assert session_id == "legacy-session"
        assert "Homepage" in html
        path = self.thumbnail_path(session_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"fake-png")
        return path

    monkeypatch.setattr(ThumbnailService, "capture_html", fake_capture_html)

    with TestClient(app) as client:
        response = client.get("/api/sessions/legacy-session/thumbnail")

    assert response.status_code == 200
    assert response.content == b"fake-png"
