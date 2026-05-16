import uuid
from datetime import timedelta

import pytest

from app.db.database import Database
from app.db.migrations import init_db
from app.db.models import Session as SessionModel, SessionRun
from app.db.utils import get_db, transaction_scope
from app.schemas.run import RunPhase, RunStatus
from app.services.run import RunNotFoundError, RunService, RunStateConflictError
from app.utils.datetime import utcnow


def _create_database(tmp_path, name: str) -> Database:
    db_path = tmp_path / name
    database = Database(f"sqlite:///{db_path}")
    init_db(database)
    return database


def _seed_session(database: Database) -> str:
    session_id = uuid.uuid4().hex
    with transaction_scope(database) as session:
        session.add(SessionModel(id=session_id, title="Run Service Test"))
    return session_id


def test_create_run_defaults_and_checkpoint_thread(tmp_path) -> None:
    database = _create_database(tmp_path, "run-service-create.db")
    session_id = _seed_session(database)

    with get_db(database) as session:
        service = RunService(session)
        run = service.create_run(
            session_id=session_id,
            message="generate",
            generate_now=True,
            target_pages=["index"],
        )
        run_payload = {
            "id": run.id,
            "status": run.status,
            "started_at": run.started_at,
            "finished_at": run.finished_at,
            "checkpoint_thread": run.checkpoint_thread,
            "metrics": run.metrics,
        }
        session.commit()

    assert run_payload["status"] == "queued"
    assert run_payload["started_at"] is None
    assert run_payload["finished_at"] is None
    assert run_payload["checkpoint_thread"] == f"{session_id}:{run_payload['id']}"
    assert run_payload["metrics"] == {
        "generate_now": True,
        "execution_mode": "agent",
        "approval_mode": "agent",
        "target_pages": ["index"],
    }


def test_run_state_transitions_and_conflicts(tmp_path) -> None:
    database = _create_database(tmp_path, "run-service-transitions.db")
    session_id = _seed_session(database)

    with get_db(database) as session:
        service = RunService(session)
        run = service.create_run(session_id=session_id, message="hello")
        session.commit()
        run_id = run.id

    with get_db(database) as session:
        service = RunService(session)
        running = service.start_run(run_id)
        running_status = running.status
        running_started_at = running.started_at
        session.commit()

    assert running_status == "running"
    assert running_started_at is not None

    with get_db(database) as session:
        service = RunService(session)
        waiting = service.persist_run_state(run_id, "waiting_input")
        waiting_status = waiting.status
        session.commit()

    assert waiting_status == "waiting_input"

    with get_db(database) as session:
        service = RunService(session)
        resumed = service.resume_run(run_id, {"ok": True})
        resumed_status = resumed.status
        resumed_payload = resumed.resume_payload
        session.commit()

    assert resumed_status == "running"
    assert resumed_payload == {"ok": True}

    with get_db(database) as session:
        service = RunService(session)
        completed = service.persist_run_state(run_id, "completed")
        completed_status = completed.status
        completed_finished_at = completed.finished_at
        session.commit()

    assert completed_status == "completed"
    assert completed_finished_at is not None

    with get_db(database) as session:
        service = RunService(session)
        with pytest.raises(RunStateConflictError):
            service.persist_run_state(run_id, "running")


def test_create_run_rejects_second_active_run_for_session(tmp_path) -> None:
    database = _create_database(tmp_path, "run-service-active-unique.db")
    session_id = _seed_session(database)

    with get_db(database) as session:
        service = RunService(session)
        service.create_run(session_id=session_id, message="first")
        session.commit()

    with get_db(database) as session:
        service = RunService(session)
        with pytest.raises(RunStateConflictError):
            service.create_run(session_id=session_id, message="second")


