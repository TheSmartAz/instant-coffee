import uuid

import pytest
from pydantic import ValidationError

from app.db.database import Database
from app.db.migrations import init_db
from app.db.models import Session as SessionModel
from app.db.models import SessionRun
from app.db.utils import get_db, transaction_scope
from app.schemas.run import RunCreate, RunResponse, RunResumeRequest, RunStatus


def test_session_run_model_crud(tmp_path) -> None:
    db_path = tmp_path / "run-model.db"
    database = Database(f"sqlite:///{db_path}")
    init_db(database)

    session_id = uuid.uuid4().hex
    with transaction_scope(database) as session:
        session.add(SessionModel(id=session_id, title="Run Model Test"))

    with get_db(database) as session:
        run = SessionRun(
            session_id=session_id,
            trigger_source="chat",
            input_message="build me a landing page",
        )
        session.add(run)
        session.commit()
        run_id = run.id

    with get_db(database) as session:
        stored = session.get(SessionRun, run_id)
        assert stored is not None
        assert stored.session_id == session_id
        assert stored.status == "queued"
        assert stored.created_at is not None
        assert stored.updated_at is not None

        stored.status = "running"
        stored.metrics = {"tokens": 123}
        stored.checkpoint_thread = f"{session_id}:{run_id}"
        session.commit()

    with get_db(database) as session:
        stored = session.get(SessionRun, run_id)
        assert stored is not None
        assert stored.status == "running"
        assert stored.metrics == {"tokens": 123}
        assert stored.checkpoint_thread == f"{session_id}:{run_id}"


def test_session_run_model_validates_status_and_trigger_source() -> None:
    run = SessionRun(session_id="s1", trigger_source="chat", status="queued")
    assert run.trigger_source == "chat"
    assert run.status == "queued"

    with pytest.raises(ValueError):
        run.trigger_source = "manual"

    with pytest.raises(ValueError):
        run.status = "paused"


def test_run_status_enum_validation() -> None:
    assert RunStatus("queued") is RunStatus.QUEUED
    assert RunStatus("waiting_input") is RunStatus.WAITING_INPUT

    with pytest.raises(ValueError):
        RunStatus("paused")


def test_run_schemas_serialize_deserialize() -> None:
    create_payload = {
        "session_id": "session-1",
        "message": "Generate now",
        "generate_now": True,
        "target_pages": ["index", "pricing"],
        "style_reference": {
            "mode": "style_only",
            "images": [],
            "scope_pages": ["index"],
        },
    }
    create_data = RunCreate.model_validate(create_payload)
    assert create_data.session_id == "session-1"
    assert create_data.generate_now is True
    assert create_data.target_pages == ["index", "pricing"]

    response = RunResponse(
        run_id="run-1",
        session_id="session-1",
        status=RunStatus.RUNNING,
        checkpoint_thread="session-1:run-1",
        waiting_reason=None,
    )
    response_payload = response.model_dump(mode="json")
    assert response_payload["run_id"] == "run-1"
    assert response_payload["status"] == "running"
    assert response_payload["checkpoint_thread"] == "session-1:run-1"

    resume_old = RunResumeRequest.model_validate({"resume": {"approval": True}})
    assert resume_old.resume_payload == {"approval": True}

    resume_new = RunResumeRequest.model_validate({"resume_payload": {"foo": "bar"}})
    assert resume_new.resume_payload == {"foo": "bar"}

    with pytest.raises(ValidationError):
        RunCreate.model_validate({
            "session_id": "session-1",
            "message": "x",
            "unexpected": True,
        })
