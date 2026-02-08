import asyncio

from app.agents.orchestrator_routing import OrchestratorRouter
from app.db.models import ProductDoc, Session


class TestProductDocTiersE2E:
    def test_static_type_forces_checklist(self, test_db, test_settings):
        session = Session(id="e2e-doc-static", title="Static")
        test_db.add(session)
        test_db.commit()

        doc = ProductDoc(
            session_id=session.id,
            content="# Doc",
            structured={
                "product_type": "landing",
                "complexity": "simple",
            },
        )
        test_db.add(doc)
        test_db.commit()

        router = OrchestratorRouter(
            db=test_db,
            session_id=session.id,
            settings=test_settings,
        )
        decision = asyncio.run(router.route("Create a landing page", product_doc=doc, session=session))

        assert decision.doc_tier == "checklist"

    def test_flow_type_maps_complexity_to_extended(self, test_db, test_settings):
        session = Session(id="e2e-doc-flow", title="Flow")
        test_db.add(session)
        test_db.commit()

        doc = ProductDoc(
            session_id=session.id,
            content="# Doc",
            structured={
                "product_type": "ecommerce",
                "complexity": "complex",
            },
        )
        test_db.add(doc)
        test_db.commit()

        router = OrchestratorRouter(
            db=test_db,
            session_id=session.id,
            settings=test_settings,
        )
        decision = asyncio.run(router.route("Build an ecommerce flow", product_doc=doc, session=session))

        assert decision.doc_tier == "extended"

    def test_doc_tier_override_is_respected(self, test_db, test_settings):
        session = Session(id="e2e-doc-override", title="Override")
        test_db.add(session)
        test_db.commit()

        doc = ProductDoc(
            session_id=session.id,
            content="# Doc",
            structured={
                "product_type": "ecommerce",
                "complexity": "simple",
                "doc_tier": "standard",
            },
        )
        test_db.add(doc)
        test_db.commit()

        router = OrchestratorRouter(
            db=test_db,
            session_id=session.id,
            settings=test_settings,
        )
        decision = asyncio.run(router.route("Create an ecommerce site", product_doc=doc, session=session))

        assert decision.doc_tier == "standard"
