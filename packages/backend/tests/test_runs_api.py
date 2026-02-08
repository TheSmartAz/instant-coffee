import uuid

from fastapi.testclient import TestClient

from app.config import refresh_settings
from app.db.database import reset_database
from app.db.migrations import init_db
from app.db.models import Session as SessionModel
from app.db.models import SessionEvent, SessionEventSource
from app.db.utils import get_db


def _create_app(tmp_path, monkeypatch, *, run_api_enabled: bool = True):
    db_path = tmp_path / "runs_api.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("DEFAULT_BASE_URL", "http://localhost")
    monkeypatch.setenv("DEFAULT_KEY", "test-key")
    monkeypatch.setenv("RUN_API_ENABLED", "true" if run_api_enabled else "false")
    refresh_settings()
    reset_database()
    init_db()

    from app.main import create_app

    return create_app()


def _seed_session() -> str:
    session_id = uuid.uuid4().hex
    with get_db() as session:
        session.add(SessionModel(id=session_id, title="Runs API Session"))
        session.commit()
    return session_id


def _seed_run_events(session_id: str, run_id: str) -> None:
    with get_db() as session:
        session.add(
            SessionEvent(
                session_id=session_id,
                run_id=run_id,
                event_id="evt-1",
                seq=1,
                type="run_started",
                payload={"a": 1},
                source=SessionEventSource.SESSION,
            )
        )
        session.add(
            SessionEvent(
                session_id=session_id,
                run_id="other-run",
                event_id="evt-2",
                seq=2,
                type="run_started",
                payload={"a": 2},
                source=SessionEventSource.SESSION,
            )
        )
        session.add(
            SessionEvent(
                session_id=session_id,
                run_id=run_id,
                event_id="evt-3",
                seq=3,
                type="run_progress",
                payload={"a": 3},
                source=SessionEventSource.SESSION,
            )
        )
        session.commit()


def test_runs_api_create_get_resume_cancel_and_idempotency(tmp_path, monkeypatch) -> None:
    app = _create_app(tmp_path, monkeypatch)
    session_id = _seed_session()

    with TestClient(app) as client:
        create_payload = {
            "session_id": session_id,
            "message": "hello",
            "generate_now": True,
            "target_pages": ["index"],
        }
        create_resp = client.post(
            "/api/runs",
            json=create_payload,
            headers={"Idempotency-Key": "create-1"},
        )
        assert create_resp.status_code == 201
        created = create_resp.json()
        run_id = created["run_id"]
        assert created["session_id"] == session_id
        assert created["status"] == "queued"

        create_again = client.post(
            "/api/runs",
            json=create_payload,
            headers={"Idempotency-Key": "create-1"},
        )
        assert create_again.status_code == 201
        assert create_again.json()["run_id"] == run_id

        get_resp = client.get(f"/api/runs/{run_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["run_id"] == run_id

        resume_conflict = client.post(
            f"/api/runs/{run_id}/resume",
            json={"resume_payload": {"ok": True}},
        )
        assert resume_conflict.status_code == 409

        cancel_resp = client.post(f"/api/runs/{run_id}/cancel")
        assert cancel_resp.status_code == 202
        assert cancel_resp.json()["status"] == "cancelled"

        cancel_again = client.post(f"/api/runs/{run_id}/cancel")
        assert cancel_again.status_code == 200
        assert cancel_again.json()["status"] == "cancelled"


def test_runs_api_resume_idempotency(tmp_path, monkeypatch) -> None:
    app = _create_app(tmp_path, monkeypatch)
    session_id = _seed_session()

    with TestClient(app) as client:
        create_resp = client.post(
            "/api/runs",
            json={"session_id": session_id, "message": "hello"},
        )
        run_id = create_resp.json()["run_id"]

    with get_db() as session:
        from app.services.run import RunService

        service = RunService(session)
        service.start_run(run_id)
        service.persist_run_state(run_id, "waiting_input")
        session.commit()

    with TestClient(app) as client:
        resume_resp = client.post(
            f"/api/runs/{run_id}/resume",
            json={"resume": {"ok": 1}},
            headers={"Idempotency-Key": "resume-1"},
        )
        assert resume_resp.status_code == 200
        assert resume_resp.json()["status"] == "running"

        resume_cached = client.post(
            f"/api/runs/{run_id}/resume",
            json={"resume": {"ok": 2}},
            headers={"Idempotency-Key": "resume-1"},
        )
        assert resume_cached.status_code == 200
        assert resume_cached.json()["status"] == "running"


def test_runs_api_events_filter_by_run_id(tmp_path, monkeypatch) -> None:
    app = _create_app(tmp_path, monkeypatch)
    session_id = _seed_session()

    with TestClient(app) as client:
        create_resp = client.post(
            "/api/runs",
            json={"session_id": session_id, "message": "hello"},
        )
        run_id = create_resp.json()["run_id"]

    _seed_run_events(session_id, run_id)

    with TestClient(app) as client:
        events_resp = client.get(f"/api/runs/{run_id}/events")
        assert events_resp.status_code == 200
        payload = events_resp.json()
        assert payload["has_more"] is False
        assert payload["last_seq"] == 3
        assert [event["seq"] for event in payload["events"]] == [1, 3]
        assert {event["run_id"] for event in payload["events"]} == {run_id}

        events_since = client.get(f"/api/runs/{run_id}/events", params={"since_seq": 1})
        assert events_since.status_code == 200
        payload_since = events_since.json()
        assert [event["seq"] for event in payload_since["events"]] == [3]


def test_session_events_endpoint_includes_run_and_event_ids(tmp_path, monkeypatch) -> None:
    app = _create_app(tmp_path, monkeypatch)
    session_id = _seed_session()

    with get_db() as session:
        session.add(
            SessionEvent(
                session_id=session_id,
                run_id="run-session-events",
                event_id="evt-session-events",
                seq=1,
                type="run_started",
                payload={"status": "running"},
                source=SessionEventSource.SESSION,
            )
        )
        session.commit()

    with TestClient(app) as client:
        response = client.get(f"/api/sessions/{session_id}/events")

    assert response.status_code == 200
    payload = response.json()
    assert payload["events"]
    first = payload["events"][0]
    assert first["run_id"] == "run-session-events"
    assert first["event_id"] == "evt-session-events"


def test_runs_api_events_support_sse(tmp_path, monkeypatch) -> None:
    app = _create_app(tmp_path, monkeypatch)
    session_id = _seed_session()

    with TestClient(app) as client:
        create_resp = client.post(
            "/api/runs",
            json={"session_id": session_id, "message": "hello"},
        )
        run_id = create_resp.json()["run_id"]
        client.post(f"/api/runs/{run_id}/cancel")

    _seed_run_events(session_id, run_id)

    with TestClient(app) as client:
        with client.stream(
            "GET",
            f"/api/runs/{run_id}/events",
            headers={"Accept": "text/event-stream"},
        ) as response:
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")
            lines = []
            for line in response.iter_lines():
                if not line:
                    continue
                decoded = line.decode() if isinstance(line, bytes) else line
                lines.append(decoded)

    assert any(line.startswith("data: {") for line in lines)
    assert any("[DONE]" in line for line in lines)


def test_runs_api_disabled_returns_404(tmp_path, monkeypatch) -> None:
    app = _create_app(tmp_path, monkeypatch, run_api_enabled=False)

    with TestClient(app) as client:
        resp = client.post("/api/runs", json={"session_id": "x", "message": "hello"})
        assert resp.status_code == 404
