import json
import uuid

from fastapi.testclient import TestClient

from app.config import refresh_settings
from app.db.migrations import init_db
from app.db.database import reset_database


def _create_app(tmp_path, monkeypatch):
    db_path = tmp_path / "product_doc_api.db"
    output_dir = tmp_path / "output"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))
    monkeypatch.setenv("DEFAULT_BASE_URL", "http://localhost")
    monkeypatch.setenv("DEFAULT_KEY", "test-key")
    refresh_settings()
    reset_database()
    init_db()
    from app.main import create_app

    return create_app(), output_dir


def test_product_doc_disk_fallback_returns_doc(tmp_path, monkeypatch) -> None:
    app, output_dir = _create_app(tmp_path, monkeypatch)
    session_id = uuid.uuid4().hex
    doc_dir = output_dir / session_id
    doc_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "overview": "Blue and white todo app",
        "pages": "- index\n- settings",
    }
    (doc_dir / "product-doc.json").write_text(json.dumps(payload), encoding="utf-8")

    with TestClient(app) as client:
        response = client.get(f"/api/sessions/{session_id}/product-doc")
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == f"disk:{session_id}"
        assert body["session_id"] == session_id
        assert body["status"] == "draft"
        assert body["version"] == 1
        assert body["structured"]["sections"]["overview"] == "Blue and white todo app"
        assert "## Overview" in body["content"]


def test_product_doc_history_disk_fallback_returns_empty_history(tmp_path, monkeypatch) -> None:
    app, output_dir = _create_app(tmp_path, monkeypatch)
    session_id = uuid.uuid4().hex
    doc_dir = output_dir / session_id
    doc_dir.mkdir(parents=True, exist_ok=True)
    (doc_dir / "product-doc.json").write_text(
        json.dumps({"overview": "Has doc but no DB record"}),
        encoding="utf-8",
    )

    with TestClient(app) as client:
        response = client.get(f"/api/sessions/{session_id}/product-doc/history")
        assert response.status_code == 200
        assert response.json() == {
            "history": [],
            "total": 0,
            "pinned_count": 0,
        }


def test_product_doc_missing_returns_404_without_disk_doc(tmp_path, monkeypatch) -> None:
    app, _ = _create_app(tmp_path, monkeypatch)
    session_id = uuid.uuid4().hex

    with TestClient(app) as client:
        response = client.get(f"/api/sessions/{session_id}/product-doc")
        assert response.status_code == 404
