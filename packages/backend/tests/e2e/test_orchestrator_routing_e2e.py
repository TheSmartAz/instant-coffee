import asyncio

from app.agents.orchestrator import AgentOrchestrator
from app.agents.orchestrator_routing import OrchestratorRouter
from app.db.models import Page, Session
from app.services.page import PageService


class TestOrchestratorRoutingE2E:
    def test_ecommerce_classification_routing(self, test_db, test_settings):
        session = Session(id="e2e-ecommerce", title="Ecommerce")
        test_db.add(session)
        test_db.commit()

        router = OrchestratorRouter(
            db=test_db,
            session_id=session.id,
            settings=test_settings,
        )

        decision = asyncio.run(router.route("I want an online store with products"))

        assert decision.product_type == "ecommerce"
        assert decision.confidence >= 0.5
        assert decision.skill_id is not None
        assert "ecommerce" in decision.skill_id
        assert decision.doc_tier in {"checklist", "standard", "extended"}
        assert "hard" in decision.guardrails
        assert len(decision.guardrails.get("hard", [])) >= 3

        orchestrator = AgentOrchestrator(test_db, session)
        orchestrator._apply_routing_metadata(decision)
        test_db.commit()

        refreshed = test_db.get(Session, session.id)
        assert refreshed.product_type == "ecommerce"
        assert refreshed.skill_id == decision.skill_id
        assert refreshed.doc_tier == decision.doc_tier

    def test_landing_page_routes_to_checklist(self, test_db, test_settings):
        session = Session(id="e2e-landing", title="Landing")
        test_db.add(session)
        test_db.commit()

        router = OrchestratorRouter(
            db=test_db,
            session_id=session.id,
            settings=test_settings,
        )

        decision = asyncio.run(router.route("Create a landing page for my app"))

        assert decision.product_type == "landing"
        assert decision.skill_id == "static-landing-v1"
        assert decision.doc_tier == "checklist"

    def test_page_mentions_resolve_targets(self, test_db, test_settings):
        session = Session(id="e2e-targets", title="Targets")
        test_db.add(session)
        test_db.commit()

        page_service = PageService(test_db)
        page_service.create(session.id, title="Home", slug="home", description="Home")
        page_service.create(session.id, title="About", slug="about", description="About")
        test_db.commit()

        pages = test_db.query(Page).filter(Page.session_id == session.id).all()

        router = OrchestratorRouter(
            db=test_db,
            session_id=session.id,
            settings=test_settings,
        )

        decision = asyncio.run(router.route("Update @Home hero section", project_pages=pages))

        assert "home" in decision.target_pages
        assert "about" not in decision.target_pages
