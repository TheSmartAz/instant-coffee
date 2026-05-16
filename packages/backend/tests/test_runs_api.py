import uuid

from fastapi.testclient import TestClient

from app.config import refresh_settings
from app.db.database import reset_database
from app.db.migrations import init_db
from app.db.models import Session as SessionModel
from app.db.models import SessionRun
from app.db.models import SessionEvent, SessionEventSource
from app.db.utils import get_db
from app.services.memory import ProjectMemoryService


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
        assert created["execution_mode"] == "agent"
        assert created["approval_mode"] == "agent"

        create_again = client.post(
            "/api/runs",
            json=create_payload,
            headers={"Idempotency-Key": "create-1"},
        )
        assert create_again.status_code == 201
        assert create_again.json()["run_id"] == run_id

        get_resp = client.get(f"/api/runs/{run_id}")
        assert get_resp.status_code == 200
        get_payload = get_resp.json()
        assert get_payload["run_id"] == run_id
        assert get_payload["created_at"]
        assert get_payload["updated_at"]
        assert get_payload["execution_mode"] == "agent"
        assert get_payload["approval_mode"] == "agent"
        assert get_payload["phase_history"] == []

        list_resp = client.get("/api/runs", params={"session_id": session_id})
        assert list_resp.status_code == 200
        list_payload = list_resp.json()
        assert list_payload["total"] == 1
        assert list_payload["runs"][0]["run_id"] == run_id

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

    with get_db() as session:
        events = (
            session.query(SessionEvent)
            .filter(SessionEvent.run_id == run_id, SessionEvent.type == "run_cancelled")
            .all()
        )
        assert len(events) == 1
        assert events[0].payload["payload"]["status"] == "cancelled"


def test_runs_api_create_conflicts_with_active_run(tmp_path, monkeypatch) -> None:
    app = _create_app(tmp_path, monkeypatch)
    session_id = _seed_session()

    with TestClient(app) as client:
        first = client.post(
            "/api/runs",
            json={"session_id": session_id, "message": "first"},
        )
        assert first.status_code == 201
        run_id = first.json()["run_id"]

        with get_db() as session:
            from app.services.run import RunService

            RunService(session).start_run(run_id)
            session.commit()

        second = client.post(
            "/api/runs",
            json={"session_id": session_id, "message": "second"},
        )

    assert second.status_code == 409
    assert "already running" in second.json()["detail"]


def test_runs_api_normalizes_legacy_yolo_approval_mode(tmp_path, monkeypatch) -> None:
    app = _create_app(tmp_path, monkeypatch)
    session_id = _seed_session()

    with TestClient(app) as client:
        response = client.post(
            "/api/runs",
            json={
                "session_id": session_id,
                "message": "build automatically",
                "approval_mode": "yolo",
            },
        )

    assert response.status_code == 201
    payload = response.json()
    assert payload["execution_mode"] == "auto"
    assert payload["approval_mode"] == "auto"

    with get_db() as session:
        run = session.get(SessionRun, payload["run_id"])
        assert run is not None
        assert run.metrics["execution_mode"] == "auto"
        assert run.metrics["approval_mode"] == "auto"


def test_runs_api_create_response_includes_execution_mode(tmp_path, monkeypatch) -> None:
    app = _create_app(tmp_path, monkeypatch)
    session_id = _seed_session()

    with TestClient(app) as client:
        response = client.post(
            "/api/runs",
            json={
                "session_id": session_id,
                "message": "plan the app before building",
                "execution_mode": "plan",
            },
        )

    assert response.status_code == 201
    payload = response.json()
    assert payload["execution_mode"] == "plan"
    assert payload["approval_mode"] == "plan"


def test_runs_api_resolves_live_shell_approval(tmp_path, monkeypatch) -> None:
    app = _create_app(tmp_path, monkeypatch)
    session_id = _seed_session()
    run_id = uuid.uuid4().hex
    calls: list[tuple[str, str, bool]] = []

    def fake_resolve(session: str, approval_id: str, approved: bool) -> bool:
        calls.append((session, approval_id, approved))
        return approval_id == "approval-1"

    monkeypatch.setattr("app.api.runs.engine_registry.resolve_shell_approval", fake_resolve)

    with get_db() as session:
        session.add(
            SessionRun(
                id=run_id,
                session_id=session_id,
                trigger_source="chat",
                status="running",
                input_message="build",
                metrics={"execution_mode": "agent", "approval_mode": "agent"},
            )
        )
        session.commit()

    with TestClient(app) as client:
        response = client.post(
            f"/api/runs/{run_id}/approvals/approval-1",
            json={"approved": True},
        )

    assert response.status_code == 200
    assert response.json()["run_id"] == run_id
    assert calls == [(session_id, "approval-1", True)]


