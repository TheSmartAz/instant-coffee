from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy

from .checkpointer import build_checkpointer
from .state import GraphState
from ..config import get_settings
from ..services.run import RunCancelledError, RunService
from .nodes import (
    aesthetic_scorer_node,
    brief_node,
    component_registry_node,
    generate_node,
    mcp_setup_node,
    refine_gate_node,
    refine_node,
    verify_node,
    render_node,
    style_extractor_node,
)
from ..events.models import (
    brief_complete_event,
    brief_start_event,
    generate_complete_event,
    generate_progress_event,
    generate_start_event,
    registry_complete_event,
    registry_start_event,
    refine_complete_event,
    refine_start_event,
    style_extracted_event,
    workflow_event,
)
from ..events.types import EventType

logger = logging.getLogger(__name__)

IO_RETRY = RetryPolicy(max_attempts=2)
LLM_RETRY = RetryPolicy(max_attempts=3)


def should_score_aesthetic(state: GraphState) -> str:
    """Decide whether to run aesthetic scoring."""
    enabled = state.get("aesthetic_enabled")
    if enabled is None:
        enabled = bool(get_settings().aesthetic_scoring_enabled)
    if not enabled:
        return "skip"
    product_doc = state.get("product_doc") or {}
    product_type = ""
    if isinstance(product_doc, dict):
        product_type = product_doc.get("product_type") or product_doc.get("productType") or ""
    if product_type in ("landing", "card", "invitation"):
        return "aesthetic"
    return "skip"


def should_refine(state: GraphState) -> str:
    if state.get("user_feedback"):
        return "refine"
    return "render"


def should_verify(state: GraphState) -> str:
    if not bool(get_settings().verify_gate_enabled):
        return "pass"
    if state.get("verify_blocked"):
        return "fail"
    return "pass"


def _verify_start_event() -> Any:
    return workflow_event(
        EventType.VERIFY_START,
        {"checks": ["build", "structure", "mobile", "security"]},
    )


def _verify_end_event(payload: Optional[dict[str, Any]] = None) -> Any:
    report = payload or {}
    if report.get("overall_passed"):
        return workflow_event(EventType.VERIFY_PASS, {"report": report})

    action = "waiting_input"
    if report.get("overall_passed"):
        action = "pass"
    return workflow_event(
        EventType.VERIFY_FAIL,
        {
            "report": report,
            "action": action,
        },
    )


def _verify_payload(result: dict[str, Any]) -> dict[str, Any]:
    report = result.get("verify_report")
    if isinstance(report, dict):
        return report
    return {
        "overall_passed": not bool(result.get("verify_blocked")),
        "checks": [],
        "retry_count": 0,
    }


def _safe_emit(event_emitter: Any | None, event: Any) -> None:
    if event_emitter is None or event is None:
        return
    try:
        event_emitter.emit(event)
    except Exception:
        logger.debug("Failed to emit workflow event")


def _emit_factory(
    event_emitter: Any | None,
    factory: Optional[Callable[..., Any]],
    payload: Optional[dict[str, Any]] = None,
    *,
    run_id: Optional[str] = None,
) -> None:
    if factory is None:
        return
    if run_id and RunService.is_cancelled(str(run_id)):
        return
    try:
        event = factory(payload) if payload is not None else factory()
    except TypeError:
        event = factory()
    if run_id and RunService.is_cancelled(str(run_id)):
        return
    _safe_emit(event_emitter, event)


def _wrap_node(
    node: Callable[[Any], Any],
    *,
    event_emitter: Any | None,
    start_factory: Optional[Callable[..., Any]] = None,
    progress_factory: Optional[Callable[..., Any]] = None,
    complete_factory: Optional[Callable[..., Any]] = None,
    payload_builder: Optional[Callable[[dict[str, Any]], Optional[dict[str, Any]]]] = None,
    node_kwargs: Optional[dict[str, Any]] = None,
    node_name: Optional[str] = None,
) -> Callable[[Any], Any]:
    async def wrapper(state: Any) -> dict[str, Any]:
        state_dict = dict(state) if isinstance(state, dict) else {}
        current_run_id = state_dict.get("run_id")
        if current_run_id and RunService.is_cancelled(str(current_run_id)):
            raise RunCancelledError(f"Run {current_run_id} cancelled")

        _emit_factory(event_emitter, start_factory, run_id=current_run_id)
        _emit_factory(event_emitter, progress_factory, run_id=current_run_id)
        kwargs = node_kwargs or {}
        result = node(state, **kwargs)
        if hasattr(result, "__await__"):
            result = await result

        if current_run_id and RunService.is_cancelled(str(current_run_id)):
            raise RunCancelledError(f"Run {current_run_id} cancelled")

        payload = None
        if payload_builder and isinstance(result, dict):
            payload = payload_builder(result)
        _emit_factory(event_emitter, complete_factory, payload, run_id=current_run_id)

        if isinstance(result, dict):
            if node_name:
                result.setdefault("current_node", node_name)
            return result

        return result

    return wrapper


