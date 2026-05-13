import asyncio
from contextlib import suppress
import json
import uuid

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.responses import StreamingResponse

from app.api import chat as chat_api
from app.config import refresh_settings
from app.db.database import Database
from app.db.database import reset_database
from app.db.migrations import init_db
from app.db.models import Message, Session as SessionModel
from app.db.models import SessionEvent, SessionRun
from app.db.utils import get_db, transaction_scope
from app.engine.orchestrator import EngineOrchestrator
from app.engine.run_coordinator import RunCoordinatorResult
from app.events.emitter import EventEmitter
from app.events.models import workflow_event
from app.events.types import EventType
from app.schemas.orchestrator_response import OrchestratorResponse
from app.schemas.session_metadata import BuildInfo, BuildStatus
from app.services.event_store import EventStoreService
from app.services.run import RunService


def _create_database(tmp_path, name: str) -> Database:
    db_path = tmp_path / name
    database = Database(f"sqlite:///{db_path}")
    init_db(database)
    return database


def _create_app(tmp_path, monkeypatch):
    db_path = tmp_path / "chat-run-adapter-api.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "output"))
    monkeypatch.setenv("DEFAULT_BASE_URL", "http://localhost")
    monkeypatch.setenv("DEFAULT_KEY", "test-key")
    monkeypatch.setenv("CHAT_USE_RUN_ADAPTER", "true")
    refresh_settings()
    reset_database()
    init_db()
    from app.main import create_app

    return create_app()


def _seed_running_run(database: Database | None = None) -> tuple[str, str]:
    session_id = uuid.uuid4().hex
    with transaction_scope(database) as session:
        session.add(SessionModel(id=session_id, title="Chat Adapter Test"))

    with get_db(database) as session:
        run_service = RunService(session)
        run = run_service.create_run(
            session_id=session_id,
            message="Build a mobile coffee shop",
            generate_now=True,
        )
        run_service.start_run(run.id)
        run_id = run.id
        session.commit()
    return session_id, run_id


class _FakeOrchestrator:
    def __init__(self, db, session, emitter: EventEmitter) -> None:
        self.db = db
        self.session = session
        self.event_emitter = emitter
        self.messages: list[str] = []

    async def stream_responses(self, **kwargs):
        self.messages.append(kwargs["user_message"])
        message = "fixed" if "previous build review failed" in kwargs["user_message"].lower() else "implemented"
        yield OrchestratorResponse(
            session_id=self.session.id,
            phase="complete",
            message=message,
            is_complete=True,
            action="pages_generated",
            affected_pages=["index"],
            active_page_slug="index",
        )


class _SequencedOrchestrator:
    responses: list[dict] = []
    calls: list[dict] = []

    def __init__(self, db, session, emitter: EventEmitter) -> None:
        self.db = db
        self.session = session
        self.event_emitter = emitter

    async def stream_responses(self, **kwargs):
        self.__class__.calls.append(
            {
                "user_message": kwargs["user_message"],
                "resume": kwargs.get("resume"),
            }
        )
        response = self.__class__.responses.pop(0) if self.__class__.responses else {}
        yield OrchestratorResponse(
            session_id=self.session.id,
            phase=str(response.get("phase") or "complete"),
            message=str(response.get("message") or "implemented"),
            is_complete=bool(response.get("is_complete", True)),
            action=response.get("action") or "pages_generated",
            affected_pages=response.get("affected_pages") or ["index"],
            active_page_slug=response.get("active_page_slug") or "index",
        )


class _FakeBuildRunner:
    calls = 0

    def __init__(self, _db, *, event_emitter=None, cancel_event=None) -> None:
        self.event_emitter = event_emitter

    async def build_session(self, _session_id: str) -> BuildInfo:
        self.__class__.calls += 1
        if self.event_emitter is not None:
            self.event_emitter.emit(workflow_event(EventType.BUILD_START))
            self.event_emitter.emit(
                workflow_event(
                    EventType.BUILD_COMPLETE,
                    {
                        "status": "success",
                        "pages": ["index.html"],
                        "dist_path": "/tmp/instant-coffee/dist",
                    },
                )
            )
        return BuildInfo(
            status=BuildStatus.SUCCESS,
            pages=["index.html"],
            dist_path="/tmp/instant-coffee/dist",
        )