def test_runs_api_rejects_missing_shell_approval(tmp_path, monkeypatch) -> None:
    app = _create_app(tmp_path, monkeypatch)
    session_id = _seed_session()
    run_id = uuid.uuid4().hex
    monkeypatch.setattr(
        "app.api.runs.engine_registry.resolve_shell_approval",
        lambda _session_id, _approval_id, _approved: False,
    )

    with get_db() as session:
        session.add(
            SessionRun(
                id=run_id,
                session_id=session_id,
                trigger_source="chat",
                status="running",
                input_message="build",
            )
        )
        session.commit()

    with TestClient(app) as client:
        response = client.post(
            f"/api/runs/{run_id}/approvals/missing",
            json={"approved": False},
        )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_runs_api_list_total_counts_runs_beyond_limit(tmp_path, monkeypatch) -> None:
    app = _create_app(tmp_path, monkeypatch)
    session_id = _seed_session()

    with get_db() as session:
        from app.services.run import RunService

        service = RunService(session)
        first = service.create_run(session_id=session_id, message="first")
        service.persist_run_state(first.id, "cancelled")
        service.create_run(session_id=session_id, message="second")
        session.commit()

    with TestClient(app) as client:
        list_resp = client.get("/api/runs", params={"session_id": session_id, "limit": 1})

    assert list_resp.status_code == 200
    list_payload = list_resp.json()
    assert list_payload["total"] == 2
    assert len(list_payload["runs"]) == 1


def test_runs_api_exposes_structured_verification_evidence(tmp_path, monkeypatch) -> None:
    app = _create_app(tmp_path, monkeypatch)
    session_id = _seed_session()
    run_id = uuid.uuid4().hex

    with get_db() as session:
        ProjectMemoryService(session).save_memory(
            session_id,
            "architecture_notes",
            "Code paths: Modified code path `packages/backend/app/api/runs.py`",
        )
        ProjectMemoryService(session).save_memory(
            session_id,
            "testing_notes",
            "Verification: Uses pytest for backend verification",
        )
        run = SessionRun(
            id=run_id,
            session_id=session_id,
            trigger_source="chat",
            status="completed",
            input_message="build a landing page",
            metrics={
                "coordinator": {
                    "current_phase": "done",
                    "fix_attempts": 1,
                    "phase_history": [
                        {"phase": "build", "status": "completed"},
                        {"phase": "review", "status": "completed"},
                    ],
                    "artifacts": {
                        "build": {
                            "status": "success",
                            "pages": ["index.html"],
                            "dist_path": "dist/test-session",
                        },
                        "review": {
                            "verdict": "pass",
                            "issues": [],
                            "summary": {
                                "error_count": 0,
                                "warning_count": 0,
                                "generated_pages": ["index"],
                                "build_status": "success",
                            },
                        },
                    },
                }
            },
        )
        session.add(run)
        session.commit()

    with TestClient(app) as client:
        response = client.get(f"/api/runs/{run_id}")

    assert response.status_code == 200
    verification = response.json()["verification"]
    assert verification["status"] == "passed"
    assert verification["passed"] is True
    assert [check["name"] for check in verification["checks"]] == ["build", "review"]
    assert verification["checks"][0]["details"]["page_count"] == 1
    assert verification["checks"][1]["details"]["issue_count"] == 0
    assert "Build produced 1 page artifact(s)." in verification["evidence"]
    payload = response.json()
    assert payload["context"]["memory_keys"] == ["architecture_notes", "testing_notes"]
    assert payload["context"]["memory"] == {}
    assert payload["metrics"] is None
    assert payload["latest_error"] is None
    assert payload["artifacts"] == {
        "build": {"status": "success", "pages": ["index.html"], "dist_path": "dist/test-session"}
    }
    commands = verification["profile"]["recommended_commands"]
    assert commands[0]["command"] == "PYTHONPATH=.:../agent/src python -m pytest -q"
    assert "test_memory_missing" not in verification["profile"]["risk_flags"]


