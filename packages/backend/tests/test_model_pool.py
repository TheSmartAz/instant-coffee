import asyncio

from app.config import Settings
from app.llm.model_catalog import model_supports_capability
from app.llm.model_pool import FallbackTrigger, ModelPoolManager
from app.llm.openai_client import TimeoutError


class DummyFactory:
    def create(self, *, model_id: str, base_url=None, api_key=None):
        return object()


def test_model_pool_candidate_priority():
    settings = Settings(default_key="test-key", default_base_url="http://localhost")
    settings.model_light = "light-model"
    settings.model_mid = "mid-model"
    settings.model_heavy = "heavy-model"
    pools = {"writer": {"default": ["heavy", "mid"]}}
    pool = ModelPoolManager(settings=settings, pools=pools, client_factory=DummyFactory())

    candidates = pool.get_candidate_model_ids("writer", product_type="landing", preferred_model="preferred")
    assert candidates[0] == "preferred"
    assert "heavy-model" in candidates
    assert "mid-model" in candidates


def test_model_pool_fallback_on_timeout():
    settings = Settings(default_key="test-key", default_base_url="http://localhost")
    pool = ModelPoolManager(settings=settings, pools={"writer": ["m1", "m2"]}, client_factory=DummyFactory())

    async def call(model_id, client):
        if model_id == "m1":
            raise TimeoutError("timeout")
        return {"model_id": model_id}

    result = asyncio.run(
        pool.run_with_fallback(
            role="writer",
            product_type=None,
            preferred_model=None,
            call=call,
        )
    )
    assert result.model_id == "m2"
    assert result.result["model_id"] == "m2"


def test_model_pool_response_checker():
    settings = Settings(default_key="test-key", default_base_url="http://localhost")
    pool = ModelPoolManager(settings=settings, pools={"writer": ["m1", "m2"]}, client_factory=DummyFactory())

    async def call(model_id, client):
        return {"model_id": model_id}

    def checker(result):
        if result.get("model_id") == "m1":
            return FallbackTrigger.MISSING_FIELD
        return None

    result = asyncio.run(
        pool.run_with_fallback(
            role="writer",
            product_type=None,
            preferred_model=None,
            call=call,
            response_checker=checker,
        )
    )
    assert result.model_id == "m2"


def test_model_pool_capability_filter():
    settings = Settings(default_key="test-key", default_base_url="http://localhost")
    pool = ModelPoolManager(settings=settings, pools={"style_refiner": ["gpt-4o", "text-only"]})

    candidates = pool.get_candidate_model_ids(
        "style_refiner",
        required_capabilities=["vision"],
    )
    assert "gpt-4o" in candidates
    assert "text-only" not in candidates


def test_model_catalog_vision_inference():
    assert model_supports_capability("gpt-4o-mini", "vision") is True
    assert model_supports_capability("text-only-model", "vision") is False
