from __future__ import annotations

from typing import Any


def _as_dict(state: Any) -> dict:
    if isinstance(state, dict):
        return dict(state)
    if hasattr(state, "__dict__"):
        return dict(state.__dict__)
    return {}


async def refine_node(state: Any) -> dict:
    updated = _as_dict(state)
    updated.setdefault("page_schemas", [])
    # Clear feedback after one refinement pass to prevent infinite loops.
    if updated.get("user_feedback"):
        updated["user_feedback"] = None
    return updated


__all__ = ["refine_node"]
