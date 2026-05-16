import asyncio
import importlib
import uuid

import pytest

from app.db.database import Database
from app.db.migrations import init_db
from app.db.models import Session as SessionModel
from app.db.models import SessionEvent, SessionRun
from app.db.utils import get_db, transaction_scope
from app.events.emitter import EventEmitter
from app.events.models import run_lifecycle_event
from app.events.types import EventType
from app.services.event_store import EventStoreService
from app.services.run import RunCancelledError, RunService


def _create_database(tmp_path, name: str) -> Database:
    db_path = tmp_path / name
    database = Database(f"sqlite:///{db_path}")
    init_db(database)
    return database


def _seed_run(database: Database, *, metrics: dict | None = None, status: str = "queued") -> str:
    session_id = uuid.uuid4().hex
    with transaction_scope(database) as session:
        session.add(SessionModel(id=session_id, title="Run Coordinator Test"))
        run = SessionRun(
            session_id=session_id,
            trigger_source="chat",
            status=status,
            input_message="build a mobile coffee shop",
            checkpoint_thread=f"{session_id}:coordinator-test",
            metrics=metrics or {},
        )
        session.add(run)
        session.flush([run])
        run_id = run.id
    return run_id


def _load_run_coordinator_contract():
    try:
        module = importlib.import_module("app.engine.run_coordinator")
    except ModuleNotFoundError as exc:
        if exc.name == "app.engine.run_coordinator":
            pytest.xfail("RunCoordinator has not landed yet")
        raise

    missing = [
        name
        for name in ("RunCoordinator", "RunCoordinatorPhases")
        if not hasattr(module, name)
    ]
    if missing:
        pytest.xfail(f"RunCoordinator contract missing symbols: {', '.join(missing)}")

    return module.RunCoordinator, module.RunCoordinatorPhases


class _FakePhases:
    def __init__(self, review_results: list[dict] | None = None) -> None:
        self.calls: list[str] = []
        self.review_results = list(review_results or [{"passed": True}])

    async def build(self, _context):
        self.calls.append("build")
        return {"artifact_id": "build-1", "pages": ["index"]}

    async def review(self, _context):
        self.calls.append("review")
        if self.review_results:
            return self.review_results.pop(0)
        return {"passed": True}

    async def fix(self, _context):
        self.calls.append("fix")
        return {"fixed": True, "changes": ["added viewport meta"]}


class _FakeImplementPhases(_FakePhases):
    def __init__(
        self,
        *,
        implement_results: list[dict],
        review_results: list[dict] | None = None,
    ) -> None:
        super().__init__(review_results=review_results)
        self.implement_results = list(implement_results)

    async def implement(self, context):
        self.calls.append("implement")
        if self.implement_results:
            result = dict(self.implement_results.pop(0))
        else:
            result = {"is_complete": True, "action": "pages_generated"}
        result["resume_payload"] = context.get("resume_payload")
        return result


def _make_coordinator(
    db,
    fake_phases: _FakePhases,
    *,
    max_fix_attempts: int = 2,
    implement=None,
):
    RunCoordinator, RunCoordinatorPhases = _load_run_coordinator_contract()
    phases = RunCoordinatorPhases(
        build=fake_phases.build,
        review=fake_phases.review,
        fix=fake_phases.fix,
        implement=implement,
    )
    return RunCoordinator(
        db=db,
        run_service=RunService(db),
        event_store=EventStoreService(db),
        phases=phases,
        max_fix_attempts=max_fix_attempts,
    )


def _run_coordinator(coordinator, run_id: str):
    return asyncio.run(coordinator.run(run_id))


def _stored_run(database: Database, run_id: str) -> SessionRun:
    with get_db(database) as session:
        run = session.get(SessionRun, run_id)
        assert run is not None
        session.expunge(run)
        return run


def _coordinator_state(run: SessionRun) -> dict:
    assert isinstance(run.metrics, dict)
    state = run.metrics.get("coordinator")
    assert isinstance(state, dict)
    return state


