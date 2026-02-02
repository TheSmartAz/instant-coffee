import asyncio
import json
import uuid

from app.agents.product_doc import ProductDocAgent
from app.config import Settings
from app.db.database import Database
from app.db.migrations import init_db
from app.db.models import ProductDoc, Session as SessionModel
from app.db.utils import get_db, transaction_scope
from app.events.emitter import EventEmitter
from app.llm.openai_client import LLMResponse, TokenUsage


def _make_agent(db, session_id: str, emitter: EventEmitter | None = None) -> ProductDocAgent:
    settings = Settings(default_key="test-key", default_base_url="http://localhost")
    return ProductDocAgent(db, session_id, settings, event_emitter=emitter)


def _create_session(database: Database, session_id: str) -> None:
    with transaction_scope(database) as session:
        session.add(SessionModel(id=session_id, title="Test Session"))


def test_generate_parsing_and_index_insert():
    agent = _make_agent(None, "session-1")
    content = """---MARKDOWN---
# Product Document
---JSON---
{"project_name": "Test", "pages": [{"title": "About", "slug": "about", "purpose": "Story", "sections": ["story"], "required": false}]}
---MESSAGE---
OK
"""
    parsed = agent._parse_generate_response(content, user_message="Test", interview_context=None)
    structured = agent._ensure_index_page(parsed.structured, user_message="Test")
    slugs = [page.get("slug") for page in structured.get("pages", [])]
    assert "index" in slugs
    assert "about" in slugs


def test_update_parsing_affected_pages_list():
    agent = _make_agent(None, "session-1")
    content = """---MARKDOWN---
# Updated
---JSON---
{"project_name": "Test", "pages": [{"title": "Home", "slug": "index", "purpose": "Landing", "sections": ["hero"], "required": true}]}
---AFFECTED_PAGES---
index, about
---CHANGE_SUMMARY---
Updated sections
---MESSAGE---
Done
"""
    parsed = agent._parse_update_response(content, current_structured={}, user_message="update")
    assert parsed.affected_pages == ["index", "about"]


def test_compute_affected_pages_for_non_page_changes():
    agent = _make_agent(None, "session-1")
    current = {
        "project_name": "Test",
        "goals": ["A"],
        "pages": [
            {"title": "Home", "slug": "index", "purpose": "Landing", "sections": ["hero"], "required": True},
            {"title": "About", "slug": "about", "purpose": "Story", "sections": ["story"], "required": False},
        ],
    }
    updated = {
        "project_name": "Test",
        "goals": ["A", "B"],
        "pages": current["pages"],
    }
    affected = agent._compute_affected_pages(current, updated)
    assert set(affected) == {"index", "about"}


def test_generate_persists_product_doc_and_emits_event(tmp_path, monkeypatch):
    db_path = tmp_path / "product_doc.db"
    database = Database(f"sqlite:///{db_path}")
    init_db(database)

    session_id = uuid.uuid4().hex
    _create_session(database, session_id)
    emitter = EventEmitter(session_id=session_id)

    with get_db(database) as session:
        agent = _make_agent(session, session_id, emitter)

        async def fake_call_llm(*args, **kwargs):
            payload = {
                "project_name": "Test",
                "description": "Sample",
                "pages": [
                    {"title": "About", "slug": "about", "purpose": "Story", "sections": ["story"], "required": False}
                ],
            }
            return LLMResponse(
                content=(
                    "---MARKDOWN---\n# Doc\n---JSON---\n"
                    + json.dumps(payload)
                    + "\n---MESSAGE---\nReady"
                ),
                token_usage=TokenUsage(
                    input_tokens=5,
                    output_tokens=10,
                    total_tokens=15,
                    cost_usd=0.01,
                ),
            )

        monkeypatch.setattr(agent, "_call_llm", fake_call_llm)

        result = asyncio.run(
            agent.generate(
                session_id=session_id,
                user_message="Build a site",
                interview_context=None,
                history=[],
            )
        )
        assert result.tokens_used == 15
        session.commit()

    with get_db(database) as session:
        record = session.get(SessionModel, session_id).product_doc
        assert record is not None
        assert record.structured
        slugs = [page.get("slug") for page in record.structured.get("pages", [])]
        assert "index" in slugs
        assert "about" in slugs

    events = emitter.get_events()
    assert any(getattr(event, "type", None).value == "product_doc_generated" for event in events)


def test_update_persists_change_summary_and_emits_event(tmp_path, monkeypatch):
    db_path = tmp_path / "product_doc_update.db"
    database = Database(f"sqlite:///{db_path}")
    init_db(database)

    session_id = uuid.uuid4().hex
    _create_session(database, session_id)
    emitter = EventEmitter(session_id=session_id)

    with get_db(database) as session:
        agent = _make_agent(session, session_id, emitter)
        service_payload = {
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
        from app.services.product_doc import ProductDocService

        service = ProductDocService(session, event_emitter=emitter)
        record = service.create(session_id, content="# Doc", structured=service_payload)
        record_id = record.id
        session.commit()

    with get_db(database) as session:
        agent = _make_agent(session, session_id, emitter)
        record = session.get(ProductDoc, record_id)

        async def fake_call_llm(*args, **kwargs):
            payload = {
                "project_name": "Test",
                "pages": [
                    {"title": "Home", "slug": "index", "purpose": "Landing", "sections": ["hero", "cta"], "required": True}
                ],
            }
            return LLMResponse(
                content=(
                    "---MARKDOWN---\n# Updated\n---JSON---\n"
                    + json.dumps(payload)
                    + "\n---AFFECTED_PAGES---\nindex\n---CHANGE_SUMMARY---\nAdded CTA\n---MESSAGE---\nUpdated"
                ),
                token_usage=TokenUsage(
                    input_tokens=7,
                    output_tokens=11,
                    total_tokens=18,
                    cost_usd=0.02,
                ),
            )

        monkeypatch.setattr(agent, "_call_llm", fake_call_llm)
        result = asyncio.run(
            agent.update(
                session_id=session_id,
                current_doc=record,
                user_message="Add CTA",
                history=[],
            )
        )
        session.commit()

    assert result.change_summary == "Added CTA"
    assert result.affected_pages == ["index"]

    events = emitter.get_events()
    assert any(getattr(event, "type", None).value == "product_doc_updated" for event in events)
    assert any(getattr(event, "change_summary", None) == "Added CTA" for event in events)
