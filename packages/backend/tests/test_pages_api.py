import uuid

from fastapi.testclient import TestClient

from app.config import refresh_settings
from app.db.migrations import init_db
from app.db.database import reset_database
from app.db.models import Session as SessionModel
from app.db.utils import get_db
from app.services.page import PageService
from app.services.page_version import PageVersionService


def _create_app(tmp_path, monkeypatch):
    db_path = tmp_path / "pages_api.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("DEFAULT_BASE_URL", "http://localhost")
    monkeypatch.setenv("DEFAULT_KEY", "test-key")
    refresh_settings()
    reset_database()
    init_db()
    from app.main import create_app

    return create_app()


def _seed_page_data(session_id: str) -> tuple[str, int, int]:
    with get_db() as session:
        session.add(SessionModel(id=session_id, title="API Session"))
        session.flush()

        page = PageService(session).create(
            session_id=session_id,
            title="Index",
            slug="index",
        )
        page_id = page.id
        version_service = PageVersionService(session)
        v1 = version_service.create(page_id, "<html>v1</html>")
        v2 = version_service.create(page_id, "<html>v2</html>")
        v1_id = v1.id
        v2_id = v2.id
        session.commit()
    return page_id, v1_id, v2_id


def _seed_page_versions(session_id: str, count: int) -> tuple[str, list[int]]:
    with get_db() as session:
        session.add(SessionModel(id=session_id, title="API Session"))
        session.flush()

        page = PageService(session).create(
            session_id=session_id,
            title="Index",
            slug="index",
        )
        page_id = page.id
        version_service = PageVersionService(session)
        version_ids: list[int] = []
        for idx in range(count):
            version = version_service.create(page_id, f"<html>v{idx + 1}</html>")
            version_ids.append(version.id)
        session.commit()
    return page_id, version_ids


def test_pages_endpoints_roundtrip(tmp_path, monkeypatch) -> None:
    app = _create_app(tmp_path, monkeypatch)
    session_id = uuid.uuid4().hex
    page_id, v1_id, v2_id = _seed_page_data(session_id)

    with TestClient(app) as client:
        pages_response = client.get(f"/api/sessions/{session_id}/pages")
        assert pages_response.status_code == 200
        pages_payload = pages_response.json()
        assert pages_payload["total"] == 1
        assert pages_payload["pages"][0]["id"] == page_id

        page_response = client.get(f"/api/pages/{page_id}")
        assert page_response.status_code == 200
        assert page_response.json()["slug"] == "index"

        versions_response = client.get(f"/api/pages/{page_id}/versions")
        assert versions_response.status_code == 200
        versions_payload = versions_response.json()
        assert versions_payload["current_version_id"] == v2_id
        assert versions_payload["versions"][0]["version"] == 2
        assert versions_payload["versions"][0]["available"] is True

        preview_response = client.get(f"/api/pages/{page_id}/preview")
        assert preview_response.status_code == 200
        preview_payload = preview_response.json()
        assert preview_payload["version"] == 2
        assert "v2" in preview_payload["html"]

        preview_version = client.get(f"/api/pages/{page_id}/versions/{v1_id}/preview")
        assert preview_version.status_code == 200
        preview_payload = preview_version.json()
        assert preview_payload["version"] == 1
        assert "v1" in preview_payload["html"]

        rollback_response = client.post(f"/api/pages/{page_id}/rollback")
        assert rollback_response.status_code == 410


def test_pages_endpoint_404s(tmp_path, monkeypatch) -> None:
    app = _create_app(tmp_path, monkeypatch)
    missing_id = uuid.uuid4().hex

    with TestClient(app) as client:
        resp = client.get(f"/api/sessions/{missing_id}/pages")
        assert resp.status_code == 404

        resp = client.get(f"/api/pages/{missing_id}")
        assert resp.status_code == 404

        resp = client.get(f"/api/pages/{missing_id}/versions")
        assert resp.status_code == 404

        resp = client.get(f"/api/pages/{missing_id}/preview")
        assert resp.status_code == 404

        resp = client.post(f"/api/pages/{missing_id}/rollback", json={"version_id": 1})
        assert resp.status_code == 404


def test_page_version_pin_unpin_and_limit(tmp_path, monkeypatch) -> None:
    app = _create_app(tmp_path, monkeypatch)
    session_id = uuid.uuid4().hex
    page_id, version_ids = _seed_page_versions(session_id, 3)
    v1_id, v2_id, v3_id = version_ids

    with TestClient(app) as client:
        pin_v1 = client.post(f"/api/pages/{page_id}/versions/{v1_id}/pin")
        assert pin_v1.status_code == 200
        assert pin_v1.json()["version"]["is_pinned"] is True

        pin_v2 = client.post(f"/api/pages/{page_id}/versions/{v2_id}/pin")
        assert pin_v2.status_code == 200
        assert pin_v2.json()["version"]["is_pinned"] is True

        pin_v3 = client.post(f"/api/pages/{page_id}/versions/{v3_id}/pin")
        assert pin_v3.status_code == 409
        assert pin_v3.json()["error"] == "pinned_limit_exceeded"

        unpin_v1 = client.post(f"/api/pages/{page_id}/versions/{v1_id}/unpin")
        assert unpin_v1.status_code == 200
        assert unpin_v1.json()["version"]["is_pinned"] is False


def test_page_version_preview_released_returns_410(tmp_path, monkeypatch) -> None:
    app = _create_app(tmp_path, monkeypatch)
    session_id = uuid.uuid4().hex
    page_id, version_ids = _seed_page_versions(session_id, 7)
    released_version_id = version_ids[0]

    with TestClient(app) as client:
        response = client.get(
            f"/api/pages/{page_id}/versions/{released_version_id}/preview"
        )
        assert response.status_code == 410
        payload = response.json()
        assert payload["error"] == "version_released"
