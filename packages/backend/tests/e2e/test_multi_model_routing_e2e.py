import asyncio

from app.agents.orchestrator import AgentOrchestrator
from app.agents.orchestrator_routing import OrchestratorRouter
from app.db.models import Session
from app.llm.model_pool import ModelRole


class TestMultiModelRoutingE2E:
    def test_model_roles_defined(self):
        expected = {"classifier", "writer", "validator", "expander", "style_refiner"}
        actual = {role.value for role in ModelRole}
        assert expected.issubset(actual)

    def test_model_prefs_resolved_from_manifest(self, test_db, test_settings):
        session = Session(id="e2e-model-prefs", title="Models")
        test_db.add(session)
        test_db.commit()

        router = OrchestratorRouter(
            db=test_db,
            session_id=session.id,
            settings=test_settings,
        )

        decision = asyncio.run(router.route("Create an ecommerce store with cart"))

        assert decision.model_prefs["classifier"] == "test-light"
        assert decision.model_prefs["writer"] == "test-heavy"
        assert decision.model_prefs["expander"] == "test-mid"
        assert decision.model_prefs["validator"] == "test-light"

    def test_session_model_fields_updated(self, test_db, test_settings):
        session = Session(id="e2e-model-session", title="Session Models")
        test_db.add(session)
        test_db.commit()

        router = OrchestratorRouter(
            db=test_db,
            session_id=session.id,
            settings=test_settings,
        )
        decision = asyncio.run(router.route("Build an ecommerce checkout flow"))

        orchestrator = AgentOrchestrator(test_db, session)
        orchestrator._apply_routing_metadata(decision)
        test_db.commit()

        refreshed = test_db.get(Session, session.id)
        assert refreshed.model_classifier == "test-light"
        assert refreshed.model_writer == "test-heavy"
        assert refreshed.model_expander == "test-mid"
        assert refreshed.model_validator == "test-light"
