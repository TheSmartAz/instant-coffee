import json

from fastapi.testclient import TestClient

from app.agents.generation import GenerationAgent, GenerationResult
from app.agents.product_doc import ProductDocAgent, ProductDocGenerateResult
from app.agents.sitemap import SitemapResult
from app.events.models import ToolCallEvent, ToolResultEvent
from app.schemas.sitemap import GlobalStyle, NavItem, SitemapPage
from app.services.product_doc import ProductDocService
import app.db.database as db_module


def _generate_now_message(text: str = "hi") -> str:
    payload = json.dumps({"action": "generate_now", "answers": []})
    return f"{text} <INTERVIEW_ANSWERS>{payload}</INTERVIEW_ANSWERS>"


def _patch_generation_flow(monkeypatch):
    async def fake_product_doc_generate(
        self,
        session_id,
        user_message,
        interview_context=None,
        history=None,
        **kwargs,
    ):
        structured = {
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
        }
        service = ProductDocService(self.db, event_emitter=self.event_emitter)
        resolved_session_id = session_id or self.session_id
        existing = service.get_by_session_id(resolved_session_id)
        if existing is None:
            service.create(resolved_session_id, content="# Doc", structured=structured)
        else:
            service.update(existing.id, content="# Doc", structured=structured)
        return ProductDocGenerateResult(
            content="# Doc",
            structured=structured,
            message="ok",
            tokens_used=0,
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

    monkeypatch.setattr(ProductDocAgent, "generate", fake_product_doc_generate)
    monkeypatch.setattr("app.agents.sitemap.SitemapAgent.generate", fake_sitemap_generate)


def test_chat_stream_emits_tool_events(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("DEFAULT_BASE_URL", "http://localhost")
    monkeypatch.setenv("DEFAULT_KEY", "test-key")
    monkeypatch.setattr(db_module, "_database", None)
    _patch_generation_flow(monkeypatch)

    async def fake_generate(
        self,
        *,
        requirements=None,
        output_dir=None,
        history=None,
        current_html=None,
        stream=True,
        **kwargs,
    ):
        if self.event_emitter:
            self.event_emitter.emit(
                ToolCallEvent(
                    agent_id=self.agent_id or "generation_1",
                    agent_type=self.agent_type,
                    tool_name="dummy",
                    tool_input={"path": "index.html"},
                )
            )
            self.event_emitter.emit(
                ToolResultEvent(
                    agent_id=self.agent_id or "generation_1",
                    agent_type=self.agent_type,
                    tool_name="dummy",
                    success=True,
                    tool_output={"ok": True},
                )
            )
        return GenerationResult(
            html="<p>ok</p>",
            preview_url="file://preview",
            filepath="/tmp/index.html",
        )

    monkeypatch.setattr(GenerationAgent, "generate", fake_generate)

    from app.main import create_app

    app = create_app()

    with TestClient(app) as client:
        with client.stream(
            "GET",
            "/api/chat/stream",
            params={"message": _generate_now_message("hi")},
        ) as response:
            lines = []
            for line in response.iter_lines():
                if not line:
                    continue
                decoded = line.decode() if isinstance(line, bytes) else line
                lines.append(decoded)

    payloads = []
    for line in lines:
        if not line.startswith("data:") or "[DONE]" in line:
            continue
        raw = line.replace("data:", "").strip()
        payloads.append(json.loads(raw))

    types = [payload.get("type") for payload in payloads if "type" in payload]
    assert "tool_call" in types
    assert "tool_result" in types
    assert types.index("tool_call") < types.index("tool_result")


def test_chat_stream_multiple_tool_calls_order(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("DEFAULT_BASE_URL", "http://localhost")
    monkeypatch.setenv("DEFAULT_KEY", "test-key")
    monkeypatch.setattr(db_module, "_database", None)
    _patch_generation_flow(monkeypatch)

    async def fake_generate(
        self,
        *,
        requirements=None,
        output_dir=None,
        history=None,
        current_html=None,
        stream=True,
        **kwargs,
    ):
        if self.event_emitter:
            self.event_emitter.emit(
                ToolCallEvent(
                    agent_id=self.agent_id or "generation_1",
                    agent_type=self.agent_type,
                    tool_name="first",
                    tool_input={"path": "index.html"},
                )
            )
            self.event_emitter.emit(
                ToolResultEvent(
                    agent_id=self.agent_id or "generation_1",
                    agent_type=self.agent_type,
                    tool_name="first",
                    success=True,
                    tool_output={"ok": True},
                )
            )
            self.event_emitter.emit(
                ToolCallEvent(
                    agent_id=self.agent_id or "generation_1",
                    agent_type=self.agent_type,
                    tool_name="second",
                    tool_input={"path": "index.html"},
                )
            )
            self.event_emitter.emit(
                ToolResultEvent(
                    agent_id=self.agent_id or "generation_1",
                    agent_type=self.agent_type,
                    tool_name="second",
                    success=True,
                    tool_output={"ok": True},
                )
            )
        return GenerationResult(
            html="<p>ok</p>",
            preview_url="file://preview",
            filepath="/tmp/index.html",
        )

    monkeypatch.setattr(GenerationAgent, "generate", fake_generate)

    from app.main import create_app

    app = create_app()

    with TestClient(app) as client:
        with client.stream(
            "GET",
            "/api/chat/stream",
            params={"message": _generate_now_message("hi")},
        ) as response:
            lines = []
            for line in response.iter_lines():
                if not line:
                    continue
                decoded = line.decode() if isinstance(line, bytes) else line
                lines.append(decoded)

    payloads = []
    for line in lines:
        if not line.startswith("data:") or "[DONE]" in line:
            continue
        raw = line.replace("data:", "").strip()
        payloads.append(json.loads(raw))

    tool_events = [payload for payload in payloads if payload.get("type") in {"tool_call", "tool_result"}]
    names = [event.get("tool_name") for event in tool_events]
    assert names == ["first", "first", "second", "second"]
    assert tool_events[0]["type"] == "tool_call"
    assert tool_events[1]["type"] == "tool_result"
    assert tool_events[2]["type"] == "tool_call"
    assert tool_events[3]["type"] == "tool_result"
