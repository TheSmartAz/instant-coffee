from __future__ import annotations

from typing import Any, Optional, TypedDict


class GraphState(TypedDict, total=False):
    """LangGraph state payload for the generation workflow."""

    # Input
    session_id: str
    user_input: str
    assets: list[dict[str, Any]]
    mcp_tools: list[dict[str, Any]]

    # Brief output
    product_doc: Optional[dict[str, Any]]
    pages: list[dict[str, Any]]
    data_model: Optional[dict[str, Any]]

    # Style output
    style_tokens: Optional[dict[str, Any]]

    # Component registry output
    component_registry: Optional[dict[str, Any]]
    component_registry_hash: Optional[str]

    # Generate output
    page_schemas: list[dict[str, Any]]

    # Aesthetic scorer output
    aesthetic_enabled: bool
    aesthetic_scores: Optional[dict[str, Any]]
    aesthetic_suggestions: list[dict[str, Any]]

    # Refine input/output
    user_feedback: Optional[str]

    # Render output
    build_artifacts: Optional[dict[str, Any]]
    build_status: str

    # Runtime
    run_id: Optional[str]
    run_status: str
    data_model_migration: Optional[dict[str, Any]]
    verify_report: Optional[dict[str, Any]]
    verify_blocked: Optional[bool]
    current_node: Optional[str]

    # Error handling
    error: Optional[str]


__all__ = ["GraphState"]
