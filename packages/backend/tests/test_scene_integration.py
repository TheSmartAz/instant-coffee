import asyncio
import json
import uuid

from app.agents.classifier import ProductClassification
from app.agents.orchestrator_routing import ComplexityReport, OrchestratorRouter
from app.agents.product_doc import ProductDocAgent
from app.config import Settings
from app.db.database import Database
from app.db.migrations import init_db
from app.db.models import Session as SessionModel
from app.db.utils import get_db, transaction_scope
from app.llm.openai_client import LLMResponse, TokenUsage
from app.services.product_doc import ProductDocService


def test_route_to_product_doc_persists_data_model(tmp_path, monkeypatch):
    db_path = tmp_path / "scene_integration.db"
    database = Database(f"sqlite:///{db_path}")
    init_db(database)

    session_id = uuid.uuid4().hex
    with transaction_scope(database) as session:
        session.add(SessionModel(id=session_id, title="Scene Test"))

    settings = Settings(default_key="test-key", default_base_url="http://localhost")

    class FakeClassifier:
        async def classify(self, _input, use_llm=True):
            return ProductClassification(product_type="landing", confidence=0.9, reasoning="fake")

    class FakeComplexityEvaluator:
        async def evaluate(self, _input, _product_type, use_llm=True):
            return ComplexityReport(
                level="medium",
                page_count_estimate=3,
                has_cross_page_data_flow=True,
                has_forms=False,
                data_structure_complexity="medium",
                scores={},
            )

    router = OrchestratorRouter(
        db=None,
        session_id=session_id,
        settings=settings,
        classifier=FakeClassifier(),
        complexity_evaluator=FakeComplexityEvaluator(),
    )
    decision = asyncio.run(router.route("旅行行程规划，包含行程和景点 itinerary"))
    assert decision.product_type == "travel"

    with get_db(database) as db:
        session = db.get(SessionModel, session_id)
        session.product_type = decision.product_type
        session.complexity = decision.complexity
        session.doc_tier = decision.doc_tier
        db.commit()

        async def fake_call_llm(self, *args, **kwargs):
            payload = {
                "project_name": "Trip Planner",
                "goal": "Plan a trip",
                "pages": [{"title": "Overview", "slug": "index", "purpose": "Plan"}],
            }
            return LLMResponse(
                content=(
                    "---MARKDOWN---\n# Doc\n---JSON---\n"
                    + json.dumps(payload)
                    + "\n---MESSAGE---\nOK"
                ),
                token_usage=TokenUsage(input_tokens=5, output_tokens=10, total_tokens=15, cost_usd=0.0),
            )

        monkeypatch.setattr(ProductDocAgent, "_call_llm", fake_call_llm)

        agent = ProductDocAgent(db, session_id, settings)
        asyncio.run(agent.generate(session_id, "旅行行程", interview_context=None, history=[]))

        product_doc = ProductDocService(db).get_by_session_id(session_id)
        structured = product_doc.structured
        assert structured.get("product_type") == "travel"
        data_model = structured.get("data_model")
        assert isinstance(data_model, dict)
        assert "Trip" in data_model.get("entities", {})
