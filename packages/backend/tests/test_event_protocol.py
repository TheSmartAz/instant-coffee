from __future__ import annotations

import asyncio

from app.agents.generation import GenerationAgent, GenerationProgress, GenerationResult
from app.agents.orchestrator import AgentOrchestrator
from app.agents.sitemap import SitemapResult
from app.db.database import Database
from app.db.migrations import init_db
from app.db.models import ProductDocStatus, Session as SessionModel
from app.db.utils import get_db
from app.events.emitter import EventEmitter
from app.events.models import AgentProgressEvent, AgentStartEvent, DoneEvent, ToolCallEvent, ToolResultEvent
from app.events.types import EventType
from app.schemas.sitemap import GlobalStyle, NavItem, SitemapPage
from app.services.product_doc import ProductDocService


def test_event_model_serialization() -> None:
    event = AgentStartEvent(agent_id="agent-1", agent_type="interview", session_id="session-1")
    payload = event.model_dump(mode="json")
    assert payload["type"] == EventType.AGENT_START.value
    assert "timestamp" in payload
    assert payload["session_id"] == "session-1"

    progress = AgentProgressEvent(agent_id="agent-1", message="Sample prompt")
    sse = progress.to_sse()
    assert sse.startswith("data: ")
    assert "Sample prompt" in sse


def test_event_emitter_emit_and_clear() -> None:
    emitter = EventEmitter()
    event = DoneEvent(summary="ok")
    emitter.emit(event)
    assert emitter.get_events() == [event]
    emitter.clear()
    assert emitter.get_events() == []


def test_orchestrator_stream_events(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "events.db"
    database = Database(f"sqlite:///{db_path}")
    init_db(database)

    async def fake_generate(
        self,
        *,
        requirements=None,
        output_dir=None,
        history=None,
        **kwargs,
    ):
        if self.event_emitter:
            self.event_emitter.emit(
                ToolCallEvent(agent_id=self.agent_id or "generation_1", tool_name="dummy", tool_input=None)
            )
            self.event_emitter.emit(
                ToolResultEvent(
                    agent_id=self.agent_id or "generation_1",
                    tool_name="dummy",
                    success=True,
                    tool_output={"ok": True},
                )
            )
        return GenerationResult(
            html="<p>ok</p>",
            preview_url="file://preview",
            filepath=str(tmp_path / "index.html"),
        )

    async def fake_sitemap_generate(self, product_doc, multi_page=True, explicit_multi_page=False):
        page = SitemapPage(
            title="Home",
            slug="index",
            purpose="Landing",
            sections=["hero"],
            required=True,
        )
        nav = [NavItem(slug="index", label="Home", order=0)]
        style = GlobalStyle(primary_color="#111111", secondary_color="#222222", font_family="Test")
        return SitemapResult(pages=[page], nav=nav, global_style=style, tokens_used=0)

    monkeypatch.setattr(GenerationAgent, "generate", fake_generate)
    monkeypatch.setattr("app.agents.sitemap.SitemapAgent.generate", fake_sitemap_generate)

    with get_db(database) as session:
        record = SessionModel(id="session-1", title="Test Session")
        session.add(record)
        session.flush()
        ProductDocService(session).create(
            record.id,
            content="# Doc",
            structured={
                "project_name": "Test",
                "pages": [
                    {
                        "title": "Home",
                        "slug": "index",
                        "purpose": "Landing",
                        "sections": ["hero"],
                        "required": True,
                    }
                ],
            },
            status=ProductDocStatus.CONFIRMED,
        )
        session.flush()
        orchestrator = AgentOrchestrator(session, record)

        async def collect_events():
            events = []
            async for event in orchestrator.stream(
                user_message="hi",
                output_dir=str(tmp_path),
                skip_interview=True,
            ):
                events.append(event)
            return events

        events = asyncio.run(collect_events())

    event_types = [event.type.value for event in events]
    assert EventType.AGENT_START.value in event_types
    assert EventType.AGENT_PROGRESS.value in event_types
    assert EventType.TOOL_CALL.value in event_types
    assert EventType.TOOL_RESULT.value in event_types
    assert EventType.AGENT_END.value in event_types
    assert EventType.DONE.value in event_types
