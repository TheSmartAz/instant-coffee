import asyncio

from app.config import refresh_settings
from app.events.emitter import EventEmitter
from app.events.types import EventType
from app.graph.graph import create_generation_graph, should_verify
from app.graph.nodes.verify import verify_node


def _base_state(**overrides):
    state = {
        "session_id": "session-verify",
        "user_input": "build a page",
        "assets": [],
        "mcp_tools": [],
        "pages": [],
        "page_schemas": [
            {
                "slug": "index",
                "title": "Home",
                "layout": "default",
                "components": [],
            }
        ],
        "aesthetic_enabled": False,
        "aesthetic_suggestions": [],
        "build_status": "pending",
        "run_id": "run-verify",
        "run_status": "running",
        "verify_report": None,
        "verify_blocked": None,
        "current_node": None,
        "error": None,
    }
    state.update(overrides)
    return state


def test_should_verify_routing():
    assert should_verify({"verify_blocked": False}) == "pass"
    assert should_verify({"verify_blocked": True}) == "fail"


def test_verify_node_all_pass(monkeypatch):
    monkeypatch.setenv("VERIFY_GATE_ENABLED", "true")
    monkeypatch.setenv("VERIFY_GATE_AUTO_FIX_ENABLED", "true")
    monkeypatch.setenv("VERIFY_GATE_MAX_RETRY", "1")
    refresh_settings()

    result = asyncio.run(verify_node(_base_state()))
    assert result["verify_blocked"] is False
    assert result["verify_action"] == "pass"
    report = result.get("verify_report") or {}
    assert report.get("overall_passed") is True
    assert len(report.get("checks") or []) == 4


def test_verify_node_single_failure(monkeypatch):
    monkeypatch.setenv("VERIFY_GATE_ENABLED", "true")
    monkeypatch.setenv("VERIFY_GATE_AUTO_FIX_ENABLED", "false")
    monkeypatch.setenv("VERIFY_GATE_MAX_RETRY", "0")
    refresh_settings()

    bad_state = _base_state(page_schemas=[{"slug": "home", "layout": "default", "components": []}])
    result = asyncio.run(verify_node(bad_state))
    assert result["verify_blocked"] is True
    assert result["verify_action"] == "wait"
    report = result.get("verify_report") or {}
    assert report.get("overall_passed") is False
    structure = next((item for item in report.get("checks", []) if item.get("name") == "structure"), None)
    assert structure is not None
    assert structure["passed"] is False


def test_verify_node_retry_exhaustion(monkeypatch):
    monkeypatch.setenv("VERIFY_GATE_ENABLED", "true")
    monkeypatch.setenv("VERIFY_GATE_AUTO_FIX_ENABLED", "true")
    monkeypatch.setenv("VERIFY_GATE_MAX_RETRY", "1")
    refresh_settings()

    bad_state = _base_state(page_schemas=[{"slug": "home", "layout": "unknown", "components": []}])
    result = asyncio.run(verify_node(bad_state))
    assert result["verify_blocked"] is True
    report = result.get("verify_report") or {}
    assert report.get("retry_count") == 1


def test_verify_gate_feature_flag_disabled(monkeypatch):
    monkeypatch.setenv("VERIFY_GATE_ENABLED", "false")
    refresh_settings()

    result = asyncio.run(verify_node(_base_state(page_schemas=[])))
    assert result["verify_blocked"] is False
    report = result.get("verify_report") or {}
    assert report.get("skipped") is True
    assert report.get("overall_passed") is True


def test_graph_emits_verify_events(monkeypatch):
    monkeypatch.setenv("LANGGRAPH_CHECKPOINTER", "memory")
    monkeypatch.setenv("VERIFY_GATE_ENABLED", "true")
    monkeypatch.setenv("VERIFY_GATE_AUTO_FIX_ENABLED", "false")
    refresh_settings()

    emitter = EventEmitter(session_id="session-verify")
    graph = create_generation_graph(event_emitter=emitter)

    state = _base_state(user_feedback="refine once")
    _ = asyncio.run(graph.ainvoke(state, config={"configurable": {"thread_id": "session-verify:run-verify"}}))

    event_types = [getattr(event.type, "value", event.type) for event in emitter.get_events()]
    assert EventType.VERIFY_START.value in event_types
    assert (
        EventType.VERIFY_PASS.value in event_types
        or EventType.VERIFY_FAIL.value in event_types
    )

