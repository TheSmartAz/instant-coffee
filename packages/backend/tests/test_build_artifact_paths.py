from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import refresh_settings
from app.db.database import reset_database
from app.db.migrations import init_db
from app.db.models import Session as SessionModel
from app.db.utils import get_db


def _create_app(tmp_path, monkeypatch):
    db_path = tmp_path / "build_artifact_paths.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("DEFAULT_BASE_URL", "http://localhost")
    monkeypatch.setenv("DEFAULT_KEY", "test-key")
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "configured-output"))
    refresh_settings()
    reset_database()
    init_db()

    from app.main import create_app

    return create_app()


def test_build_logs_use_configured_output_dir(tmp_path, monkeypatch) -> None:
    app = _create_app(tmp_path, monkeypatch)
    session_id = "logs-session"
    log_path = tmp_path / "configured-output" / session_id / "build.log"
    log_path.parent.mkdir(parents=True)
    log_path.write_text("configured build log\n", encoding="utf-8")

    with get_db() as session:
        session.add(SessionModel(id=session_id, title="Logs Session"))
        session.commit()

    with TestClient(app) as client:
        response = client.get(f"/api/sessions/{session_id}/build/logs")

    assert response.status_code == 200
    assert response.json() == {"logs": "configured build log\n", "available": True}


def test_preview_uses_build_artifact_dist_path_from_metadata(tmp_path, monkeypatch) -> None:
    app = _create_app(tmp_path, monkeypatch)
    session_id = "metadata-preview-session"
    metadata_dist = tmp_path / "metadata-dist"
    metadata_dist.mkdir()
    (metadata_dist / "index.html").write_text("<html>metadata dist</html>", encoding="utf-8")

    configured_dist = tmp_path / "configured-output" / session_id / "dist"
    configured_dist.mkdir(parents=True)
    (configured_dist / "index.html").write_text("<html>configured dist</html>", encoding="utf-8")

    with get_db() as session:
        session.add(
            SessionModel(
                id=session_id,
                title="Metadata Preview Session",
                build_artifacts={"dist_path": str(metadata_dist), "pages": ["index.html"]},
            )
        )
        session.commit()

    with TestClient(app) as client:
        response = client.get(f"/preview/{session_id}/index.html")

    assert response.status_code == 200
    assert "metadata dist" in response.text


def test_preview_falls_back_to_configured_output_dist(tmp_path, monkeypatch) -> None:
    app = _create_app(tmp_path, monkeypatch)
    session_id = "fallback-preview-session"
    dist_path = tmp_path / "configured-output" / session_id / "dist"
    dist_path.mkdir(parents=True)
    (dist_path / "index.html").write_text("<html>configured dist</html>", encoding="utf-8")

    with get_db() as session:
        session.add(SessionModel(id=session_id, title="Fallback Preview Session"))
        session.commit()

    with TestClient(app) as client:
        response = client.get(f"/preview/{session_id}/index.html")

    assert response.status_code == 200
    assert "configured dist" in response.text