class _FakeReviewService:
    verdicts: list[dict] = []

    def __init__(self, _db) -> None:
        pass

    def review_session(self, _session_id: str) -> dict:
        if self.__class__.verdicts:
            return self.__class__.verdicts.pop(0)
        return {"passed": True, "summary": {"error_count": 0}}


class _TerminalPendingEmitter:
    def __init__(self) -> None:
        self._sent_terminal = False

    def get_events(self) -> list:
        return []

    def events_since(self, index: int) -> tuple[list, int]:
        if index == 0 and not self._sent_terminal:
            self._sent_terminal = True
            return [workflow_event(EventType.DONE, {"status": "done"})], 1
        return [], index


class _PendingQuestionOrchestrator:
    has_pending_question = True

    def __init__(self) -> None:
        self.event_emitter = _TerminalPendingEmitter()
        self.answers: list[dict] = []

    def resolve_answer(self, answer_data: dict) -> bool:
        self.answers.append(answer_data)
        return True


def _sse_json_payloads(response_text: str) -> list[dict]:
    payloads = []
    for line in response_text.splitlines():
        if not line.startswith("data: "):
            continue
        raw = line.removeprefix("data: ")
        if raw == "[DONE]":
            continue
        payloads.append(json.loads(raw))
    return payloads


def _filtered_events(event_types: list[str], allowed: set[str]) -> list[str]:
    return [event_type for event_type in event_types if event_type in allowed]


class _ChatRequestStub:
    def __init__(self, accept: str = "application/json") -> None:
        self.headers = {"accept": accept}
        self.base_url = "http://testserver/"

    async def is_disconnected(self) -> bool:
        return False


async def _read_streaming_response(response: StreamingResponse) -> str:
    chunks: list[str] = []
    async for chunk in response.body_iterator:
        if isinstance(chunk, bytes):
            chunks.append(chunk.decode())
        else:
            chunks.append(str(chunk))
    return "".join(chunks)


@pytest.mark.parametrize(
    ("coordinator_status", "expected_action"),
    [
        ("failed", "error"),
        ("cancelled", "cancelled"),
    ],
)
def test_chat_endpoint_run_adapter_surfaces_terminal_coordinator_status_without_stale_success(
    tmp_path,
    monkeypatch,
    coordinator_status: str,
    expected_action: str,
) -> None:
    class _TerminalCoordinator:
        def __init__(self, *, phases, **_kwargs) -> None:
            self.phases = phases

        async def run(self, run_id: str) -> RunCoordinatorResult:
            stale_final = await self.phases.implement({})
            assert stale_final.message == "stale success"
            return RunCoordinatorResult(
                status=coordinator_status,
                run_id=run_id,
                current_phase="review",
                final_response=None,
            )

    monkeypatch.setattr(chat_api, "RunCoordinator", _TerminalCoordinator)
    monkeypatch.setattr(chat_api, "BuildRunner", _FakeBuildRunner)
    monkeypatch.setattr(chat_api, "ReviewService", _FakeReviewService)
    monkeypatch.setattr(
        chat_api,
        "_create_orchestrator",
        lambda db, session, emitter: _SequencedOrchestrator(db, session, emitter),
    )
    _SequencedOrchestrator.calls = []
    _SequencedOrchestrator.responses = [
        {
            "phase": "complete",
            "message": "stale success",
            "is_complete": True,
            "action": "pages_generated",
            "affected_pages": ["index"],
            "active_page_slug": "index",
        }
    ]

    _create_app(tmp_path, monkeypatch)
    with get_db() as session:
        session_id = uuid.uuid4().hex
        session.add(SessionModel(id=session_id, title="Terminal coordinator status"))
        session.commit()

    with get_db() as db:
        response = asyncio.run(
            chat_api.chat(
                chat_api.ChatRequest(
                    session_id=session_id,
                    message="Build a mobile coffee shop",
                    generate_now=True,
                    interview=False,
                ),
                _ChatRequestStub(),
                db,
            )
        )

    assert response.status_code == 200
    body = response.body if hasattr(response, "body") else response.json()
    if isinstance(body, (bytes, bytearray)):
        body = json.loads(body.decode())
    assert body["action"] == expected_action
    assert coordinator_status in body["message"].lower()
    assert body["message"] != "stale success"
    assert body["affected_pages"] == []
    assert body["active_page_slug"] is None

    with get_db() as session:
        runs = session.query(SessionRun).all()
        assert len(runs) == 1
        assert runs[0].status == coordinator_status