def test_runs_api_runs_verification_and_persists_result(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_TOKEN", "admin-secret")
    app = _create_app(tmp_path, monkeypatch)
    session_id = _seed_session()
    run_id = uuid.uuid4().hex

    class FakeVerificationRunner:
        async def run_profile(self, profile):
            from app.schemas.run import VerificationRunResult

            assert profile["recommended_commands"]
            return VerificationRunResult(
                status="failed",
                passed=False,
                risk_flags=["verification_failed"],
                commands=[
                    {
                        "name": "backend targeted tests",
                        "command": "PYTHONPATH=.:../agent/src python -m pytest -q",
                        "scope": "backend",
                        "status": "failed",
                        "exit_code": 1,
                        "duration_ms": 12,
                        "output_summary": "app/api/runs.py:42: AssertionError",
                        "failures": [
                            {
                                "file": "app/api/runs.py",
                                "line": 42,
                                "message": "AssertionError",
                                "source": "pytest",
                                "route": "pytest",
                                "kind": "backend_test",
                                "fix_hint": "Fix the failing Python test or the backend behavior it protects, then rerun backend tests.",
                            }
                        ],
                    }
                ],
            )

    monkeypatch.setattr("app.api.runs.VerificationRunner", lambda: FakeVerificationRunner())

    with get_db() as session:
        run = SessionRun(
            id=run_id,
            session_id=session_id,
            trigger_source="chat",
            status="completed",
            input_message="build",
            metrics={"coordinator": {"artifacts": {"build": {"status": "success", "pages": ["index.html"]}}}},
        )
        session.add(run)
        session.commit()

    with TestClient(app) as client:
        blocked = client.post(f"/api/runs/{run_id}/verification")
        response = client.post(
            f"/api/runs/{run_id}/verification",
            headers={"X-Admin-Token": "admin-secret"},
        )
        detail = client.get(f"/api/runs/{run_id}")

    assert blocked.status_code == 401
    assert response.status_code == 200
    last_run = response.json()["verification"]["last_run"]
    assert last_run["status"] == "failed"
    assert response.json()["verification"]["status"] == "failed"
    assert response.json()["verification"]["passed"] is False
    assert last_run["commands"][0]["output_summary"] == ""
    assert last_run["commands"][0]["failures"][0]["file"] == "app/api/runs.py"
    assert last_run["commands"][0]["failures"][0]["route"] == "pytest"
    assert last_run["commands"][0]["failures"][0]["kind"] == "backend_test"
    assert "rerun backend tests" in last_run["commands"][0]["failures"][0]["fix_hint"]
    assert "message" not in last_run["commands"][0]["failures"][0]
    audit = response.json()["verification"]["audit_trail"]
    audit_types = [event["type"] for event in audit]
    assert "verification_started" in audit_types
    assert "verification_completed" in audit_types
    assert audit_types.index("verification_started") < audit_types.index("verification_completed")
    completed_event = audit[audit_types.index("verification_completed")]
    assert completed_event["failure_count"] == 1
    actions = response.json()["verification"]["action_audit_trail"]
    assert [event["type"] for event in actions] == [
        "verification_run_started",
        "verification_command",
    ]
    assert actions[-1]["category"] == "shell"
    assert actions[-1]["command"] == "PYTHONPATH=.:../agent/src python -m pytest -q"
    assert actions[-1]["risk_flags"] == ["failure_route:pytest"]
    assert "AssertionError" not in str(actions)
    assert detail.json()["verification"]["last_run"]["risk_flags"] == ["verification_failed"]


def test_runs_api_runs_visual_verification_when_build_dist_exists(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_TOKEN", "admin-secret")
    app = _create_app(tmp_path, monkeypatch)
    session_id = _seed_session()
    run_id = uuid.uuid4().hex
    dist_path = str(tmp_path / "dist" / session_id)

    class FakeVerificationRunner:
        async def run_profile(self, profile):
            from app.schemas.run import VerificationRunResult

            return VerificationRunResult(status="passed", passed=True, commands=[])

    class FakeVisualVerificationService:
        async def verify_dist(self, *, session_id, dist_path, page="index.html"):
            return {
                "status": "passed",
                "passed": True,
                "quality_score": 95,
                "page": page,
                "screenshot_path": f"{dist_path}/visual-check/mobile.png",
                "checks": [{"name": "page_loads", "passed": True}],
                "errors": [],
                "warnings": [],
            }

    monkeypatch.setattr("app.api.runs.VerificationRunner", lambda: FakeVerificationRunner())
    monkeypatch.setattr("app.api.runs.VisualVerificationService", lambda: FakeVisualVerificationService())

    with get_db() as session:
        run = SessionRun(
            id=run_id,
            session_id=session_id,
            trigger_source="chat",
            status="completed",
            input_message="build",
            metrics={
                "coordinator": {
                    "artifacts": {
                        "build": {
                            "status": "success",
                            "pages": ["index.html"],
                            "dist_path": dist_path,
                        }
                    }
                }
            },
        )
        session.add(run)
        session.commit()

    with TestClient(app) as client:
        response = client.post(
            f"/api/runs/{run_id}/verification",
            headers={"X-Admin-Token": "admin-secret"},
        )

    assert response.status_code == 200
    payload = response.json()
    visual_check = next(check for check in payload["verification"]["checks"] if check["name"] == "visual")
    assert visual_check["passed"] is True
    assert visual_check["details"]["quality_score"] == 95
    assert "Visual quality score: 95/100." in payload["verification"]["evidence"]
    assert payload["artifacts"]["visual_verification"]["quality_score"] == 95
    assert payload["verification"]["audit_trail"][-1]["type"] == "visual_verification_completed"


def test_runs_api_dogfood_verification_failure_auto_fix_and_gate_acceptance(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_TOKEN", "admin-secret")
    app = _create_app(tmp_path, monkeypatch)
    session_id = _seed_session()
    run_id = uuid.uuid4().hex

    class SequencedVerificationRunner:
        def __init__(self) -> None:
            self.calls = 0

        async def run_profile(self, profile):
            from app.schemas.run import VerificationRunResult

            assert profile["recommended_commands"]
            self.calls += 1
            if self.calls == 1:
                return VerificationRunResult(
                    status="failed",
                    passed=False,
                    risk_flags=["verification_failed"],
                    commands=[
                        {
                            "name": "backend targeted tests",
                            "command": "PYTHONPATH=.:../agent/src python -m pytest -q",
                            "scope": "backend",
                            "status": "failed",
                            "exit_code": 1,
                            "duration_ms": 12,
                            "output_summary": "app/services/review.py:88: AssertionError: leaked raw failure",
                            "failures": [
                                {
                                    "file": "app/services/review.py",
                                    "line": 88,
                                    "message": "AssertionError: leaked raw failure",
                                    "source": "pytest",
                                }
                            ],
                        }
                    ],
                )
            return VerificationRunResult(
                status="passed",
                passed=True,
                risk_flags=[],
                commands=[
                    {
                        "name": "backend targeted tests",
                        "command": "PYTHONPATH=.:../agent/src python -m pytest -q",
                        "scope": "backend",
                        "status": "passed",
                        "exit_code": 0,
                        "duration_ms": 9,
                        "output_summary": "1 passed",
                        "failures": [],
                    }
                ],
            )

    verification_runner = SequencedVerificationRunner()

    async def fake_execute_verification_fix(*, db, run, prompt):
        assert "app/services/review.py:88" in prompt
        assert "leaked raw failure" in prompt
        return {"message": "fixed leaked raw failure"}

    worktree_snapshots = [
        set(),
        {"packages/backend/app/services/review.py"},
    ]

    monkeypatch.setattr("app.api.runs.VerificationRunner", lambda: verification_runner)
    monkeypatch.setattr("app.api.runs._execute_verification_fix", fake_execute_verification_fix)
    monkeypatch.setattr("app.api.runs.capture_worktree_files", lambda: worktree_snapshots.pop(0))

    with get_db() as session:
        run = SessionRun(
            id=run_id,
            session_id=session_id,
            trigger_source="chat",
            status="completed",
            input_message="dogfood verification fix",
            metrics={
                "coordinator": {
                    "artifacts": {
                        "build": {"status": "success", "pages": ["index.html"]},
                        "review": {
                            "verdict": "pass",
                            "issues": [],
                            "summary": {"error_count": 0, "warning_count": 0},
                        },
                    }
                }
            },
        )
        session.add(run)
        session.commit()

    with TestClient(app) as client:
        failed = client.post(
            f"/api/runs/{run_id}/verification",
            headers={"X-Admin-Token": "admin-secret"},
        )
        fixed = client.post(
            f"/api/runs/{run_id}/fix-verification",
            headers={"X-Admin-Token": "admin-secret"},
        )

    assert failed.status_code == 200
    failed_verification = failed.json()["verification"]
    assert failed_verification["status"] == "failed"
    assert failed_verification["last_run"]["commands"][0]["failures"][0]["file"] == "app/services/review.py"
    assert failed_verification["last_run"]["commands"][0]["output_summary"] == ""
    assert "leaked raw failure" not in str(failed_verification["action_audit_trail"])

    assert fixed.status_code == 200
    verification = fixed.json()["verification"]
    assert verification["status"] == "passed"
    assert verification["last_run"]["status"] == "passed"
    assert verification["fix_attempts"][0]["status"] == "passed"
    assert verification["fix_attempts"][0]["prompt"] == ""
    assert verification["fix_attempts"][0]["engine"] is None
    assert verification["fix_attempts"][0]["change_summary"] == {
        "status": "captured",
        "changed_files": ["packages/backend/app/services/review.py"],
        "file_count": 1,
        "risk_level": "medium",
        "risk_flags": ["application_code_changed"],
        "verification_status": "passed",
        "captured_at": verification["fix_attempts"][0]["change_summary"]["captured_at"],
    }
    assert verification["fix_attempts"][0]["gate"]["status"] == "accepted"
    assert verification["fix_attempts"][0]["gate"]["decision"] == "auto_accepted"
    assert verification["fix_attempts"][0]["gate"]["approved"] is True
    assert [event["type"] for event in verification["audit_trail"]] == [
        "verification_started",
        "verification_completed",
        "verification_fix_started",
        "verification_fix_completed",
    ]
    assert [event["type"] for event in verification["action_audit_trail"]] == [
        "verification_run_started",
        "verification_command",
        "verification_fix_prompt",
        "verification_fix_started",
        "verification_command",
        "verification_fix_change_summary",
        "verification_fix_gate",
        "verification_fix_completed",
    ]
    assert "leaked raw failure" not in str(verification["action_audit_trail"])
    assert "fixed leaked raw failure" not in str(verification)


def test_runs_api_fix_verification_records_attempt_and_reruns(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_TOKEN", "admin-secret")
    app = _create_app(tmp_path, monkeypatch)
    session_id = _seed_session()
    run_id = uuid.uuid4().hex

    first_verification = {
        "status": "failed",
        "passed": False,
        "risk_flags": ["verification_failed"],
        "commands": [
            {
                "name": "backend targeted tests",
                "command": "PYTHONPATH=.:../agent/src python -m pytest -q",
                "scope": "backend",
                "status": "failed",
                "exit_code": 1,
                "duration_ms": 12,
                "output_summary": "app/api/runs.py:42: AssertionError",
                "failures": [
                    {
                        "file": "app/api/runs.py",
                        "line": 42,
                        "message": "AssertionError",
                        "source": "pytest",
                    }
                ],
            }
        ],
    }

    class FakeVerificationRunner:
        async def run_profile(self, profile):
            from app.schemas.run import VerificationRunResult

            assert profile["recommended_commands"]
            return VerificationRunResult(
                status="passed",
                passed=True,
                risk_flags=[],
                commands=[
                    {
                        "name": "backend targeted tests",
                        "command": "PYTHONPATH=.:../agent/src python -m pytest -q",
                        "scope": "backend",
                        "status": "passed",
                        "exit_code": 0,
                        "duration_ms": 10,
                        "output_summary": "1 passed",
                        "failures": [],
                    }
                ],
            )

    async def fake_execute_verification_fix(*, db, run, prompt):
        assert "app/api/runs.py:42" in prompt
        return {"message": "fixed verification failure"}

    worktree_snapshots = [
        {"packages/backend/app/api/runs.py"},
        {
            "packages/backend/app/api/runs.py",
            "packages/backend/app/services/change_summary.py",
        },
    ]

    monkeypatch.setattr("app.api.runs.VerificationRunner", lambda: FakeVerificationRunner())
    monkeypatch.setattr("app.api.runs._execute_verification_fix", fake_execute_verification_fix)
    monkeypatch.setattr("app.api.runs.capture_worktree_files", lambda: worktree_snapshots.pop(0))

    with get_db() as session:
        run = SessionRun(
            id=run_id,
            session_id=session_id,
            trigger_source="chat",
            status="completed",
            input_message="build",
            metrics={
                "coordinator": {
                    "artifacts": {
                        "build": {"status": "success", "pages": ["index.html"]},
                        "verification_run": first_verification,
                    }
                }
            },
        )
        session.add(run)
        session.commit()

    with TestClient(app) as client:
        blocked = client.post(f"/api/runs/{run_id}/fix-verification")
        response = client.post(
            f"/api/runs/{run_id}/fix-verification",
            headers={"X-Admin-Token": "admin-secret"},
        )
        detail = client.get(f"/api/runs/{run_id}")

    assert blocked.status_code == 401
    assert response.status_code == 200
    verification = response.json()["verification"]
    assert verification["last_run"]["status"] == "passed"
    assert verification["fix_attempts"][0]["status"] == "passed"
    assert verification["fix_attempts"][0]["prompt"] == ""
    assert verification["fix_attempts"][0]["engine"] is None
    assert verification["fix_attempts"][0]["change_summary"]["changed_files"] == [
        "packages/backend/app/services/change_summary.py"
    ]
    assert verification["fix_attempts"][0]["change_summary"]["risk_level"] == "medium"
    assert verification["fix_attempts"][0]["change_summary"]["verification_status"] == "passed"
    assert verification["fix_attempts"][0]["gate"]["status"] == "accepted"
    assert verification["fix_attempts"][0]["gate"]["decision"] == "auto_accepted"
    assert "diff" not in verification["fix_attempts"][0]["change_summary"]
    actions = verification["action_audit_trail"]
    assert [event["type"] for event in actions] == [
        "verification_fix_prompt",
        "verification_fix_started",
        "verification_command",
        "verification_fix_change_summary",
        "verification_fix_gate",
        "verification_fix_completed",
    ]
    assert actions[0]["category"] == "agent_prompt"
    assert actions[0]["summary"] == "Prepared automatic fix prompt with 1 failure item(s)."
    assert actions[-3]["category"] == "edit"
    assert actions[-3]["file_count"] == 1
    assert actions[-2]["category"] == "gate"
    assert actions[-2]["status"] == "accepted"
    assert "app/api/runs.py:42" not in str(actions)
    assert "fixed verification failure" not in str(actions)
    assert [event["type"] for event in verification["audit_trail"]] == [
        "verification_fix_started",
        "verification_fix_completed",
    ]
    assert detail.json()["fix_attempts"] == 1


def test_runs_api_fix_verification_blocks_high_risk_gate_and_allows_admin_resolution(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_TOKEN", "admin-secret")
    app = _create_app(tmp_path, monkeypatch)
    session_id = _seed_session()
    run_id = uuid.uuid4().hex

    class FakeVerificationRunner:
        async def run_profile(self, profile):
            from app.schemas.run import VerificationRunResult

            return VerificationRunResult(status="passed", passed=True, commands=[])

    async def fake_execute_verification_fix(*, db, run, prompt):
        return {"message": "fixed sensitive settings"}

    worktree_snapshots = [
        set(),
        {"packages/backend/app/api/auth.py"},
    ]
    monkeypatch.setattr("app.api.runs.VerificationRunner", lambda: FakeVerificationRunner())
    monkeypatch.setattr("app.api.runs._execute_verification_fix", fake_execute_verification_fix)
    monkeypatch.setattr("app.api.runs.capture_worktree_files", lambda: worktree_snapshots.pop(0))

    with get_db() as session:
        run = SessionRun(
            id=run_id,
            session_id=session_id,
            trigger_source="chat",
            status="completed",
            input_message="build",
            metrics={
                "coordinator": {
                    "artifacts": {
                        "verification_run": {
                            "status": "failed",
                            "passed": False,
                            "commands": [],
                        },
                    }
                }
            },
        )
        session.add(run)
        session.commit()

    with TestClient(app) as client:
        fix_response = client.post(
            f"/api/runs/{run_id}/fix-verification",
            headers={"X-Admin-Token": "admin-secret"},
        )
        blocked_resolution = client.post(
            f"/api/runs/{run_id}/fix-verification/1/gate",
            json={"approved": True},
        )
        resolved = client.post(
            f"/api/runs/{run_id}/fix-verification/1/gate",
            json={"approved": True},
            headers={"X-Admin-Token": "admin-secret"},
        )

    assert fix_response.status_code == 200
    attempt = fix_response.json()["verification"]["fix_attempts"][0]
    assert attempt["gate"]["status"] == "blocked"
    assert attempt["gate"]["decision"] == "requires_review"
    assert "high_risk_change" in attempt["gate"]["reasons"]
    assert "sensitive_files_changed" in attempt["gate"]["reasons"]
    assert attempt["gate"]["reviewer"]["source"] == "deterministic_reviewer"
    assert attempt["gate"]["reviewer"]["recommendation"] == "review_required"
    assert "manual review" in attempt["gate"]["reviewer"]["summary"]
    assert blocked_resolution.status_code == 401
    assert resolved.status_code == 200
    resolved_attempt = resolved.json()["verification"]["fix_attempts"][0]
    assert resolved_attempt["gate"]["status"] == "accepted"
    assert resolved_attempt["gate"]["decision"] == "manual_approved"
    assert resolved_attempt["gate"]["approved"] is True
    assert resolved_attempt["gate"]["approved_at"]
    assert resolved.json()["verification"]["action_audit_trail"][-1]["type"] == "verification_fix_gate_resolved"


def test_runs_api_fix_gate_review_endpoint_refreshes_reviewer_recommendation(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_TOKEN", "admin-secret")
    app = _create_app(tmp_path, monkeypatch)
    session_id = _seed_session()
    run_id = uuid.uuid4().hex

    with get_db() as session:
        run = SessionRun(
            id=run_id,
            session_id=session_id,
            trigger_source="chat",
            status="completed",
            input_message="build",
            metrics={
                "coordinator": {
                    "artifacts": {
                        "verification_fix_attempts": [
                            {
                                "attempt": 1,
                                "status": "failed",
                                "prompt": "secret prompt",
                                "failures": [],
                                "verification": {"status": "failed", "passed": False, "commands": []},
                                "change_summary": {
                                    "status": "captured",
                                    "changed_files": ["packages/backend/app/api/runs.py"],
                                    "file_count": 1,
                                    "risk_level": "medium",
                                    "risk_flags": ["verification_not_passing"],
                                    "verification_status": "failed",
                                },
                                "gate": {
                                    "status": "blocked",
                                    "decision": "requires_review",
                                    "reasons": ["verification_not_passing"],
                                },
                            }
                        ]
                    }
                }
            },
        )
        session.add(run)
        session.commit()

    with TestClient(app) as client:
        blocked = client.post(f"/api/runs/{run_id}/fix-verification/1/gate/review")
        response = client.post(
            f"/api/runs/{run_id}/fix-verification/1/gate/review",
            headers={"X-Admin-Token": "admin-secret"},
        )

    assert blocked.status_code == 401
    assert response.status_code == 200
    gate = response.json()["verification"]["fix_attempts"][0]["gate"]
    assert gate["reviewer"]["recommendation"] == "reject"
    assert "verification passes" in gate["reviewer"]["summary"]
    assert "secret prompt" not in str(gate["reviewer"])
    assert response.json()["verification"]["action_audit_trail"][-1]["type"] == "verification_fix_gate_reviewed"


def test_runs_api_fix_gate_resolution_rejects_already_resolved_gate(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_TOKEN", "admin-secret")
    app = _create_app(tmp_path, monkeypatch)
    session_id = _seed_session()
    run_id = uuid.uuid4().hex

    with get_db() as session:
        session.add(
            SessionRun(
                id=run_id,
                session_id=session_id,
                trigger_source="chat",
                status="completed",
                input_message="build",
                metrics={
                    "coordinator": {
                        "artifacts": {
                            "verification_fix_attempts": [
                                {
                                    "attempt": 1,
                                    "status": "passed",
                                    "prompt": "",
                                    "failures": [],
                                    "gate": {
                                        "status": "accepted",
                                        "decision": "manual_approved",
                                        "reasons": ["high_risk_change"],
                                        "approved": True,
                                    },
                                }
                            ]
                        }
                    }
                },
            )
        )
        session.commit()

    with TestClient(app) as client:
        response = client.post(
            f"/api/runs/{run_id}/fix-verification/1/gate",
            json={"approved": False},
            headers={"X-Admin-Token": "admin-secret"},
        )

    assert response.status_code == 409
    assert response.json()["detail"] == "Verification fix gate is already resolved"


def test_runs_api_fix_verification_persists_error_attempt(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_TOKEN", "admin-secret")
    app = _create_app(tmp_path, monkeypatch)
    session_id = _seed_session()
    run_id = uuid.uuid4().hex

    async def failing_execute_verification_fix(*, db, run, prompt):
        raise RuntimeError("agent crashed")

    monkeypatch.setattr("app.api.runs._execute_verification_fix", failing_execute_verification_fix)

    with get_db() as session:
        run = SessionRun(
            id=run_id,
            session_id=session_id,
            trigger_source="chat",
            status="completed",
            input_message="build",
            metrics={
                "coordinator": {
                    "artifacts": {
                        "build": {"status": "success", "pages": ["index.html"]},
                        "verification_run": {
                            "status": "failed",
                            "passed": False,
                            "commands": [
                                {
                                    "name": "backend targeted tests",
                                    "command": "PYTHONPATH=.:../agent/src python -m pytest -q",
                                    "scope": "backend",
                                    "status": "failed",
                                    "output_summary": "failure",
                                    "failures": [{"message": "failure", "source": "pytest"}],
                                }
                            ],
                        },
                    }
                }
            },
        )
        session.add(run)
        session.commit()

    with TestClient(app) as client:
        response = client.post(
            f"/api/runs/{run_id}/fix-verification",
            headers={"X-Admin-Token": "admin-secret"},
        )

    assert response.status_code == 200
    attempt = response.json()["verification"]["fix_attempts"][0]
    assert attempt["status"] == "error"
    assert "agent crashed" in attempt["error"]
    assert attempt["prompt"] == ""
    assert attempt["started_at"]
    assert attempt["completed_at"]
    assert response.json()["verification"]["audit_trail"][-1]["status"] == "error"


def test_runs_api_fix_verification_rejects_concurrent_attempt(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_TOKEN", "admin-secret")
    app = _create_app(tmp_path, monkeypatch)
    session_id = _seed_session()
    run_id = uuid.uuid4().hex

    from app.api import runs as runs_api

    with get_db() as session:
        run = SessionRun(
            id=run_id,
            session_id=session_id,
            trigger_source="chat",
            status="completed",
            input_message="build",
            metrics={
                "coordinator": {
                    "artifacts": {
                        "verification_run": {
                            "status": "failed",
                            "passed": False,
                            "commands": [],
                        }
                    }
                }
            },
        )
        session.add(run)
        session.commit()

    assert runs_api._try_acquire_verification_fix(run_id) is True
    try:
        with TestClient(app) as client:
            response = client.post(
                f"/api/runs/{run_id}/fix-verification",
                headers={"X-Admin-Token": "admin-secret"},
            )
    finally:
        runs_api._release_verification_fix(run_id)

    assert response.status_code == 409
    assert "already running" in response.json()["detail"]


def test_runs_api_fix_verification_recovers_stale_running_attempt(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_TOKEN", "admin-secret")
    app = _create_app(tmp_path, monkeypatch)
    session_id = _seed_session()
    run_id = uuid.uuid4().hex

    class FakeVerificationRunner:
        async def run_profile(self, profile):
            from app.schemas.run import VerificationRunResult

            return VerificationRunResult(status="passed", passed=True, commands=[])

    async def fake_execute_verification_fix(*, db, run, prompt):
        return {"message": "fixed after stale recovery"}

    monkeypatch.setattr("app.api.runs.VerificationRunner", lambda: FakeVerificationRunner())
    monkeypatch.setattr("app.api.runs._execute_verification_fix", fake_execute_verification_fix)

    with get_db() as session:
        run = SessionRun(
            id=run_id,
            session_id=session_id,
            trigger_source="chat",
            status="completed",
            input_message="build",
            metrics={
                "coordinator": {
                    "artifacts": {
                        "verification_run": {
                            "status": "failed",
                            "passed": False,
                            "commands": [],
                        },
                        "verification_fix_attempts": [
                            {
                                "attempt": 1,
                                "status": "running",
                                "prompt": "old prompt",
                                "failures": [],
                                "started_at": "2020-01-01T00:00:00Z",
                            }
                        ],
                    }
                }
            },
        )
        session.add(run)
        session.commit()

    with TestClient(app) as client:
        response = client.post(
            f"/api/runs/{run_id}/fix-verification",
            headers={"X-Admin-Token": "admin-secret"},
        )

    assert response.status_code == 200
    attempts = response.json()["verification"]["fix_attempts"]
    assert attempts[0]["status"] == "stale_error"
    assert attempts[1]["status"] == "passed"
    event_types = [event["type"] for event in response.json()["verification"]["audit_trail"]]
    assert "verification_fix_recovered" in event_types


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
