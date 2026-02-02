import asyncio

import pytest

from app.agents.generation import GenerationAgent
from app.agents.orchestrator import AgentOrchestrator
from app.agents.sitemap import SitemapResult
from app.db.database import Database
from app.db.migrations import init_db
from app.db.models import ProductDocStatus, Session
from app.db.utils import get_db
from app.llm.openai_client import LLMResponse
from app.schemas.sitemap import GlobalStyle, NavItem, SitemapPage
from app.services.product_doc import ProductDocService


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
    async def fake_call_llm(self, *args, **kwargs):
        agent_type = kwargs.get("agent_type")
        self._emit_agent_start(context=kwargs.get("context"), agent_type=agent_type)
        self._emit_agent_progress(message="stub", progress=50, agent_type=agent_type)
        self._emit_agent_end(status="success", summary="ok", agent_type=agent_type)
        return LLMResponse(content="<!doctype html><html><body>ok</body></html>")

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

    monkeypatch.setattr(GenerationAgent, "_call_llm", fake_call_llm)
    monkeypatch.setattr("app.agents.sitemap.SitemapAgent.generate", fake_sitemap_generate)

    with get_db(database) as db:
        session = Session(id="session-1", title="Test")
        db.add(session)
        db.commit()
        db.refresh(session)
        ProductDocService(db).create(
            session.id,
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
        db.commit()

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
    assert "agent_end" in types
    assert "done" in types
