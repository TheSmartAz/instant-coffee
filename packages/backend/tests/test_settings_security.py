from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

import app.config as config_module
from app.config import refresh_settings
from app.db.database import reset_database
from app.db.migrations import init_db
from app.db.models import Session as SessionModel
from app.db.utils import get_db


@pytest.fixture(autouse=True)
def _clear_runtime_overrides():
    config_module._runtime_overrides.clear()
    yield
    config_module._runtime_overrides.clear()


def _create_app(tmp_path, monkeypatch, *, admin_token: str | None = None):
    db_path = tmp_path / "settings_security.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("DEFAULT_BASE_URL", "http://localhost")
    monkeypatch.setenv("DEFAULT_KEY", "secret-api-key")
    if admin_token is None:
        monkeypatch.delenv("ADMIN_TOKEN", raising=False)
        monkeypatch.delenv("SETTINGS_ADMIN_TOKEN", raising=False)
    else:
        monkeypatch.setenv("ADMIN_TOKEN", admin_token)
    refresh_settings()
    reset_database()
    init_db()

    from app.main import create_app

    return create_app()


def _seed_session() -> str:
    session_id = uuid.uuid4().hex
    with get_db() as db:
        db.add(SessionModel(id=session_id, title="Security Session"))
        db.commit()
    return session_id


def test_get_settings_redacts_api_key(tmp_path, monkeypatch):
    app = _create_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        response = client.get("/api/settings")

    assert response.status_code == 200
    payload = response.json()
    assert payload["api_key"] == ""
    assert payload["has_api_key"] is True
    assert "secret-api-key" not in response.text


def test_settings_mutations_require_admin_token_when_configured(tmp_path, monkeypatch):
    app = _create_app(tmp_path, monkeypatch, admin_token="admin-secret")

    with TestClient(app) as client:
        put_response = client.put("/api/settings", json={"temperature": 0.2})
        cleanup_response = client.post("/api/settings/cleanup", json={"dry_run": True})
        authorized_response = client.put(
            "/api/settings",
            json={"temperature": 0.3, "api_key": "new-secret"},
            headers={"Authorization": "Bearer admin-secret"},
        )

    assert put_response.status_code == 401
    assert cleanup_response.status_code == 401
    assert authorized_response.status_code == 200
    assert authorized_response.json()["temperature"] == 0.3
    assert authorized_response.json()["api_key"] == ""
    assert "new-secret" not in authorized_response.text


def test_settings_mutations_fail_closed_without_admin_token(tmp_path, monkeypatch):
    app = _create_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        response = client.put("/api/settings", json={"temperature": 0.4})

    assert response.status_code == 401
    assert response.json()["detail"] == "Admin token is not configured"


def test_settings_mutations_allow_explicit_unsafe_dev_bypass(tmp_path, monkeypatch):
    monkeypatch.setenv("ALLOW_UNSAFE_DEV_ADMIN_BYPASS", "true")
    app = _create_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        response = client.put("/api/settings", json={"temperature": 0.4})

    assert response.status_code == 200
    assert response.json()["temperature"] == 0.4


def test_settings_can_clear_api_key(tmp_path, monkeypatch):
    app = _create_app(tmp_path, monkeypatch, admin_token="admin-secret")

    with TestClient(app) as client:
        response = client.put(
            "/api/settings",
            json={"api_key": ""},
            headers={"X-Admin-Token": "admin-secret"},
        )

    assert response.status_code == 200
    assert response.json()["has_api_key"] is False
    assert config_module.get_settings().default_key == ""
    assert config_module.get_settings().openai_api_key == ""


def test_session_delete_requires_admin_token_when_configured(tmp_path, monkeypatch):
    app = _create_app(tmp_path, monkeypatch, admin_token="admin-secret")
    session_id = _seed_session()

    with TestClient(app) as client:
        blocked = client.delete(f"/api/sessions/{session_id}")
        allowed = client.delete(
            f"/api/sessions/{session_id}",
            headers={"X-Admin-Token": "admin-secret"},
        )

    assert blocked.status_code == 401
    assert allowed.status_code == 200
    assert allowed.json()["deleted"] is True


def test_project_mutations_require_admin_token_when_configured(tmp_path, monkeypatch):
    app = _create_app(tmp_path, monkeypatch, admin_token="admin-secret")
    session_id = _seed_session()

    with TestClient(app) as client:
        responses = [
            client.post(f"/api/sessions/{session_id}/data/Product", json={"name": "C"}),
            client.delete(f"/api/sessions/{session_id}/data/Product/1"),
            client.post(f"/api/sessions/{session_id}/assets?asset_type=logo"),
            client.delete(f"/api/sessions/{session_id}/assets/asset:logo_missing"),
            client.post(f"/api/sessions/{session_id}/build"),
            client.delete(f"/api/sessions/{session_id}/build"),
            client.post(f"/api/sessions/{session_id}/threads", json={"title": "Draft"}),
        ]

    assert [response.status_code for response in responses] == [401] * len(responses)