def test_run_coordinator_completes_when_review_passes_without_fixing(tmp_path) -> None:
    database = _create_database(tmp_path, "run-coordinator-pass.db")
    run_id = _seed_run(database)
    fake_phases = _FakePhases(review_results=[{"passed": True, "findings": []}])

    with get_db(database) as session:
        coordinator = _make_coordinator(session, fake_phases)
        _run_coordinator(coordinator, run_id)
        session.commit()

    stored = _stored_run(database, run_id)
    state = _coordinator_state(stored)
    assert stored.status == "completed"
    assert fake_phases.calls == ["build", "review"]
    assert [item["phase"] for item in state["phase_history"]] == ["build", "review"]
    phase_metadata = RunService.get_phase_metadata(stored)
    assert phase_metadata["phase"] == "review"
    assert phase_metadata["status"] == "completed"
    assert phase_metadata["result"] == {"passed": True, "findings": []}
    assert phase_metadata["completed_at"]


def test_run_coordinator_runs_fix_once_when_initial_review_fails(tmp_path) -> None:
    database = _create_database(tmp_path, "run-coordinator-fix.db")
    run_id = _seed_run(database)
    fake_phases = _FakePhases(
        review_results=[
            {"passed": False, "findings": ["missing viewport meta"]},
            {"passed": True, "findings": []},
        ]
    )

    with get_db(database) as session:
        coordinator = _make_coordinator(session, fake_phases)
        _run_coordinator(coordinator, run_id)
        session.commit()

    stored = _stored_run(database, run_id)
    state = _coordinator_state(stored)
    assert stored.status == "completed"
    assert fake_phases.calls == ["build", "review", "fix", "review"]
    assert state["fix_attempts"] == 1

    with get_db(database) as session:
        event_types = [
            row.type
            for row in session.query(SessionEvent)
            .filter(
                SessionEvent.run_id == run_id,
                SessionEvent.type.in_(["verify_start", "verify_fail", "verify_pass"]),
            )
            .order_by(SessionEvent.seq.asc())
            .all()
        ]
    assert event_types == ["verify_start", "verify_fail", "verify_start", "verify_pass"]


def test_run_coordinator_plan_mode_stops_after_implement(tmp_path) -> None:
    database = _create_database(tmp_path, "run-coordinator-plan-mode.db")
    run_id = _seed_run(database, metrics={"approval_mode": "plan"})
    fake_phases = _FakeImplementPhases(
        implement_results=[{"is_complete": True, "action": "plan_created"}],
        review_results=[{"passed": True}],
    )

    with get_db(database) as session:
        coordinator = _make_coordinator(
            session,
            fake_phases,
            implement=fake_phases.implement,
        )
        result = _run_coordinator(coordinator, run_id)
        session.commit()

    stored = _stored_run(database, run_id)
    state = _coordinator_state(stored)
    assert result.status == "completed"
    assert stored.status == "completed"
    assert fake_phases.calls == ["implement"]
    assert [item["phase"] for item in state["phase_history"]] == ["implement"]
    assert state["current_phase"] == "done"
    assert state["artifacts"]["implement"]["action"] == "plan_created"
    assert "build" not in state["artifacts"]
    assert "review" not in state["artifacts"]


def test_run_coordinator_execution_mode_plan_stops_after_implement(tmp_path) -> None:
    database = _create_database(tmp_path, "run-coordinator-execution-mode-plan.db")
    run_id = _seed_run(database, metrics={"execution_mode": "plan"})
    fake_phases = _FakeImplementPhases(
        implement_results=[{"is_complete": True, "action": "plan_created"}],
        review_results=[{"passed": True}],
    )

    with get_db(database) as session:
        coordinator = _make_coordinator(
            session,
            fake_phases,
            implement=fake_phases.implement,
        )
        result = _run_coordinator(coordinator, run_id)
        session.commit()

    stored = _stored_run(database, run_id)
    state = _coordinator_state(stored)
    assert result.status == "completed"
    assert stored.status == "completed"
    assert fake_phases.calls == ["implement"]
    assert [item["phase"] for item in state["phase_history"]] == ["implement"]
    assert state["current_phase"] == "done"
    assert "build" not in state["artifacts"]
    assert "review" not in state["artifacts"]


