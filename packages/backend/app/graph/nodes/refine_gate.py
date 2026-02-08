from __future__ import annotations

from typing import Any

from langgraph.types import interrupt


def _as_dict(state: Any) -> dict:
    if isinstance(state, dict):
        return dict(state)
    if hasattr(state, "__dict__"):
        return dict(state.__dict__)
    return {}


async def refine_gate_node(state: Any) -> dict:
    updated = _as_dict(state)
    if not updated.get("user_feedback"):
        return interrupt(
            {
                "type": "need_user_feedback",
                "message": "Please provide feedback to continue refinement.",
            }
        )
    return updated


__all__ = ["refine_gate_node"]