def _style_payload(result: dict[str, Any]) -> dict[str, Any]:
    return {"has_tokens": bool(result.get("style_tokens"))}


def _registry_payload(result: dict[str, Any]) -> dict[str, Any]:
    registry = result.get("component_registry") or {}
    if isinstance(registry, dict):
        return {"components": len(registry.get("components") or [])}
    return {}


def _page_schema_payload(result: dict[str, Any]) -> dict[str, Any]:
    schemas = result.get("page_schemas") or []
    if isinstance(schemas, list):
        return {"pages": len(schemas)}
    return {}


def create_generation_graph(event_emitter: Any | None = None, *, checkpointer: Any | None = None):
    graph = StateGraph(GraphState)
    if checkpointer is None:
        checkpointer = build_checkpointer()

    graph.add_node(
        "mcp_setup",
        _wrap_node(
            mcp_setup_node,
            event_emitter=event_emitter,
            node_name="mcp_setup",
        ),
        retry_policy=IO_RETRY,
    )
    graph.add_node(
        "brief",
        _wrap_node(
            brief_node,
            event_emitter=event_emitter,
            start_factory=brief_start_event,
            complete_factory=brief_complete_event,
            node_name="brief",
        ),
    )
    graph.add_node(
        "style_extractor",
        _wrap_node(
            style_extractor_node,
            event_emitter=event_emitter,
            complete_factory=style_extracted_event,
            payload_builder=_style_payload,
            node_name="style_extractor",
        ),
        retry_policy=LLM_RETRY,
    )
    graph.add_node(
        "component_registry",
        _wrap_node(
            component_registry_node,
            event_emitter=event_emitter,
            start_factory=registry_start_event,
            complete_factory=registry_complete_event,
            payload_builder=_registry_payload,
            node_kwargs={"event_emitter": event_emitter},
            node_name="component_registry",
        ),
        retry_policy=LLM_RETRY,
    )
    graph.add_node(
        "generate",
        _wrap_node(
            generate_node,
            event_emitter=event_emitter,
            start_factory=generate_start_event,
            progress_factory=lambda: generate_progress_event(
                step="Generating schemas",
                percent=50,
                message="Generating page schemas",
            ),
            complete_factory=generate_complete_event,
            payload_builder=_page_schema_payload,
            node_kwargs={"event_emitter": event_emitter},
            node_name="generate",
        ),
        retry_policy=IO_RETRY,
    )
    graph.add_node(
        "aesthetic_scorer",
        _wrap_node(
            aesthetic_scorer_node,
            event_emitter=event_emitter,
            node_kwargs={"event_emitter": event_emitter},
            node_name="aesthetic_scorer",
        ),
        retry_policy=LLM_RETRY,
    )
    graph.add_node(
        "refine_gate",
        _wrap_node(
            refine_gate_node,
            event_emitter=event_emitter,
            node_name="refine_gate",
        ),
    )
    graph.add_node(
        "refine",
        _wrap_node(
            refine_node,
            event_emitter=event_emitter,
            start_factory=refine_start_event,
            complete_factory=refine_complete_event,
            payload_builder=_page_schema_payload,
            node_name="refine",
        ),
    )
    graph.add_node(
        "verify",
        _wrap_node(
            verify_node,
            event_emitter=event_emitter,
            start_factory=_verify_start_event,
            complete_factory=_verify_end_event,
            payload_builder=_verify_payload,
            node_name="verify",
        ),
    )
    graph.add_node(
        "render",
        _wrap_node(
            render_node,
            event_emitter=event_emitter,
            node_kwargs={"event_emitter": event_emitter},
            node_name="render",
        ),
        retry_policy=IO_RETRY,
    )

    graph.add_edge(START, "mcp_setup")
    graph.add_edge("mcp_setup", "brief")
    graph.add_edge("brief", "style_extractor")
    graph.add_edge("style_extractor", "component_registry")
    graph.add_edge("component_registry", "generate")

    graph.add_conditional_edges(
        "generate",
        should_score_aesthetic,
        {
            "aesthetic": "aesthetic_scorer",
            "skip": "refine_gate",
        },
    )
    graph.add_edge("aesthetic_scorer", "refine_gate")

    graph.add_conditional_edges(
        "refine_gate",
        should_refine,
        {
            "refine": "refine",
            "render": "verify",
        },
    )
    graph.add_edge("refine", "verify")
    graph.add_conditional_edges(
        "verify",
        should_verify,
        {
            "pass": "render",
            "fail": "refine_gate",
        },
    )
    graph.add_edge("render", END)

    return graph.compile(checkpointer=checkpointer)


__all__ = [
    "create_generation_graph",
    "should_refine",
    "should_score_aesthetic",
    "should_verify",
]