def test_run_coordinator_legacy_yolo_mode_runs_build_and_review(tmp_path) -> None:
    database = _create_database(tmp_path, "run-coordinator-yolo-mode.db")
    run_id = _seed_run(database, metrics={"execution_mode": "yolo"})
    fake_phases = _FakeImplementPhases(
        implement_results=[{"is_complete": True, "action": "pages_generated"}],
        review_results=[{"passed": True}],
    )

    with get_db(database) as session:
        coordinator = _make_coordinator(
            session,
            fake_phases,
            implement=fake_phases.implement,
        )
        _run_coordinator(coordinator, run_id)
        session.commit()

    assert fake_phases.calls == ["implement", "build", "review"]


def test_run_coordinator_passes_fresh_artifacts_to_each_phase(tmp_path) -> None:
    database = _create_database(tmp_path, "run-coordinator-fresh-context.db")
    run_id = _seed_run(database)
    RunCoordinator, RunCoordinatorPhases = _load_run_coordinator_contract()
    calls: list[str] = []

    async def build(context):
        calls.append("build")
        assert context["artifacts"] == {}
        return {"artifact_id": "build-1", "pages": ["index"]}

    async def review(context):
        calls.append("review")
        artifacts = context["artifacts"]
        assert artifacts["build"]["artifact_id"] == "build-1"
        if "fix" not in artifacts:
            return {"passed": False, "issues": [{"code": "needs_fix"}]}
        assert artifacts["fix"]["fixed"] is True
        assert context["fix_attempts"] == 1
        return {"passed": True, "issues": []}

    async def fix(context):
        calls.append("fix")
        artifacts = context["artifacts"]
        assert artifacts["build"]["artifact_id"] == "build-1"
        assert context["review"]["issues"][0]["code"] == "needs_fix"
        assert context["fix_attempt"] == 1
        return {"fixed": True}

    phases = RunCoordinatorPhases(build=build, review=review, fix=fix)

    with get_db(database) as session:
        coordinator = RunCoordinator(
            db=session,
            run_service=RunService(session),
            event_store=EventStoreService(session),
            phases=phases,
            max_fix_attempts=1,
        )
        result = _run_coordinator(coordinator, run_id)
        session.commit()

    assert result.status == "completed"
    assert calls == ["build", "review", "fix", "review"]


def test_run_coordinator_resumes_from_persisted_build_checkpoint(tmp_path) -> None:
    database = _create_database(tmp_path, "run-coordinator-resume.db")
    run_id = _seed_run(
        database,
        status="running",
        metrics={
            "coordinator": {
                "current_phase": "review",
                "fix_attempts": 0,
                "artifacts": {"build": {"artifact_id": "build-1", "pages": ["index"]}},
                "phase_history": [
                    {
                        "phase": "build",
                        "status": "completed",
                        "output": {"artifact_id": "build-1", "pages": ["index"]},
                    }
                ],
            }
        },
    )
    fake_phases = _FakePhases(review_results=[{"passed": True, "findings": []}])

    with get_db(database) as session:
        coordinator = _make_coordinator(session, fake_phases)
        _run_coordinator(coordinator, run_id)
        session.commit()

    stored = _stored_run(database, run_id)
    state = _coordinator_state(stored)
    assert stored.status == "completed"
    assert fake_phases.calls == ["review"]
    assert [item["phase"] for item in state["phase_history"]] == ["build", "review"]


def test_run_coordinator_resumes_waiting_input_implement_phase(tmp_path) -> None:
    database = _create_database(tmp_path, "run-coordinator-waiting-resume.db")
    run_id = _seed_run(database)
    fake_phases = _FakeImplementPhases(
        implement_results=[
            {
                "status": "waiting_input",
                "message": "Which visual direction should I use?",
            },
            {
                "is_complete": True,
                "action": "pages_generated",
            },
        ],
        review_results=[{"passed": True, "findings": []}],
    )

    with get_db(database) as session:
        coordinator = _make_coordinator(
            session,
            fake_phases,
            implement=fake_phases.implement,
        )
        result = _run_coordinator(coordinator, run_id)
        session.commit()

    assert result.status == "waiting_input"
    stored = _stored_run(database, run_id)
    state = _coordinator_state(stored)
    assert stored.status == "waiting_input"
    assert state["current_phase"] == "implement"
    assert state["phase_history"][0]["phase"] == "implement"
    assert state["phase_history"][0]["status"] == "waiting_input"
    assert RunService.get_phase_metadata(stored)["status"] == "waiting_input"

    with get_db(database) as session:
        RunService(session).resume_run(run_id, {"user_feedback": "Use a crisp editorial style"})
        session.commit()

    with get_db(database) as session:
        coordinator = _make_coordinator(
            session,
            fake_phases,
            implement=fake_phases.implement,
        )
        result = _run_coordinator(coordinator, run_id)
        session.commit()

    stored = _stored_run(database, run_id)
    state = _coordinator_state(stored)
    assert result.status == "completed"
    assert stored.status == "completed"
    assert fake_phases.calls == ["implement", "implement", "build", "review"]
    assert [item["phase"] for item in state["phase_history"]] == [
        "implement",
        "implement",
        "build",
        "review",
    ]
    assert state["artifacts"]["implement"]["resume_payload"] == {
        "user_feedback": "Use a crisp editorial style",
    }


