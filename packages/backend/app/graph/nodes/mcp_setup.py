from __future__ import annotations

from typing import Any

from ..mcp import cache_mcp_handlers, load_mcp_tooling


def _as_dict(state: Any) -> dict:
    if isinstance(state, dict):
        return dict(state)
    if hasattr(state, "__dict__"):
        return dict(state.__dict__)
    return {}


async def mcp_setup_node(state: Any) -> dict:
    updated = _as_dict(state)
    tooling = await load_mcp_tooling()
    if tooling is None:
        updated.setdefault("mcp_tools", [])
        return updated

    cache_mcp_handlers(updated.get("session_id"), tooling.tool_handlers)
    updated["mcp_tools"] = tooling.tools
    return updated


__all__ = ["mcp_setup_node"]
