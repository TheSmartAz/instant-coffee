import asyncio
import uuid

import pytest

from app.config import refresh_settings
from app.db.database import Database
from app.db.migrations import init_db
from app.db.models import Session as SessionModel
from app.db.models import SessionEvent
from app.db.utils import get_db, transaction_scope
from app.events.emitter import EventEmitter
from app.graph.orchestrator import LangGraphOrchestrator
from app.services.event_store import EventStoreService
from app.services.run import RunService


def _make_database(tmp_path, name: str = "b3-orch.db") -> Database:
    db_path = tmp_path / name
    database = Database(f"sqlite:///{db_path}")
    init_db(database)
    return database


def _seed_session(database: Database, session_id: str | None = None) -> str:
    sid = session_id or uuid.uuid4().hex
    with transaction_scope(database) as session:
        session.add(SessionModel(id=sid, title="B3 Test Session"))
    return sid


async def _collect_responses(orchestrator: LangGraphOrchestrator, **kwargs):
    items = []
    async for item in orchestrator.stream_responses(**kwargs):
        items.append(item)
    return items


def _common_stream_kwargs(message: str = "hello", resume: dict | None = None) -> dict:
    return {
        "user_message": message,
        "output_dir": "instant-coffee-output",
        "history": [],
        "trigger_interview": False,
        "generate_now": True,
        "style_reference": None,
        "target_pages": ["index"],
        "resume": resume,
    }


@pytest.mark.parametrize("resume", [None])
def test_run_created_started_completed_via_orchestrator(tmp_path, monkeypatch, resume):
    monkeypatch.setenv("LANGGRAPH_CHECKPOINTER", "memory")
    refresh_settings()

    database = _make_database(tmp_path, "b3-run-lifecycle.db")
    session_id = _seed_session(database)

    with get_db(database) as db:
        session = db.get(SessionModel, session_id)
        emitter = EventEmitter(session_id=session_id, event_store=EventStoreService(db))
        orchestrator = LangGraphOrchestrator(db, session, emitter)

        responses = asyncio.run(_collect_responses(orchestrator, **_common_stream_kwargs(resume=resume)))
        assert responses

        runs = RunService(db).list_runs(session_id)
        assert len(runs) == 1
        run = runs[0]
        assert run.status == "waiting_input"
        assert run.checkpoint_thread == f"{session_id}:{run.id}"

        event_types = [
            row.type
            for row in db.query(SessionEvent)
            .filter(SessionEvent.session_id == session_id, SessionEvent.run_id == run.id)
            .order_by(SessionEvent.seq.asc())
            .all()
        ]
        assert "run_created" in event_types
        assert "run_started" in event_types
        assert "run_waiting_input" in event_types

        db.refresh(session)
        graph_state = session.graph_state or {}
        assert graph_state.get("run_id") == run.id
        assert graph_state.get("run_status") == "waiting_input"


def test_interrupt_then_resume_preserves_run_id_and_thread(tmp_path, monkeypatch):
    monkeypatch.setenv("LANGGRAPH_CHECKPOINTER", "memory")
    refresh_settings()

    database = _make_database(tmp_path, "b3-resume.db")
    session_id = _seed_session(database)

    with get_db(database) as db:
        session = db.get(SessionModel, session_id)
        emitter = EventEmitter(session_id=session_id, event_store=EventStoreService(db))
        orchestrator = LangGraphOrchestrator(db, session, emitter)

        first = asyncio.run(_collect_responses(orchestrator, **_common_stream_kwargs()))
        assert first
        assert first[-1].action == "refine_waiting"

        run_service = RunService(db)
        waiting = run_service.get_latest_waiting_run(session_id)
        assert waiting is not None
        run_id = waiting.id
        checkpoint_thread = waiting.checkpoint_thread

        second = asyncio.run(
            _collect_responses(
                orchestrator,
                **_common_stream_kwargs(
                    message="继续优化",
                    resume={
                        "run_id": run_id,
                        "user_feedback": "improve spacing",
                    },
                ),
            )
        )
        assert second

        resumed = run_service.get_run(run_id)
        assert resumed.status == "completed"
        assert resumed.checkpoint_thread == checkpoint_thread

        run_events = [
            row.type
            for row in db.query(SessionEvent)
            .filter(SessionEvent.session_id == session_id, SessionEvent.run_id == run_id)
            .order_by(SessionEvent.seq.asc())
            .all()
        ]
        assert "run_waiting_input" in run_events
        assert "run_resumed" in run_events
        assert "run_completed" in run_events
        assert run_events.index("run_resumed") < run_events.index("run_completed")