def test_run_coordinator_fails_and_checkpoints_timed_out_phase(tmp_path) -> None:
    database = _create_database(tmp_path, "run-coordinator-timeout.db")
    run_id = _seed_run(database)
    RunCoordinator, RunCoordinatorPhases = _load_run_coordinator_contract()

    async def slow_build(_context):
        await asyncio.sleep(0.05)
        return {"artifact_id": "late"}

    phases = RunCoordinatorPhases(
        build=slow_build,
        review=lambda _context: {"passed": True},
        fix=lambda _context: {"fixed": True},
    )

    with get_db(database) as session:
        coordinator = RunCoordinator(
            db=session,
            run_service=RunService(session),
            event_store=EventStoreService(session),
            phases=phases,
            phase_timeout_seconds=0.01,
        )
        with pytest.raises(asyncio.TimeoutError):
            _run_coordinator(coordinator, run_id)
        session.commit()

    stored = _stored_run(database, run_id)
    state = _coordinator_state(stored)
    assert stored.status == "failed"
    assert stored.latest_error["phase"] == "build"
    assert state["phase_history"][0]["phase"] == "build"
    assert state["phase_history"][0]["status"] == "failed"
    assert RunService.get_phase_metadata(stored)["status"] == "failed"


def test_run_coordinator_persists_cancelled_phase_without_failure(tmp_path) -> None:
    database = _create_database(tmp_path, "run-coordinator-cancelled.db")
    run_id = _seed_run(database)
    RunCoordinator, RunCoordinatorPhases = _load_run_coordinator_contract()

    async def cancelled_build(_context):
        raise RunCancelledError("cancel requested")

    phases = RunCoordinatorPhases(
        build=cancelled_build,
        review=lambda _context: {"passed": True},
        fix=lambda _context: {"fixed": True},
    )

    with get_db(database) as session:
        coordinator = RunCoordinator(
            db=session,
            run_service=RunService(session),
            event_store=EventStoreService(session),
            phases=phases,
        )
        with pytest.raises(RunCancelledError):
            _run_coordinator(coordinator, run_id)
        session.commit()

    stored = _stored_run(database, run_id)
    state = _coordinator_state(stored)
    assert stored.status == "cancelled"
    assert stored.latest_error is None
    assert state["phase_history"][0]["phase"] == "build"
    assert state["phase_history"][0]["status"] == "cancelled"
    assert RunService.get_phase_metadata(stored)["status"] == "cancelled"

    with get_db(database) as session:
        event = (
            session.query(SessionEvent)
            .filter(SessionEvent.run_id == run_id, SessionEvent.type == "run_cancelled")
            .one()
        )
        assert event.payload["payload"]["status"] == "cancelled"


def test_event_emitter_persists_run_scoped_events_before_returning() -> None:
    class RecordingStore:
        _use_separate_session = True

        def __init__(self) -> None:
            self.recorded = []

        def record_event(self, event) -> None:
            import time

            time.sleep(0.05)
            self.recorded.append(event)

    async def emit_inside_running_loop(store: RecordingStore) -> None:
        emitter = EventEmitter(
            session_id="session-sync",
            run_id="run-sync",
            event_store=store,
        )
        emitter.emit(
            run_lifecycle_event(
                EventType.RUN_COMPLETED,
                phase="done",
                status="completed",
            )
        )

    store = RecordingStore()
    asyncio.run(emit_inside_running_loop(store))

    assert len(store.recorded) == 1
    assert store.recorded[0].run_id == "run-sync"