def test_chat_endpoint_run_adapter_synthesizes_completed_response_from_coordinator_artifact(
    tmp_path,
    monkeypatch,
) -> None:
    class _CompletedCheckpointCoordinator:
        def __init__(self, **_kwargs) -> None:
            pass

        async def run(self, run_id: str) -> RunCoordinatorResult:
            return RunCoordinatorResult(
                status="completed",
                run_id=run_id,
                current_phase="done",
                implement={
                    "phase": "complete",
                    "message": "Recovered from checkpoint",
                    "action": "pages_generated",
                    "affected_pages": ["index"],
                    "active_page_slug": "index",
                },
            )

    monkeypatch.setattr(chat_api, "RunCoordinator", _CompletedCheckpointCoordinator)
    monkeypatch.setattr(
        chat_api,
        "_create_orchestrator",
        lambda db, session, emitter: _FakeOrchestrator(db, session, emitter),
    )

    app = _create_app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        response = client.post(
            "/api/chat",
            json={
                "message": "Continue the checkpointed run",
                "generate_now": True,
                "interview": False,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "Recovered from checkpoint"
    assert body["action"] == "pages_generated"
    assert body["affected_pages"] == ["index"]
    assert body["active_page_slug"] == "index"

    with get_db() as session:
        runs = session.query(SessionRun).all()
        assert len(runs) == 1
        assert runs[0].status == "completed"


def test_chat_sse_pending_question_routes_answer_before_creating_bound_run(
    tmp_path,
    monkeypatch,
) -> None:
    _create_app(tmp_path, monkeypatch)
    with get_db() as session:
        session_id = uuid.uuid4().hex
        session.add(SessionModel(id=session_id, title="Pending question"))
        session.commit()

    pending_orch = _PendingQuestionOrchestrator()

    from app.engine.registry import engine_registry

    engine_registry.register(session_id, pending_orch)
    monkeypatch.setattr(
        chat_api,
        "_create_orchestrator",
        lambda *_args, **_kwargs: pytest.fail("should not spawn a new orchestrator"),
    )
    try:
        with get_db() as db:
            response = asyncio.run(
                chat_api.chat(
                    chat_api.ChatRequest(
                        session_id=session_id,
                        message="Use the editorial option",
                        generate_now=True,
                        interview=False,
                    ),
                    _ChatRequestStub(accept="text/event-stream"),
                    db,
                )
            )
            assert isinstance(response, StreamingResponse)
            response_text = asyncio.run(_read_streaming_response(response))
    finally:
        engine_registry.unregister(session_id)

    assert pending_orch.answers == [{"text": "Use the editorial option"}]
    assert _sse_json_payloads(response_text)[-1]["type"] == EventType.DONE.value

    with get_db() as session:
        runs = session.query(SessionRun).filter(SessionRun.session_id == session_id).all()
        assert runs == []


def test_chat_json_pending_question_rejects_without_creating_bound_run(
    tmp_path,
    monkeypatch,
) -> None:
    _create_app(tmp_path, monkeypatch)
    with get_db() as session:
        session_id = uuid.uuid4().hex
        session.add(SessionModel(id=session_id, title="Pending question JSON"))
        session.commit()

    pending_orch = _PendingQuestionOrchestrator()

    from app.engine.registry import engine_registry

    engine_registry.register(session_id, pending_orch)
    monkeypatch.setattr(
        chat_api,
        "_create_orchestrator",
        lambda *_args, **_kwargs: pytest.fail("should not spawn a new orchestrator"),
    )
    try:
        with get_db() as db:
            with pytest.raises(HTTPException) as exc_info:
                asyncio.run(
                    chat_api.chat(
                        chat_api.ChatRequest(
                            session_id=session_id,
                            message="Use the editorial option",
                            generate_now=True,
                            interview=False,
                        ),
                        _ChatRequestStub(),
                        db,
                    )
                )
    finally:
        engine_registry.unregister(session_id)

    assert exc_info.value.status_code == 409
    assert "stream endpoint" in str(exc_info.value.detail)
    assert pending_orch.answers == []

    with get_db() as session:
        runs = session.query(SessionRun).filter(SessionRun.session_id == session_id).all()
        messages = session.query(Message).filter(Message.session_id == session_id).all()
        assert runs == []
        assert messages == []


def test_engine_user_io_persists_run_waiting_and_resumed_states(tmp_path) -> None:
    database = _create_database(tmp_path, "engine-user-io-waiting.db")
    session_id, run_id = _seed_running_run(database)

    async def exercise_user_io() -> None:
        with get_db(database) as session:
            session_model = session.get(SessionModel, session_id)
            assert session_model is not None
            emitter = EventEmitter(
                session_id=session_id,
                run_id=run_id,
                event_store=EventStoreService(session),
            )
            orchestrator = EngineOrchestrator(session, session_model, emitter)
            question_task = asyncio.create_task(
                orchestrator._web_user_io.present_questions(
                    [{"question": "Which visual direction should I use?"}]
                )
            )
            await asyncio.sleep(0)

            session.expire_all()
            waiting_run = session.get(SessionRun, run_id)
            assert waiting_run is not None
            assert waiting_run.status == "waiting_input"
            assert waiting_run.latest_error["batch_id"]
            assert waiting_run.latest_error["waiting_reason"] == "Which visual direction should I use?"
            assert RunService.get_phase_metadata(waiting_run)["status"] == "waiting_input"
            assert orchestrator.has_pending_question

            assert orchestrator.resolve_answer({"answers": [{"text": "Use editorial minimalism"}]})
            await asyncio.wait_for(question_task, timeout=1)

            session.expire_all()
            resumed_run = session.get(SessionRun, run_id)
            assert resumed_run is not None
            assert resumed_run.status == "running"
            assert resumed_run.resume_payload["source"] == "ask_user"
            assert resumed_run.resume_payload["batch_id"] == waiting_run.latest_error["batch_id"]
            assert resumed_run.resume_payload["answers"] == {
                "answers": [{"text": "Use editorial minimalism"}]
            }
            assert RunService.get_phase_metadata(resumed_run)["status"] == "running"

            event_types = [
                row.type
                for row in session.query(SessionEvent)
                .filter(
                    SessionEvent.run_id == run_id,
                    SessionEvent.type.in_(["run_waiting_input", "run_resumed"]),
                )
                .order_by(SessionEvent.seq.asc())
                .all()
            ]
            assert event_types == ["run_waiting_input", "run_resumed"]

    asyncio.run(exercise_user_io())


def test_chat_stream_recovers_ask_user_waiting_run_after_registry_loss(tmp_path, monkeypatch) -> None:
    app = _create_app(tmp_path, monkeypatch)
    _FakeBuildRunner.calls = 0
    _FakeReviewService.verdicts = [{"passed": True, "issues": [], "summary": {"error_count": 0}}]
    _SequencedOrchestrator.calls = []
    _SequencedOrchestrator.responses = [
        {
            "phase": "complete",
            "message": "implemented after restart",
            "is_complete": True,
            "action": "pages_generated",
        },
    ]
    monkeypatch.setattr(chat_api, "BuildRunner", _FakeBuildRunner)
    monkeypatch.setattr(chat_api, "ReviewService", _FakeReviewService)
    monkeypatch.setattr(
        chat_api,
        "_create_orchestrator",
        lambda db, session, emitter: _SequencedOrchestrator(db, session, emitter),
    )

    with get_db() as session:
        session_id = uuid.uuid4().hex
        session.add(SessionModel(id=session_id, title="Ask user restart recovery"))
        session.commit()
        run_service = RunService(session)
        run = run_service.create_run(
            session_id=session_id,
            message="Build a mobile coffee shop",
            generate_now=True,
        )
        run_service.start_run(run.id)
        run_id = run.id
        session.commit()

    async def persist_waiting_then_drop_memory() -> None:
        with get_db() as session:
            session_model = session.get(SessionModel, session_id)
            assert session_model is not None
            emitter = EventEmitter(
                session_id=session_id,
                run_id=run_id,
                event_store=EventStoreService(session),
            )
            orchestrator = EngineOrchestrator(session, session_model, emitter)
            question_task = asyncio.create_task(
                orchestrator._web_user_io.present_questions(
                    [{"question": "Which visual direction should I use?"}]
                )
            )
            await asyncio.sleep(0)
            waiting_run = session.get(SessionRun, run_id)
            assert waiting_run is not None
            assert waiting_run.status == "waiting_input"
            state = waiting_run.metrics["coordinator"]
            assert state["current_phase"] == "implement"
            assert state["phase_history"][-1]["status"] == "waiting_input"
            question_task.cancel()
            with suppress(asyncio.CancelledError):
                await question_task

    asyncio.run(persist_waiting_then_drop_memory())

    with TestClient(app) as client:
        with client.stream(
            "POST",
            "/api/chat/stream",
            json={
                "session_id": session_id,
                "message": "Use a crisp editorial style",
                "generate_now": True,
                "interview": False,
            },
        ) as response:
            assert response.status_code == 200
            response_text = "\n".join(
                line.decode() if isinstance(line, bytes) else line
                for line in response.iter_lines()
            )

    payloads = _sse_json_payloads(response_text)
    lifecycle_events = _filtered_events(
        [payload["type"] for payload in payloads if "type" in payload],
        {"run_resumed", "build_start", "build_complete", "verify_start", "verify_pass", "run_completed"},
    )
    assert lifecycle_events == [
        "run_resumed",
        "build_start",
        "build_complete",
        "verify_start",
        "verify_pass",
        "run_completed",
    ]
    run_scoped_payloads = [
        payload
        for payload in payloads
        if payload.get("type") in {
            "run_resumed",
            "build_start",
            "build_complete",
            "verify_start",
            "verify_pass",
            "run_completed",
        }
    ]
    assert {payload.get("run_id") for payload in run_scoped_payloads} == {run_id}
    assert _SequencedOrchestrator.calls[0]["resume"]["run_id"] == run_id
    assert _SequencedOrchestrator.calls[0]["resume"]["auto_resumed"] is True
    assert _SequencedOrchestrator.calls[0]["resume"]["user_feedback"] == "Use a crisp editorial style"

    with get_db() as session:
        run = session.get(SessionRun, run_id)
        assert run is not None
        assert run.status == "completed"
        state = run.metrics["coordinator"]
        assert [item["status"] for item in state["phase_history"][:2]] == [
            "waiting_input",
            "completed",
        ]


def test_chat_rejected_active_run_does_not_persist_user_message(tmp_path, monkeypatch) -> None:
    app = _create_app(tmp_path, monkeypatch)
    with get_db() as session:
        session_id = uuid.uuid4().hex
        session.add(SessionModel(id=session_id, title="Active run conflict"))
        session.commit()
        run_service = RunService(session)
        active = run_service.create_run(
            session_id=session_id,
            message="first",
            generate_now=True,
        )
        run_service.start_run(active.id)
        session.commit()

    with TestClient(app) as client:
        response = client.post(
            "/api/chat",
            json={
                "session_id": session_id,
                "message": "second",
                "generate_now": True,
                "interview": False,
            },
        )

    assert response.status_code == 409
    with get_db() as session:
        messages = session.query(Message).filter(Message.session_id == session_id).all()
        runs = session.query(SessionRun).filter(SessionRun.session_id == session_id).all()
        assert messages == []
        assert len(runs) == 1


def test_chat_run_adapter_executes_build_review_fix_and_persists_run_state(tmp_path, monkeypatch) -> None:
    database = _create_database(tmp_path, "chat-run-adapter.db")
    session_id, run_id = _seed_running_run(database)

    _FakeBuildRunner.calls = 0
    _FakeReviewService.verdicts = [
        {
            "passed": False,
            "issues": [{"code": "page_html_missing", "severity": "error"}],
            "summary": {"error_count": 1},
        },
        {"passed": True, "issues": [], "summary": {"error_count": 0}},
    ]
    monkeypatch.setattr(chat_api, "BuildRunner", _FakeBuildRunner)
    monkeypatch.setattr(chat_api, "ReviewService", _FakeReviewService)

    stream_db = database.session()
    stream_session = stream_db.get(SessionModel, session_id)
    assert stream_session is not None
    emitter = EventEmitter(
        session_id=session_id,
        run_id=run_id,
        event_store=EventStoreService(stream_db),
    )
    orchestrator = _FakeOrchestrator(stream_db, stream_session, emitter)
    run_context = chat_api._ChatRunContext(
        run_id=run_id,
        resume_payload=None,
        checkpoint_thread=f"{session_id}:{run_id}",
        adapter_active=True,
        transition="created",
    )

    asyncio.run(
        chat_api._run_orchestrator_stream(
            orchestrator=orchestrator,
            queue=asyncio.Queue(),
            done_event=asyncio.Event(),
            user_message="Build a mobile coffee shop",
            output_dir="unused",
            history=[],
            trigger_interview=False,
            generate_now=True,
            run_context=run_context,
            thread_id=None,
        )
    )

    assert len(orchestrator.messages) == 2
    assert _FakeBuildRunner.calls == 2

    with get_db(database) as session:
        run = session.get(SessionRun, run_id)
        assert run is not None
        assert run.status == "completed"
        state = run.metrics["coordinator"]
        assert state["current_phase"] == "done"
        assert state["fix_attempts"] == 1
        assert [item["phase"] for item in state["phase_history"]] == [
            "implement",
            "build",
            "review",
            "fix",
            "review",
        ]
        event_types = [
            row.type
            for row in session.query(SessionEvent)
            .filter(SessionEvent.run_id == run_id)
            .order_by(SessionEvent.seq.asc())
            .all()
        ]
        build_verify_events = _filtered_events(
            event_types,
            {"build_start", "build_complete", "verify_start", "verify_fail", "verify_pass"},
        )
        assert build_verify_events == [
            "build_start",
            "build_complete",
            "verify_start",
            "verify_fail",
            "build_start",
            "build_complete",
            "verify_start",
            "verify_pass",
        ]
        verify_events = _filtered_events(event_types, {"verify_start", "verify_fail", "verify_pass"})
        assert verify_events == ["verify_start", "verify_fail", "verify_start", "verify_pass"]
        assert "verify_fail" in event_types
        assert "verify_pass" in event_types
        assert event_types.count("run_completed") == 1


def test_chat_endpoint_run_adapter_smoke_executes_fix_loop(tmp_path, monkeypatch) -> None:
    app = _create_app(tmp_path, monkeypatch)
    _FakeBuildRunner.calls = 0
    _FakeReviewService.verdicts = [
        {
            "passed": False,
            "issues": [{"code": "page_html_missing", "severity": "error"}],
            "summary": {"error_count": 1},
        },
        {"passed": True, "issues": [], "summary": {"error_count": 0}},
    ]
    monkeypatch.setattr(chat_api, "BuildRunner", _FakeBuildRunner)
    monkeypatch.setattr(chat_api, "ReviewService", _FakeReviewService)
    monkeypatch.setattr(
        chat_api,
        "_create_orchestrator",
        lambda db, session, emitter: _FakeOrchestrator(db, session, emitter),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/chat",
            json={
                "message": "Build a mobile coffee shop",
                "generate_now": True,
                "interview": False,
            },
        )
        assert response.status_code == 200

        with get_db() as session:
            runs = session.query(SessionRun).all()
            assert len(runs) == 1
            run_id = runs[0].id

        run_detail = client.get(f"/api/runs/{run_id}")

    body = response.json()
    assert body["message"] == "fixed"
    assert body["action"] == "pages_generated"
    assert _FakeBuildRunner.calls == 2
    assert run_detail.status_code == 200
    detail = run_detail.json()
    assert detail["current_phase"] == "done"
    assert detail["fix_attempts"] == 1
    assert detail["review_summary"]["error_count"] == 0

    with get_db() as session:
        runs = session.query(SessionRun).all()
        assert len(runs) == 1
        run = runs[0]
        assert run.status == "completed"
        state = run.metrics["coordinator"]
        assert [item["phase"] for item in state["phase_history"]] == [
            "implement",
            "build",
            "review",
            "fix",
            "review",
        ]


def test_chat_stream_endpoint_run_adapter_emits_run_lifecycle(tmp_path, monkeypatch) -> None:
    app = _create_app(tmp_path, monkeypatch)
    _FakeBuildRunner.calls = 0
    _FakeReviewService.verdicts = [
        {
            "passed": False,
            "issues": [{"code": "page_html_missing", "severity": "error"}],
            "summary": {"error_count": 1},
        },
        {"passed": True, "issues": [], "summary": {"error_count": 0}},
    ]
    monkeypatch.setattr(chat_api, "BuildRunner", _FakeBuildRunner)
    monkeypatch.setattr(chat_api, "ReviewService", _FakeReviewService)
    monkeypatch.setattr(
        chat_api,
        "_create_orchestrator",
        lambda db, session, emitter: _FakeOrchestrator(db, session, emitter),
    )

    with TestClient(app) as client:
        with client.stream(
            "POST",
            "/api/chat/stream",
            json={
                "message": "Build a mobile coffee shop",
                "generate_now": True,
                "interview": False,
            },
        ) as response:
            assert response.status_code == 200
            response_text = "\n".join(
                line.decode() if isinstance(line, bytes) else line
                for line in response.iter_lines()
            )

    payloads = _sse_json_payloads(response_text)
    event_types = [payload["type"] for payload in payloads if "type" in payload]
    final_payloads = [payload for payload in payloads if payload.get("message") == "fixed"]
    assert "run_created" in event_types
    assert "run_started" in event_types
    build_verify_events = _filtered_events(
        event_types,
        {"build_start", "build_complete", "verify_start", "verify_fail", "verify_pass"},
    )
    assert build_verify_events == [
        "build_start",
        "build_complete",
        "verify_start",
        "verify_fail",
        "build_start",
        "build_complete",
        "verify_start",
        "verify_pass",
    ]
    verify_events = _filtered_events(event_types, {"verify_start", "verify_fail", "verify_pass"})
    assert verify_events == ["verify_start", "verify_fail", "verify_start", "verify_pass"]
    assert "verify_fail" in event_types
    assert "verify_pass" in event_types
    assert "run_completed" in event_types
    assert final_payloads
    assert final_payloads[-1]["action"] == "pages_generated"
    assert final_payloads[-1]["thread_id"]
    assert _FakeBuildRunner.calls == 2

    with get_db() as session:
        runs = session.query(SessionRun).all()
        assert len(runs) == 1
        assert runs[0].status == "completed"
        state = runs[0].metrics["coordinator"]
        assert [item["phase"] for item in state["phase_history"]] == [
            "implement",
            "build",
            "review",
            "fix",
            "review",
        ]


def test_chat_endpoint_run_adapter_auto_resumes_waiting_run(tmp_path, monkeypatch) -> None:
    app = _create_app(tmp_path, monkeypatch)
    _FakeBuildRunner.calls = 0
    _FakeReviewService.verdicts = [{"passed": True, "issues": [], "summary": {"error_count": 0}}]
    _SequencedOrchestrator.calls = []
    _SequencedOrchestrator.responses = [
        {
            "phase": "interview",
            "message": "Which visual direction should I use?",
            "is_complete": False,
            "action": "refine_waiting",
            "affected_pages": [],
            "active_page_slug": None,
        },
        {
            "phase": "complete",
            "message": "implemented",
            "is_complete": True,
            "action": "pages_generated",
        },
    ]
    monkeypatch.setattr(chat_api, "BuildRunner", _FakeBuildRunner)
    monkeypatch.setattr(chat_api, "ReviewService", _FakeReviewService)
    monkeypatch.setattr(
        chat_api,
        "_create_orchestrator",
        lambda db, session, emitter: _SequencedOrchestrator(db, session, emitter),
    )

    with TestClient(app) as client:
        first = client.post(
            "/api/chat",
            json={
                "message": "Build a mobile coffee shop",
                "generate_now": True,
                "interview": False,
            },
        )
        assert first.status_code == 200
        first_body = first.json()

        with get_db() as session:
            runs = session.query(SessionRun).all()
            assert len(runs) == 1
            waiting_run = runs[0]
            waiting_run_id = waiting_run.id
            assert waiting_run.status == "waiting_input"
            waiting_state = waiting_run.metrics["coordinator"]
            assert waiting_state["phase_history"][0]["phase"] == "implement"
            assert waiting_state["phase_history"][0]["status"] == "waiting_input"

        second = client.post(
            "/api/chat",
            json={
                "session_id": first_body["session_id"],
                "message": "Use a crisp editorial style",
                "generate_now": True,
                "interview": False,
            },
        )

    assert second.status_code == 200
    assert second.json()["message"] == "implemented"
    assert _FakeBuildRunner.calls == 1
    assert len(_SequencedOrchestrator.calls) == 2
    assert _SequencedOrchestrator.calls[1]["resume"]["run_id"] == waiting_run_id
    assert _SequencedOrchestrator.calls[1]["resume"]["auto_resumed"] is True
    assert _SequencedOrchestrator.calls[1]["resume"]["user_feedback"] == "Use a crisp editorial style"

    with get_db() as session:
        runs = session.query(SessionRun).all()
        assert len(runs) == 1
        run = runs[0]
        assert run.id == waiting_run_id
        assert run.status == "completed"
        state = run.metrics["coordinator"]
        assert [item["phase"] for item in state["phase_history"]] == [
            "implement",
            "implement",
            "build",
            "review",
        ]


def test_chat_stream_endpoint_run_adapter_auto_resumes_waiting_run(tmp_path, monkeypatch) -> None:
    app = _create_app(tmp_path, monkeypatch)
    _FakeBuildRunner.calls = 0
    _FakeReviewService.verdicts = [{"passed": True, "issues": [], "summary": {"error_count": 0}}]
    _SequencedOrchestrator.calls = []
    _SequencedOrchestrator.responses = [
        {
            "phase": "interview",
            "message": "Which visual direction should I use?",
            "is_complete": False,
            "action": "refine_waiting",
            "affected_pages": [],
            "active_page_slug": None,
        },
        {
            "phase": "complete",
            "message": "implemented",
            "is_complete": True,
            "action": "pages_generated",
        },
    ]
    monkeypatch.setattr(chat_api, "BuildRunner", _FakeBuildRunner)
    monkeypatch.setattr(chat_api, "ReviewService", _FakeReviewService)
    monkeypatch.setattr(
        chat_api,
        "_create_orchestrator",
        lambda db, session, emitter: _SequencedOrchestrator(db, session, emitter),
    )

    with TestClient(app) as client:
        first = client.post(
            "/api/chat",
            json={
                "message": "Build a mobile coffee shop",
                "generate_now": True,
                "interview": False,
            },
        )
        assert first.status_code == 200
        first_body = first.json()

        with get_db() as session:
            waiting_run = session.query(SessionRun).one()
            waiting_run_id = waiting_run.id
            assert waiting_run.status == "waiting_input"

        with client.stream(
            "POST",
            "/api/chat/stream",
            json={
                "session_id": first_body["session_id"],
                "message": "Use a crisp editorial style",
                "generate_now": True,
                "interview": False,
            },
        ) as response:
            assert response.status_code == 200
            response_text = "\n".join(
                line.decode() if isinstance(line, bytes) else line
                for line in response.iter_lines()
            )

    payloads = _sse_json_payloads(response_text)
    event_types = [payload["type"] for payload in payloads if "type" in payload]
    lifecycle_events = _filtered_events(
        event_types,
        {"run_resumed", "build_start", "build_complete", "verify_start", "verify_pass", "run_completed"},
    )
    assert lifecycle_events == [
        "run_resumed",
        "build_start",
        "build_complete",
        "verify_start",
        "verify_pass",
        "run_completed",
    ]
    run_scoped_payloads = [
        payload
        for payload in payloads
        if payload.get("type") in {
            "run_resumed",
            "build_start",
            "build_complete",
            "verify_start",
            "verify_pass",
            "run_completed",
        }
    ]
    assert run_scoped_payloads
    assert {payload.get("run_id") for payload in run_scoped_payloads} == {waiting_run_id}
    assert _FakeBuildRunner.calls == 1
    assert len(_SequencedOrchestrator.calls) == 2
    assert _SequencedOrchestrator.calls[1]["resume"]["run_id"] == waiting_run_id
    assert _SequencedOrchestrator.calls[1]["resume"]["auto_resumed"] is True
    assert _SequencedOrchestrator.calls[1]["resume"]["user_feedback"] == "Use a crisp editorial style"

    with get_db() as session:
        runs = session.query(SessionRun).all()
        assert len(runs) == 1
        run = runs[0]
        assert run.id == waiting_run_id
        assert run.status == "completed"
