import uuid

from fastapi.testclient import TestClient

from app.config import refresh_settings
from app.db.database import reset_database
from app.db.migrations import init_db
from app.db.models import Session as SessionModel, SessionEvent
from app.db.utils import get_db
from app.services.page import PageService
from app.services.page_version import PageVersionService
from app.services.product_doc import ProductDocService
from app.services.run import RunService
from app.services.token_tracker import TokenTrackerService


def _create_app(tmp_path, monkeypatch):
    db_path = tmp_path / "compat_api.db"
    output_dir = tmp_path / "output"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("DEFAULT_BASE_URL", "http://localhost")
    monkeypatch.setenv("DEFAULT_KEY", "test-key")
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))
    refresh_settings()
    reset_database()
    init_db()

    from app.main import create_app

    return create_app(), output_dir


def _seed_session(title: str = "Compat Session") -> str:
    session_id = uuid.uuid4().hex
    with get_db() as session:
        session.add(SessionModel(id=session_id, title=title))
        session.commit()
    return session_id


def test_session_export_and_legacy_export_routes_write_manifest(tmp_path, monkeypatch) -> None:
    app, output_dir = _create_app(tmp_path, monkeypatch)
    session_id = _seed_session()

    with get_db() as session:
        ProductDocService(session).create(
            session_id=session_id,
            content="# Product Doc",
            structured={"design_direction": {"color_preference": "#336699"}},
        )
        page_service = PageService(session)
        index_page = page_service.create(session_id=session_id, title="Home", slug="index")
        about_page = page_service.create(session_id=session_id, title="About", slug="about")
        version_service = PageVersionService(session)
        version_service.create(index_page.id, "<html><body>Home</body></html>")
        version_service.create(about_page.id, "<html><body>About</body></html>")
        session.commit()

    with TestClient(app) as client:
        response = client.post(f"/api/sessions/{session_id}/export")
        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is True
        assert payload["export_dir"] == str((output_dir / session_id / "export").resolve())
        assert (output_dir / session_id / "export" / "index.html").exists()
        assert (output_dir / session_id / "export" / "pages" / "about.html").exists()
        assert (output_dir / session_id / "export" / "assets" / "site.css").exists()
        assert (output_dir / session_id / "export" / "product-doc.md").exists()
        assert (output_dir / session_id / "export" / "export_manifest.json").exists()
        assert {page["slug"] for page in payload["manifest"]["pages"]} == {"index", "about"}

        legacy_dir = tmp_path / "legacy-export"
        legacy_response = client.post(
            "/api/export",
            json={"session_id": session_id, "output_dir": str(legacy_dir)},
        )
        assert legacy_response.status_code == 200
        legacy_payload = legacy_response.json()
        assert legacy_payload["file_path"] == str((legacy_dir / "index.html").resolve())
        assert (legacy_dir / "export_manifest.json").exists()


def test_stats_and_abort_compatibility_routes(tmp_path, monkeypatch) -> None:
    app, _output_dir = _create_app(tmp_path, monkeypatch)
    session_id = _seed_session()

    with get_db() as session:
        TokenTrackerService(session).record_usage(
            session_id,
            agent_type="writer",
            model="test-model",
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.01,
        )
        run_service = RunService(session)
        run = run_service.create_run(session_id=session_id, message="hello")
        run_id = run.id
        run_service.start_run(run_id)
        session.commit()

    with TestClient(app) as client:
        stats_response = client.get("/api/stats")
        assert stats_response.status_code == 200
        stats = stats_response.json()
        assert stats["total"]["tokens"] == 150
        assert stats["total"]["calls"] == 1
        assert stats["by_agent"]["writer"]["tokens"] == 150

        session_stats_response = client.get(f"/api/stats/session/{session_id}")
        assert session_stats_response.status_code == 200
        session_stats = session_stats_response.json()
        assert session_stats["session_id"] == session_id
        assert session_stats["total_tokens"] == 150
        assert session_stats["calls"] == 1
        assert len(session_stats["timeline"]) == 1

        abort_response = client.post(f"/api/session/{session_id}/abort")
        assert abort_response.status_code == 200
        abort_payload = abort_response.json()
        assert abort_payload["success"] is True
        assert abort_payload["aborted_tasks"] == [run_id]

    with get_db() as session:
        stored = RunService(session).get_run(run_id)
        assert stored.status == "cancelled"


