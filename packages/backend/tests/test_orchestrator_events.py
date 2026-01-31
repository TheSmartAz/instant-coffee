import asyncio

import pytest

from app.agents.generation import GenerationAgent, GenerationProgress, GenerationResult
from app.agents.orchestrator import AgentOrchestrator
from app.db.database import Database
from app.db.migrations import init_db
from app.db.models import Session
from app.db.utils import get_db


@pytest.fixture()
def database(tmp_path):
    db_path = tmp_path / "test.db"
    db = Database(f"sqlite:///{db_path}")
    init_db(db)
    return db


@pytest.fixture(autouse=True)
def llm_env(monkeypatch):
    monkeypatch.setenv("DEFAULT_BASE_URL", "http://localhost")
    monkeypatch.setenv("DEFAULT_KEY", "test-key")


def test_stream_emits_generation_events(database, monkeypatch, tmp_path):
    async def fake_generate(self, *, requirements, output_dir, history):
        return GenerationResult(
            html="<p>ok</p>",
            preview_url="file:///tmp/test.html",
            filepath="/tmp/test.html",
        )

    monkeypatch.setattr(GenerationAgent, "generate", fake_generate)
    monkeypatch.setattr(
        GenerationAgent,
        "progress_steps",
        lambda self: [
            GenerationProgress(message="step-1", progress=20),
            GenerationProgress(message="step-2", progress=40),
        ],
    )

    with get_db(database) as db:
        session = Session(id="session-1", title="Test")
        db.add(session)
        db.commit()
        db.refresh(session)

        orchestrator = AgentOrchestrator(db, session)

        async def collect():
            return [event async for event in orchestrator.stream(
                user_message="hi",
                output_dir=str(tmp_path),
                skip_interview=True,
            )]

        events = asyncio.run(collect())

    types = [event.type.value for event in events]
    assert "agent_start" in types
    assert "agent_progress" in types
    assert "agent_end" in types
    assert "done" in types
