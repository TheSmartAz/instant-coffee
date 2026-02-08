import uuid

import pytest

from app.db.database import Database
from app.db.migrations import init_db
from app.db.models import Session as SessionModel
from app.db.models import SessionEvent
from app.db.models import SessionEventSource
from app.db.utils import get_db, transaction_scope
from app.events.emitter import EventEmitter
from app.events.models import BaseEvent
from app.events.types import EventType, RUN_SCOPED_EVENT_TYPES
from app.services.event_store import EventStoreService


def _make_database(tmp_path) -> Database:
    db_path = tmp_path / "event-layer-v08.db"
    database = Database(f"sqlite:///{db_path}")
    init_db(database)
    return database


def test_v08_new_event_types_registered() -> None:
    expected = {
        "run_created",
        "run_started",
        "run_waiting_input",
        "run_resumed",
        "run_completed",
        "run_failed",
        "run_cancelled",
        "verify_start",
        "verify_pass",
        "verify_fail",
        "tool_policy_blocked",
        "tool_policy_warn",
    }

    actual = {item.value for item in EventType}
    for event_name in expected:
        assert event_name in actual
        assert event_name in RUN_SCOPED_EVENT_TYPES


def test_run_scoped_event_without_run_id_rejected(tmp_path) -> None:
    database = _make_database(tmp_path)
    session_id = uuid.uuid4().hex

    with transaction_scope(database) as session:
        session.add(SessionModel(id=session_id, title="Run Scoped Rejected"))

    with get_db(database) as session:
        store = EventStoreService(session)
        event = BaseEvent(
            type=EventType.RUN_STARTED,
            session_id=session_id,
            payload={"phase": "langgraph"},
        )
        with pytest.raises(ValueError):
            store.record_event(event)


def test_legacy_event_without_run_id_still_valid() -> None:
    event = BaseEvent(
        type=EventType.AGENT_PROGRESS,
        session_id="s1",
        payload={"message": "ok"},
    )
    assert event.run_id is None
    assert event.payload == {"message": "ok"}


def test_payload_must_be_object() -> None:
    with pytest.raises(ValueError):
        BaseEvent(
            type=EventType.AGENT_PROGRESS,
            session_id="s1",
            payload="oops",  # type: ignore[arg-type]
        )


def test_event_emitter_passes_run_id_and_event_id(tmp_path) -> None:
    database = _make_database(tmp_path)
    session_id = uuid.uuid4().hex

    with transaction_scope(database) as session:
        session.add(SessionModel(id=session_id, title="Emitter Run"))

    with get_db(database) as session:
        store = EventStoreService(session)
        emitter = EventEmitter(
            session_id=session_id,
            run_id="run-123",
            event_store=store,
        )
        event = BaseEvent(type=EventType.RUN_STARTED, payload={"phase": "langgraph"})
        emitter.emit(event)
        session.commit()

    with get_db(database) as session:
        rows = session.query(SessionEvent).all()
        assert rows

    with get_db(database) as session:
        store = EventStoreService(session)
        rows = store.get_events_by_run(session_id, "run-123")
        assert len(rows) == 1
        row = rows[0]
        assert row.run_id == "run-123"
        assert row.event_id is not None
        assert row.payload.get("run_id") == "run-123"
        assert row.payload.get("event_id") == row.event_id


def test_run_dimension_query_and_since_seq_filter(tmp_path) -> None:
    database = _make_database(tmp_path)
    session_id = uuid.uuid4().hex

    with transaction_scope(database) as session:
        session.add(SessionModel(id=session_id, title="Run Query"))

    with get_db(database) as session:
        store = EventStoreService(session)
        store.store_event(
            session_id,
            "run_started",
            {"run_id": "run-a", "event_id": "e-1", "payload": {"step": 1}},
            SessionEventSource.SESSION.value,
        )
        store.store_event(
            session_id,
            "run_started",
            {"run_id": "run-b", "event_id": "e-2", "payload": {"step": 2}},
            SessionEventSource.SESSION.value,
        )
        store.store_event(
            session_id,
            "run_completed",
            {"run_id": "run-a", "event_id": "e-3", "payload": {"step": 3}},
            SessionEventSource.SESSION.value,
        )
        session.commit()

    with get_db(database) as session:
        store = EventStoreService(session)
        run_a_events = store.get_events_by_run(session_id, "run-a")
        assert [event.type for event in run_a_events] == ["run_started", "run_completed"]
        assert [event.seq for event in run_a_events] == sorted(event.seq for event in run_a_events)

        filtered = store.get_events_by_run(session_id, "run-a", since_seq=run_a_events[0].seq)
        assert [event.type for event in filtered] == ["run_completed"]

        all_events = store.get_events(session_id)
        assert len(all_events) == 3


def test_run_scoped_store_event_without_run_id_rejected(tmp_path) -> None:
    database = _make_database(tmp_path)
    session_id = uuid.uuid4().hex

    with transaction_scope(database) as session:
        session.add(SessionModel(id=session_id, title="Run Missing ID"))

    with get_db(database) as session:
        store = EventStoreService(session)
        with pytest.raises(ValueError):
            store.store_event(
                session_id,
                EventType.RUN_STARTED.value,
                {"phase": "langgraph"},
                SessionEventSource.SESSION.value,
            )
