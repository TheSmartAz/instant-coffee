import asyncio

import os

from app.config import refresh_settings
from app.graph.graph import create_generation_graph, should_refine, should_score_aesthetic, should_verify
from app.graph.nodes.brief import brief_node
from app.graph.nodes.base import validate_contract_fields
from app.graph.state import GraphState


def test_graph_state_fields_present():
    expected = {
        "session_id",
        "user_input",
        "assets",
        "mcp_tools",
        "product_doc",
        "pages",
        "data_model",
        "style_tokens",
        "component_registry",
        "page_schemas",
        "aesthetic_enabled",
        "aesthetic_scores",
        "aesthetic_suggestions",
        "user_feedback",
        "build_artifacts",
        "build_status",
        "run_id",
        "run_status",
        "data_model_migration",
        "verify_report",
        "verify_blocked",
        "current_node",
        "error",
    }
    fields = set(GraphState.__annotations__.keys())
    assert expected.issubset(fields)


def test_node_contracts_match_state_fields():
    missing = validate_contract_fields(GraphState.__annotations__.keys())
    assert missing == {}


def test_conditional_routing():
    assert should_score_aesthetic({"aesthetic_enabled": False}) == "skip"
    assert (
        should_score_aesthetic(
            {"aesthetic_enabled": True, "product_doc": {"product_type": "landing"}}
        )
        == "aesthetic"
    )
    assert (
        should_score_aesthetic(
            {"aesthetic_enabled": True, "product_doc": {"product_type": "dashboard"}}
        )
        == "skip"
    )

    assert should_refine({"user_feedback": "fix spacing"}) == "refine"
    assert should_refine({"user_feedback": None}) == "render"

    assert should_verify({"verify_blocked": False}) == "pass"
    assert should_verify({"verify_blocked": True}) == "fail"


def test_graph_compiles_and_runs():
    os.environ["LANGGRAPH_CHECKPOINTER"] = "memory"
    refresh_settings()
    graph = create_generation_graph()
    state = {
        "session_id": "session-1",
        "user_input": "hi",
        "assets": [],
        "aesthetic_enabled": False,
        "build_status": "pending",
    }
    result = asyncio.run(graph.ainvoke(state, config={"configurable": {"thread_id": "session-1:test"}}))
    assert result["build_status"] in {"pending", "success"}


def test_brief_node_injects_scene_data_model():
    state = {
        "session_id": "session-1",
        "user_input": "旅行行程规划，包含行程和景点 itinerary",
        "assets": [],
        "aesthetic_enabled": False,
        "build_status": "pending",
    }
    result = asyncio.run(brief_node(state))
    data_model = result.get("data_model")
    assert isinstance(data_model, dict)
    assert "Trip" in data_model.get("entities", {})