def test_run_phase_metadata_persisted_in_metrics(tmp_path) -> None:
    database = _create_database(tmp_path, "run-service-phase.db")
    session_id = _seed_session(database)

    with get_db(database) as session:
        service = RunService(session)
        run = service.create_run(
            session_id=session_id,
            message="hello",
            generate_now=True,
            target_pages=["index"],
        )
        run_id = run.id
        session.commit()

    with get_db(database) as session:
        service = RunService(session)
        updated = service.persist_run_phase(
            run_id,
            RunPhase.BUILD,
            status=RunStatus.RUNNING,
            step="assets",
        )
        metrics = dict(updated.metrics)
        phase_metadata = service.get_phase_metadata(updated)
        session.commit()

    assert metrics["generate_now"] is True
    assert metrics["target_pages"] == ["index"]
    assert metrics["phase"] == "build"
    assert metrics["phase_status"] == "running"
    assert phase_metadata == {"phase": "build", "status": "running", "step": "assets"}

    with get_db(database) as session:
        service = RunService(session)
        stored = service.get_run(run_id)
        assert service.get_phase_metadata(stored) == {
            "phase": "build",
            "status": "running",
            "step": "assets",
        }


def test_resume_requires_waiting_input(tmp_path) -> None:
    database = _create_database(tmp_path, "run-service-resume.db")
    session_id = _seed_session(database)

    with get_db(database) as session:
        service = RunService(session)
        run = service.create_run(session_id=session_id, message="hello")
        session.commit()

        with pytest.raises(RunStateConflictError):
            service.resume_run(run.id, {"data": 1})


def test_cancel_idempotency(tmp_path) -> None:
    database = _create_database(tmp_path, "run-service-cancel.db")
    session_id = _seed_session(database)

    with get_db(database) as session:
        service = RunService(session)
        run = service.create_run(session_id=session_id, message="hello")
        session.commit()
        run_id = run.id

    with get_db(database) as session:
        service = RunService(session)
        cancelled, accepted = service.cancel_run(run_id)
        cancelled_status = cancelled.status
        session.commit()

    assert accepted is True
    assert cancelled_status == "cancelled"

    with get_db(database) as session:
        service = RunService(session)
        cancelled_again, accepted_again = service.cancel_run(run_id)
        cancelled_again_status = cancelled_again.status
        session.commit()

    assert accepted_again is False
    assert cancelled_again_status == "cancelled"


def test_active_run_lookup_stale_failure_and_heartbeat(tmp_path) -> None:
    database = _create_database(tmp_path, "run-service-active-stale.db")
    session_id = _seed_session(database)

    with get_db(database) as session:
        service = RunService(session)
        active = service.create_run(session_id=session_id, message="hello")
        service.start_run(active.id)
        heartbeat = service.heartbeat_run(
            active.id,
            phase=RunPhase.IMPLEMENT,
            status=RunStatus.RUNNING,
            step="thinking",
        )
        run_id = active.id
        heartbeat_payload = heartbeat.metrics["heartbeat"]
        session.commit()

    assert heartbeat_payload["phase"] == "implement"
    assert heartbeat_payload["status"] == "running"
    assert heartbeat_payload["step"] == "thinking"

    with get_db(database) as session:
        service = RunService(session)
        active = service.get_latest_active_run(session_id)
        assert active is not None
        assert active.id == run_id

        stale = session.get(SessionRun, run_id)
        assert stale is not None
        stale.updated_at = utcnow() - timedelta(hours=2)
        session.add(stale)
        session.commit()

    with get_db(database) as session:
        service = RunService(session)
        failed = service.fail_stale_runs(
            session_id=session_id,
            stale_after_seconds=60,
        )
        failed_ids = [run.id for run in failed]
        session.commit()

    assert failed_ids == [run_id]

    with get_db(database) as session:
        service = RunService(session)
        stored = session.get(SessionRun, run_id)
        assert stored is not None
        assert stored.status == "failed"
        assert stored.latest_error["code"] == "run_stale_timeout"
        assert service.get_latest_active_run(session_id) is None


def test_get_run_not_found(tmp_path) -> None:
    database = _create_database(tmp_path, "run-service-notfound.db")

    with get_db(database) as session:
        service = RunService(session)
        with pytest.raises(RunNotFoundError):
            service.get_run("missing")
