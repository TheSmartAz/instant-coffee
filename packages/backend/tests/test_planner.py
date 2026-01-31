import pytest

from app.config import refresh_settings
from app.planner.base import BasePlanner, PlannerResponseError
from app.planner.factory import PlannerFactory
from app.planner.anthropic_planner import AnthropicPlanner
from app.planner.openai_planner import OpenAIPlanner


class DummyPlanner(BasePlanner):
    async def plan(self, user_message: str, context=None):  # pragma: no cover - test helper
        raise NotImplementedError


def test_build_plan_maps_dependencies():
    planner = DummyPlanner()
    data = {
        "goal": "Test goal",
        "tasks": [
            {"id": "task_1", "title": "First"},
            {"id": "task_2", "title": "Second", "depends_on": ["task_1"]},
        ],
    }
    plan = planner._build_plan(data, "message")
    assert plan.id
    assert len(plan.tasks) == 2
    assert plan.tasks[0].id.startswith(plan.id)
    assert plan.tasks[1].depends_on == [plan.tasks[0].id]


def test_build_plan_requires_tasks():
    planner = DummyPlanner()
    with pytest.raises(PlannerResponseError):
        planner._build_plan({"goal": "none", "tasks": []}, "message")


def test_planner_factory_openai(monkeypatch):
    monkeypatch.setenv("PLANNER_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    refresh_settings()
    planner = PlannerFactory.create()
    assert isinstance(planner, OpenAIPlanner)


def test_planner_factory_anthropic(monkeypatch):
    monkeypatch.setenv("PLANNER_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    refresh_settings()
    planner = PlannerFactory.create()
    assert isinstance(planner, AnthropicPlanner)
