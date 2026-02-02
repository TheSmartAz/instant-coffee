import asyncio

import pytest

from app.agents.orchestrator import AgentOrchestrator
from app.agents.refinement import RefinementResult
from app.db.database import Database
from app.db.migrations import init_db
from app.db.models import ProductDocStatus, Session
from app.db.utils import get_db
from app.services.page import PageService
from app.services.product_doc import ProductDocService


@pytest.fixture()
def database(tmp_path):
    db_path = tmp_path / "routing.db"
    db = Database(f"sqlite:///{db_path}")
    init_db(db)
    return db


@pytest.fixture(autouse=True)
def llm_env(monkeypatch):
    monkeypatch.setenv("DEFAULT_BASE_URL", "http://localhost")
    monkeypatch.setenv("DEFAULT_KEY", "test-key")


def _create_session(db, session_id: str = "session-1") -> Session:
    session = Session(id=session_id, title="Test")
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def _create_product_doc(db, session_id: str, status: ProductDocStatus) -> None:
    ProductDocService(db).create(
        session_id,
        content="# Doc",
        structured={
            "project_name": "Test",
            "description": "Sample",
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
        status=status,
    )
    db.commit()


def test_route_no_product_doc(database):
    with get_db(database) as db:
        session = _create_session(db)
        orchestrator = AgentOrchestrator(db, session)
        result = asyncio.run(orchestrator.route("hi", session))
        assert result.route == "product_doc_generation"


def test_route_generate_now_no_doc(database):
    with get_db(database) as db:
        session = _create_session(db)
        orchestrator = AgentOrchestrator(db, session)
        result = asyncio.run(orchestrator.route("hi", session, generate_now=True))
        assert result.route == "product_doc_generation_generate_now"


def test_route_confirm_draft(database):
    with get_db(database) as db:
        session = _create_session(db)
        _create_product_doc(db, session.id, ProductDocStatus.DRAFT)
        orchestrator = AgentOrchestrator(db, session)
        result = asyncio.run(orchestrator.route("confirm", session))
        assert result.route == "product_doc_confirm"


def test_route_generation_pipeline_for_confirmed_doc(database):
    with get_db(database) as db:
        session = _create_session(db)
        _create_product_doc(db, session.id, ProductDocStatus.CONFIRMED)
        orchestrator = AgentOrchestrator(db, session)
        result = asyncio.run(orchestrator.route("continue", session))
        assert result.route == "generation_pipeline"


def test_route_refinement_detects_page(database):
    with get_db(database) as db:
        session = _create_session(db)
        _create_product_doc(db, session.id, ProductDocStatus.CONFIRMED)
        page_service = PageService(db)
        about_page = page_service.create(session.id, title="About", slug="about", description="Story")
        db.commit()
        orchestrator = AgentOrchestrator(db, session)
        result = asyncio.run(orchestrator.route("update about page", session))
        assert result.route == "refinement"
        assert result.target_page is not None
        assert result.target_page.id == about_page.id


def test_refinement_includes_product_doc_context(database, monkeypatch, tmp_path):
    captured = {}

    async def fake_refine(
        self,
        *,
        user_message=None,
        user_input=None,
        page=None,
        product_doc=None,
        global_style=None,
        all_pages=None,
        current_html=None,
        output_dir=None,
        history=None,
    ):
        captured["product_doc"] = product_doc
        return RefinementResult(
            page_id=getattr(page, "id", None),
            html="<!doctype html><html><body>ok</body></html>",
            version=1,
            tokens_used=0,
            changes_made="test",
            preview_url="file:///tmp/index.html",
            filepath="/tmp/index.html",
        )

    monkeypatch.setattr("app.agents.refinement.RefinementAgent.refine", fake_refine)

    with get_db(database) as db:
        session = _create_session(db)
        _create_product_doc(db, session.id, ProductDocStatus.CONFIRMED)
        page_service = PageService(db)
        page_service.create(session.id, title="Home", slug="index", description="Landing")
        db.commit()

        orchestrator = AgentOrchestrator(db, session)

        async def collect():
            return [
                response
                async for response in orchestrator.stream_responses(
                    user_message="update index",
                    output_dir=str(tmp_path),
                    history=[],
                    trigger_interview=False,
                )
            ]

        asyncio.run(collect())

    assert captured.get("product_doc") is not None
