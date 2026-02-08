import asyncio

from app.agents.orchestrator_routing import OrchestratorRouter
from app.db.models import Session


class TestModelFallbackE2E:
    def test_classifier_fallback_on_timeout(self, test_db, test_settings):
        session = Session(id="e2e-fallback", title="Fallback")
        test_db.add(session)
        test_db.commit()

        router = OrchestratorRouter(
            db=test_db,
            session_id=session.id,
            settings=test_settings,
            timeout_seconds=0.01,
        )

        async def slow_classify(*args, **kwargs):
            await asyncio.sleep(0.1)
            return await router.classifier._heuristic_classify("Create a landing page")

        router.classifier.classify = slow_classify

        decision = asyncio.run(router.route("Create a landing page"))

        assert decision.confidence == 0.4
        assert "Fallback routing used" in decision.reasoning
