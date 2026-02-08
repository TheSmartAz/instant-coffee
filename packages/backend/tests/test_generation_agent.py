import asyncio
import time
import uuid
from pathlib import Path

import pytest

from app.agents import GenerationAgent
from app.config import Settings
from app.db.database import Database
from app.db.migrations import init_db
from app.db.models import PageVersion, Session as SessionModel
from app.db.utils import get_db, transaction_scope
from app.events.emitter import EventEmitter
from app.llm.openai_client import LLMResponse, TokenUsage
from app.schemas.sitemap import GlobalStyle, NavItem, SitemapPage
from app.services.page import PageService


def _make_agent() -> GenerationAgent:
    settings = Settings(default_key="test-key", default_base_url="http://localhost")
    return GenerationAgent(None, "session-1", settings)


def test_extract_html_strategies():
    agent = _make_agent()
    marker_content = (
        "<HTML_OUTPUT>\n<!DOCTYPE html>\n<html><body>Marker</body></html>\n</HTML_OUTPUT>"
    )
    assert agent._extract_html(marker_content).startswith("<!DOCTYPE html>")

    doctype_content = "prefix <!DOCTYPE html><html><body>Doc</body></html> suffix"
    assert agent._extract_html(doctype_content).startswith("<!DOCTYPE html>")

    html_only = "prefix <html><body>Only</body></html> suffix"
    assert agent._extract_html(html_only).startswith("<html>")

    assert agent._extract_html("no html here") == ""


def test_build_messages_format():
    agent = _make_agent()
    history = [
        {"role": "user", "content": "Earlier request"},
        {"role": "assistant", "content": "Earlier response"},
    ]
    messages = agent._build_messages(
        requirements="Build a landing page",
        history=history,
        current_html="<html><body>Old</body></html>",
        guardrails=None,
    )
    assert messages[0]["role"] == "system"
    assert messages[1]["content"] == "Earlier request"
    assert messages[2]["content"] == "Earlier response"
    final = messages[-1]["content"]
    assert "Requirements:\nBuild a landing page" in final
    assert "Current HTML:\n<html><body>Old</body></html>" in final


def test_save_html_path_handling(tmp_path, monkeypatch):
    agent = _make_agent()
    monkeypatch.setattr(time, "time", lambda: 1.234)
    path_str, preview_url = agent._save_html(html="content", output_dir=str(tmp_path))
    path = Path(path_str)
    assert path.exists()
    assert path.name == "index.html"
    assert path.parent.name == "session-1"
    version_path = path.parent / "v1234_index.html"
    assert version_path.exists()
    assert preview_url == path.as_uri()


def test_write_file_handler_response_format(tmp_path, monkeypatch):
    agent = _make_agent()
    monkeypatch.setattr(time, "time", lambda: 2.222)
    handler = agent._write_file_handler(str(tmp_path))
    result = asyncio.run(handler(path="index.html", content="hello", encoding="utf-8"))
    assert result["success"] is True
    assert result["preview_path"].endswith("index.html")
    assert result["version_path"].startswith("v2222_")
    assert result["output"]["version"] == 2222
    preview_path = Path(result["preview_path"])
    assert preview_path.exists()
    version_path = preview_path.parent / result["version_path"]
    assert version_path.exists()


def test_write_file_handler_rejects_traversal(tmp_path):
    agent = _make_agent()
    handler = agent._write_file_handler(str(tmp_path))
    with pytest.raises(ValueError):
        asyncio.run(handler(path="../oops.html", content="nope"))


def test_generate_integration_with_mocked_llm(tmp_path, monkeypatch):
    agent = _make_agent()
    monkeypatch.setattr(time, "time", lambda: 3.333)

    async def fake_call_llm_with_tools(*args, **kwargs):
        return LLMResponse(
            content=(
                "<HTML_OUTPUT>\n<!DOCTYPE html>"
                "<html><body>Generated</body></html>\n</HTML_OUTPUT>"
            ),
            token_usage=TokenUsage(
                input_tokens=10,
                output_tokens=20,
                total_tokens=30,
                cost_usd=0.01,
            ),
        )

    monkeypatch.setattr(agent, "_call_llm_with_tools", fake_call_llm_with_tools)
    result = asyncio.run(
        agent.generate(
            requirements="Create a page",
            output_dir=str(tmp_path),
            history=[],
        )
    )
    assert "Generated" in result.html
    assert Path(result.filepath).exists()
    assert (Path(result.filepath).parent / "v3333_index.html").exists()
    assert result.token_usage == {
        "input_tokens": 10,
        "output_tokens": 20,
        "total_tokens": 30,
        "cost_usd": 0.01,
    }


def test_generate_integration_fallback(tmp_path, monkeypatch):
    agent = _make_agent()
    monkeypatch.setattr(time, "time", lambda: 4.444)

    async def fail_call_llm_with_tools(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(agent, "_call_llm_with_tools", fail_call_llm_with_tools)
    result = asyncio.run(
        agent.generate(
            requirements="Fallback",
            output_dir=str(tmp_path),
            history=[],
        )
    )
    assert "Fallback" in result.html
    assert Path(result.filepath).exists()
    assert (Path(result.filepath).parent / "v4444_index.html").exists()


def test_generate_multi_page_creates_version(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "generation.db"
    database = Database(f"sqlite:///{db_path}")
    init_db(database)

    session_id = uuid.uuid4().hex
    with transaction_scope(database) as session:
        session.add(SessionModel(id=session_id, title="Test Session"))

    emitter = EventEmitter(session_id=session_id)

    with get_db(database) as session:
        page_service = PageService(session, event_emitter=emitter)
        page = page_service.create(
            session_id=session_id,
            title="Home",
            slug="index",
            description="",
            order_index=0,
        )
        session.commit()

        settings = Settings(default_key="test-key", default_base_url="http://localhost")
        agent = GenerationAgent(session, session_id, settings, event_emitter=emitter)

        async def fake_call_llm(*args, **kwargs):
            return LLMResponse(
                content=(
                    "<HTML_OUTPUT><!DOCTYPE html><html><head></head><body>"
                    "<main><a href=\"about\">About</a></main>"
                    "</body></html></HTML_OUTPUT>"
                ),
                token_usage=TokenUsage(
                    input_tokens=5,
                    output_tokens=5,
                    total_tokens=10,
                    cost_usd=0.0,
                ),
            )

        monkeypatch.setattr(agent, "_call_llm", fake_call_llm)

        page_spec = SitemapPage(
            title="Home",
            slug="index",
            purpose="Landing page",
            sections=["Hero", "Features"],
            required=True,
        )
        global_style = GlobalStyle(
            primary_color="#123ABC",
            secondary_color="#456DEF",
            font_family="Test",
            font_size_base="16px",
            font_size_heading="24px",
            button_height="44px",
            spacing_unit="8px",
            border_radius="8px",
        )
        nav = [
            NavItem(slug="index", label="Home", order=0),
            NavItem(slug="about", label="About", order=1),
        ]
        result = asyncio.run(
            agent.generate(
                page_id=page.id,
                page_spec=page_spec,
                global_style=global_style,
                nav=nav,
                product_doc={"content": "Demo", "structured": {"project_name": "Demo"}},
                all_pages=["index", "about"],
                output_dir=str(tmp_path),
            )
        )
        session.commit()

        versions = session.query(PageVersion).filter(PageVersion.page_id == page.id).all()
        assert len(versions) == 1
        assert versions[0].version == 1
        assert result.version == 1
        assert "site-nav" not in result.html
        assert "pages/about.html" in result.html
