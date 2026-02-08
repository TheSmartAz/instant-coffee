import asyncio

import pytest

from app.agents.classifier import ProductClassification, ProductClassifier
from app.agents.orchestrator_routing import (
    ComplexityEvaluator,
    ComplexityReport,
    OrchestratorRouter,
    PageTargetResolver,
    SkillSelector,
)
from app.config import refresh_settings
from app.db.models import Page


@pytest.fixture()
def settings(monkeypatch):
    monkeypatch.setenv("DEFAULT_BASE_URL", "http://localhost")
    monkeypatch.setenv("DEFAULT_KEY", "test-key")
    return refresh_settings()


def test_product_classifier_ecommerce(settings):
    classifier = ProductClassifier(None, "session-1", settings)
    result = asyncio.run(classifier.classify("I want an online store", use_llm=False))
    assert result.product_type == "ecommerce"
    assert result.confidence >= 0.7


def test_complexity_evaluator_levels(settings):
    evaluator = ComplexityEvaluator(None, "session-1", settings)

    simple = asyncio.run(evaluator.evaluate("Single page showcase", "landing", use_llm=False))
    assert simple.level == "simple"

    medium = asyncio.run(
        evaluator.evaluate("We need a multi-page site with a contact form", "landing", use_llm=False)
    )
    assert medium.level == "medium"

    complex_report = asyncio.run(
        evaluator.evaluate("Multi-page ecommerce with cart, checkout, and user accounts", "ecommerce", use_llm=False)
    )
    assert complex_report.level == "complex"


def test_page_target_resolver():
    resolver = PageTargetResolver()
    pages = [
        Page(session_id="s1", slug="home", title="Home", description=""),
        Page(session_id="s1", slug="about-us", title="About Us", description=""),
    ]
    result = resolver.parse("Update @Home and @about", pages)
    assert "home" in result
    assert "about-us" in result


def test_skill_selector_matches():
    selector = SkillSelector()
    ecommerce = selector.select("ecommerce", "simple")
    assert ecommerce.skill_id == "flow-ecommerce-v1"

    landing = selector.select("landing", "simple")
    assert landing.skill_id == "static-landing-v1"

    invitation = selector.select("invitation", "simple")
    assert invitation.skill_id == "static-invitation-v1"


def test_orchestrator_router_flow(settings):
    class FakeClassifier:
        async def classify(self, _input, use_llm=True):
            return ProductClassification(product_type="landing", confidence=0.9, reasoning="fake")

    class FakeComplexityEvaluator:
        async def evaluate(self, _input, _product_type, use_llm=True):
            return ComplexityReport(
                level="simple",
                page_count_estimate=1,
                has_cross_page_data_flow=False,
                has_forms=False,
                data_structure_complexity="simple",
                scores={},
            )

    router = OrchestratorRouter(
        db=None,
        session_id="session-1",
        settings=settings,
        classifier=FakeClassifier(),
        complexity_evaluator=FakeComplexityEvaluator(),
    )
    decision = asyncio.run(router.route("Create a landing page"))
    assert decision.product_type == "landing"
    assert decision.doc_tier == "checklist"
    assert decision.skill_id == "static-landing-v1"
    assert "hard" in decision.guardrails


def test_orchestrator_router_uses_scenario_detector(settings):
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
        session_id="session-1",
        settings=settings,
        classifier=FakeClassifier(),
        complexity_evaluator=FakeComplexityEvaluator(),
    )
    decision = asyncio.run(router.route("旅行行程规划，包含行程和景点 itinerary"))
    assert decision.product_type == "travel"
    assert decision.skill_id == "flow-travel-v1"