def test_plan_and_task_compatibility_routes_are_event_sourced(tmp_path, monkeypatch) -> None:
    app, _output_dir = _create_app(tmp_path, monkeypatch)
    session_id = _seed_session()

    with TestClient(app) as client:
        plan_response = client.post(
            "/api/plan",
            json={
                "session_id": session_id,
                "message": "Build a launch page",
                "tasks": [
                    {
                        "id": "copy-task",
                        "title": "Write copy",
                        "status": "failed",
                        "error_message": "Draft missing",
                    },
                    {
                        "id": "review-task",
                        "title": "Review page",
                        "depends_on": ["copy-task"],
                    },
                ],
            },
        )
        assert plan_response.status_code == 201
        plan = plan_response.json()
        assert plan["session_id"] == session_id
        assert plan["goal"] == "Build a launch page"
        assert plan["status"] == "failed"
        assert [task["id"] for task in plan["tasks"]] == ["copy-task", "review-task"]

        status_response = client.get(f"/api/plan/{plan['id']}/status")
        assert status_response.status_code == 200
        assert status_response.json()["tasks"][0]["status"] == "failed"

        retry_response = client.post(
            "/api/task/copy-task/retry",
            json={"reason": "user requested retry", "max_attempts": 4},
        )
        assert retry_response.status_code == 200
        retry_payload = retry_response.json()
        assert retry_payload["success"] is True
        assert retry_payload["status"] == "retrying"
        assert retry_payload["attempt"] == 1
        assert retry_payload["scheduled"] is False

        task_status_response = client.get("/api/task/copy-task/status")
        assert task_status_response.status_code == 200
        task_status = task_status_response.json()
        assert task_status["status"] == "retrying"
        assert task_status["retry_count"] == 1

        skip_response = client.post(
            "/api/task/copy-task/skip",
            json={"reason": "not needed"},
        )
        assert skip_response.status_code == 200
        assert skip_response.json()["status"] == "skipped"

        final_status = client.get(f"/api/plan/{plan['id']}/status").json()
        assert final_status["tasks"][0]["status"] == "skipped"
        assert final_status["tasks"][0]["progress"] == 100

        modify_response = client.post(
            "/api/task/review-task/modify",
            json={
                "title": "Review final page",
                "description": "Check mobile rendering",
            },
        )
        assert modify_response.status_code == 200
        assert modify_response.json()["modified"] is True

        review_task = client.get("/api/task/review-task/status").json()
        assert review_task["title"] == "Review final page"
        assert review_task["description"] == "Check mobile rendering"
        assert review_task["status"] == "retrying"

    with get_db() as session:
        event_types = [
            row.type
            for row in (
                session.query(SessionEvent)
                .filter(SessionEvent.session_id == session_id)
                .order_by(SessionEvent.seq.asc())
                .all()
            )
        ]
        assert "plan_created" in event_types
        assert "plan_updated" in event_types
        assert "task_retrying" in event_types
        assert "task_skipped" in event_types


def test_plan_task_compatibility_routes_return_404_for_unknown_ids(tmp_path, monkeypatch) -> None:
    app, _output_dir = _create_app(tmp_path, monkeypatch)
    _seed_session()

    with TestClient(app) as client:
        assert client.get("/api/plan/missing/status").status_code == 404
        assert client.get("/api/task/missing/status").status_code == 404
        assert client.post("/api/task/missing/retry").status_code == 404


def test_session_rollback_route_has_single_semantic_path(tmp_path, monkeypatch) -> None:
    app, _output_dir = _create_app(tmp_path, monkeypatch)
    post_paths = [
        route.path
        for route in app.routes
        if "POST" in getattr(route, "methods", set())
    ]
    assert post_paths.count("/api/sessions/{session_id}/rollback") == 1
    assert "/api/sessions/{session_id}/agent/rollback" in post_paths
    assert "/api/plan" in post_paths
    assert "/api/task/{task_id}/retry" in post_paths
    assert "/api/task/{task_id}/skip" in post_paths
