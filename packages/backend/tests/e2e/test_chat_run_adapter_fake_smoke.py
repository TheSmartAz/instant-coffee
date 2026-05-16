from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import get_settings, refresh_settings
from app.db.database import reset_database
from app.db.migrations import init_db
from app.db.models import SessionRun
from app.db.utils import get_db
from app.events.models import workflow_event
from app.events.types import EventType
from app.schemas.orchestrator_response import OrchestratorResponse
from app.schemas.session_metadata import BuildInfo, BuildStatus
from app.services.product_doc import ProductDocService


class _SmokeOrchestrator:
    def __init__(self, db, session, emitter) -> None:
        self.db = db
        self.session = session
        self.event_emitter = emitter

    async def stream_responses(self, **_kwargs):
        ProductDocService(self.db).create(
            session_id=self.session.id,
            content="# Smoke Product\n\nA tiny product doc for the smoke path.",
            structured={"design_direction": {"tone": "concise"}},
        )
        workspace = Path(get_settings().output_dir).expanduser() / self.session.id
        src_dir = workspace / "src"
        src_dir.mkdir(parents=True, exist_ok=True)
        (src_dir / "App.tsx").write_text(
            "export default function App() { return <main>Smoke React app</main> }\n",
            encoding="utf-8",
        )
        (src_dir / "main.tsx").write_text(
            "import React from 'react'\n"
            "import { createRoot } from 'react-dom/client'\n"
            "import App from './App'\n"
            "createRoot(document.getElementById('root')!).render(<React.StrictMode><App /></React.StrictMode>)\n",
            encoding="utf-8",
        )
        (src_dir / "index.css").write_text(
            "html, body { margin: 0; } .hide-scrollbar { scrollbar-width: none; }\n",
            encoding="utf-8",
        )
        self.db.flush()
        yield OrchestratorResponse(
            session_id=self.session.id,
            phase="complete",
            message="smoke implementation complete",
            is_complete=True,
            action="pages_generated",
            affected_pages=[],
            active_page_slug="index",
        )


class _SmokeBuildRunner:
    def __init__(self, _db, *, event_emitter=None, cancel_event=None) -> None:
        self.event_emitter = event_emitter

    async def build_session(self, session_id: str) -> BuildInfo:
        workspace = Path(get_settings().output_dir).expanduser() / session_id
        assert (workspace / "src" / "App.tsx").is_file()
        if self.event_emitter is not None:
            self.event_emitter.emit(workflow_event(EventType.BUILD_START))
            self.event_emitter.emit(
                workflow_event(
                    EventType.BUILD_COMPLETE,
                    {
                        "status": "success",
                        "pages": ["index.html"],
                        "dist_path": "/tmp/instant-coffee/smoke-dist",
                        "source_mode": "workspace",
                    },
                )
            )
        return BuildInfo(
            status=BuildStatus.SUCCESS,
            pages=["index.html"],
            dist_path="/tmp/instant-coffee/smoke-dist",
            source_mode="workspace",
        )


class _SmokeReviewService:
    def __init__(self, _db) -> None:
        pass

    def review_session(self, _session_id: str) -> dict:
        return {"passed": True, "issues": [], "summary": {"error_count": 0}}


def _sse_payloads(text: str) -> list[dict]:
    payloads = []
    for line in text.splitlines():
        if not line.startswith("data: "):
            continue
        raw = line.removeprefix("data: ")
        if raw == "[DONE]":
            continue
        payloads.append(json.loads(raw))
    return payloads


def test_chat_run_adapter_fake_e2e_smoke(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'fake-chat-adapter-smoke.db'}")
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "output"))
    monkeypatch.setenv("DEFAULT_BASE_URL", "http://localhost")
    monkeypatch.setenv("DEFAULT_KEY", "test-key")
    monkeypatch.setenv("CHAT_USE_RUN_ADAPTER", "true")
    monkeypatch.setenv("RUN_API_ENABLED", "true")
    refresh_settings()
    reset_database()
    init_db()

    from app.api import chat as chat_api
    from app.main import create_app

    monkeypatch.setattr(chat_api, "BuildRunner", _SmokeBuildRunner)
    monkeypatch.setattr(chat_api, "ReviewService", _SmokeReviewService)
    monkeypatch.setattr(
        chat_api,
        "_create_orchestrator",
        lambda db, session, emitter: _SmokeOrchestrator(db, session, emitter),
    )

    app = create_app()
    with TestClient(app) as client:
        with client.stream(
            "POST",
            "/api/chat/stream",
            json={
                "message": "Build a mobile coffee shop page without asking questions.",
                "generate_now": True,
                "interview": False,
            },
        ) as response:
            assert response.status_code == 200
            response_text = "\n".join(
                line.decode() if isinstance(line, bytes) else line
                for line in response.iter_lines()
            )

        with get_db() as session:
            run = session.query(SessionRun).one()
            run_id = run.id
            session_id = run.session_id
            assert run.status == "completed"

        run_detail = client.get(f"/api/runs/{run_id}")

    payloads = _sse_payloads(response_text)
    event_types = [payload["type"] for payload in payloads if "type" in payload]
    expected_lifecycle = [
        "run_created",
        "run_started",
        "build_start",
        "build_complete",
        "verify_start",
        "verify_pass",
        "run_completed",
    ]
    cursor = -1
    for event_type in expected_lifecycle:
        cursor = event_types.index(event_type, cursor + 1)
    assert event_types.count("run_completed") == 1
    assert run_detail.status_code == 200
    detail = run_detail.json()
    assert detail["run_id"] == run_id
    assert detail["status"] == "completed"
    assert detail["current_phase"] == "done"
    assert detail["artifacts"]["build"]["pages"] == ["index.html"]
    assert detail["artifacts"]["build"]["source_mode"] == "workspace"
    assert detail["review_summary"]["error_count"] == 0
    assert (tmp_path / "output" / session_id / "src" / "App.tsx").exists()