def test_run_completed_event_contains_data_model_migration_summary(tmp_path, monkeypatch):
    monkeypatch.setenv("LANGGRAPH_CHECKPOINTER", "memory")
    refresh_settings()

    class _FakeStore:
        def __init__(self) -> None:
            self.enabled = True
            self.calls = 0

        async def create_schema(self, session_id: str) -> str:
            return f"app_{session_id}"

        async def create_tables(self, session_id: str, data_model) -> dict:
            self.calls += 1
            return {
                "schema": f"app_{session_id}",
                "entities_added": ["Trip"],
                "columns_added": {"Trip": ["title"]},
                "columns_deprecated": {},
            }

    async def _passthrough_refine_gate(state):
        if isinstance(state, dict):
            return dict(state)
        if hasattr(state, "__dict__"):
            return dict(state.__dict__)
        return {}

    fake_store = _FakeStore()
    monkeypatch.setattr("app.graph.nodes.generate.get_app_data_store", lambda: fake_store)
    monkeypatch.setattr(
        "app.graph.nodes.generate._resolve_data_model",
        lambda _state: {
            "entities": {
                "Trip": {
                    "primaryKey": "id",
                    "fields": [
                        {"name": "id", "type": "string", "required": True},
                        {"name": "title", "type": "string", "required": True},
                    ],
                }
            },
            "relations": [],
        },
    )
    monkeypatch.setattr("app.graph.graph.refine_gate_node", _passthrough_refine_gate)

    database = _make_database(tmp_path, "b3-migration-summary.db")
    session_id = _seed_session(database)

    with get_db(database) as db:
        session = db.get(SessionModel, session_id)
        emitter = EventEmitter(session_id=session_id, event_store=EventStoreService(db))
        orchestrator = LangGraphOrchestrator(db, session, emitter)

        responses = asyncio.run(
            _collect_responses(
                orchestrator,
                **_common_stream_kwargs(message="旅行行程规划，包含行程和景点 itinerary"),
            )
        )
        assert responses

        runs = RunService(db).list_runs(session_id)
        assert runs
        run_id = runs[0].id

        run_completed = (
            db.query(SessionEvent)
            .filter(
                SessionEvent.session_id == session_id,
                SessionEvent.run_id == run_id,
                SessionEvent.type == "run_completed",
            )
            .order_by(SessionEvent.seq.desc())
            .first()
        )

    assert run_completed is not None
    event_payload = run_completed.payload if isinstance(run_completed.payload, dict) else {}
    run_payload = event_payload.get("payload") if isinstance(event_payload.get("payload"), dict) else event_payload
    migration = run_payload.get("data_model_migration")
    assert isinstance(migration, dict)
    assert migration.get("version")
    summary = migration.get("summary")
    assert isinstance(summary, dict)
    assert summary.get("schema") == f"app_{session_id}"
    assert summary.get("entities_added") == ["Trip"]
    assert fake_store.calls >= 1


def test_cancelled_run_is_idempotent_in_orchestrator(tmp_path, monkeypatch):
    monkeypatch.setenv("LANGGRAPH_CHECKPOINTER", "memory")
    refresh_settings()

    database = _make_database(tmp_path, "b3-cancel.db")
    session_id = _seed_session(database)

    with get_db(database) as db:
        session = db.get(SessionModel, session_id)
        run_service = RunService(db)
        pre_run = run_service.create_run(
            session_id=session_id,
            message="cancel me",
            generate_now=True,
            target_pages=["index"],
            trigger_source="chat",
        )
        run_service.start_run(pre_run.id)
        run_service.cancel_run(pre_run.id)
        db.commit()

        emitter = EventEmitter(
            session_id=session_id,
            run_id=pre_run.id,
            event_store=EventStoreService(db),
        )
        orchestrator = LangGraphOrchestrator(db, session, emitter)

        responses = asyncio.run(
            _collect_responses(
                orchestrator,
                **_common_stream_kwargs(
                    message="resume cancelled",
                    resume={"run_id": pre_run.id, "user_feedback": "test"},
                ),
            )
        )
        assert responses
        assert responses[-1].action == "error"

        same_run = run_service.get_run(pre_run.id)
        assert same_run.status == "cancelled"


def test_concurrent_runs_use_isolated_checkpoints(tmp_path, monkeypatch):
    monkeypatch.setenv("LANGGRAPH_CHECKPOINTER", "memory")
    refresh_settings()

    database = _make_database(tmp_path, "b3-concurrency.db")
    session_id = _seed_session(database)

    def _run_once(message: str):
        with get_db(database) as db:
            session = db.get(SessionModel, session_id)
            emitter = EventEmitter(session_id=session_id, event_store=EventStoreService(db))
            orchestrator = LangGraphOrchestrator(db, session, emitter)
            return asyncio.run(_collect_responses(orchestrator, **_common_stream_kwargs(message=message)))

    first = _run_once("first")
    second = _run_once("second")
    assert first and second

    with get_db(database) as db:
        run_service = RunService(db)
        runs = run_service.list_runs(session_id)
        run_ids = {run.id for run in runs}
        threads = {run.checkpoint_thread for run in runs}

    assert len(run_ids) >= 2
    assert len(threads) >= 2
    for run_id in run_ids:
        assert f"{session_id}:{run_id}" in threads
