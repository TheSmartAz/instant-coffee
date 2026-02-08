from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Iterable

from ..config import get_settings

try:  # pragma: no cover - optional dependency
    from langchain_mcp_adapters.client import MultiServerMCPClient
    from langchain_mcp_adapters.tools import load_mcp_tools
except Exception:  # pragma: no cover - optional dependency
    MultiServerMCPClient = None
    load_mcp_tools = None

logger = logging.getLogger(__name__)

_MCP_HANDLER_CACHE: dict[str, dict[str, Callable[..., Any]]] = {}


@dataclass(frozen=True)
class MCPTooling:
    tools: list[dict[str, Any]]
    tool_handlers: dict[str, Callable[..., Any]]


def cache_mcp_handlers(session_id: str | None, handlers: dict[str, Callable[..., Any]]) -> None:
    if not session_id or not handlers:
        return
    _MCP_HANDLER_CACHE[session_id] = handlers


def get_mcp_handlers(session_id: str | None) -> dict[str, Callable[..., Any]]:
    if not session_id:
        return {}
    return _MCP_HANDLER_CACHE.get(session_id, {})


def _mcp_enabled(settings: Any) -> bool:
    return bool(
        getattr(settings, "mcp_enabled", False)
        or getattr(settings, "mcp_servers", None)
        or getattr(settings, "mcp_server_url", None)
    )


async def load_mcp_tooling() -> MCPTooling | None:
    settings = get_settings()
    if not _mcp_enabled(settings):
        return None
    if MultiServerMCPClient is None:
        logger.warning("langchain-mcp-adapters not available; MCP tools disabled")
        return None

    raw_tools: Iterable[Any] = []
    try:
        if getattr(settings, "mcp_servers", None):
            client = MultiServerMCPClient(settings.mcp_servers)
            raw_tools = await client.get_tools()
        elif getattr(settings, "mcp_server_url", None) and load_mcp_tools is not None:
            raw_tools = await load_mcp_tools(settings.mcp_server_url)
    except Exception:
        logger.exception("Failed to load MCP tools")
        return None

    tooling = _normalize_tools(raw_tools)
    if not tooling.tools:
        return None
    return tooling


def _normalize_tools(raw_tools: Iterable[Any]) -> MCPTooling:
    tools: list[dict[str, Any]] = []
    handlers: dict[str, Callable[..., Any]] = {}
    for tool in raw_tools or []:
        name = getattr(tool, "name", None)
        if not name:
            continue
        if name in handlers:
            logger.warning("Duplicate MCP tool name '%s' skipped", name)
            continue
        tools.append(_as_openai_tool(tool))
        handlers[name] = _make_tool_handler(tool)
    return MCPTooling(tools=tools, tool_handlers=handlers)


def _as_openai_tool(tool: Any) -> dict[str, Any]:
    schema = _tool_schema(tool)
    description = getattr(tool, "description", None) or schema.get("description") or ""
    return {
        "type": "function",
        "function": {
            "name": getattr(tool, "name", "mcp_tool"),
            "description": description,
            "parameters": schema,
        },
    }


def _tool_schema(tool: Any) -> dict[str, Any]:
    schema_source = getattr(tool, "tool_call_schema", None) or getattr(tool, "args_schema", None)
    if schema_source is not None:
        if hasattr(schema_source, "model_json_schema"):
            return schema_source.model_json_schema()
        if hasattr(schema_source, "schema"):
            return schema_source.schema()
    return {"type": "object", "properties": {}}


def _make_tool_handler(tool: Any) -> Callable[..., Any]:
    async def handler(**kwargs: Any) -> Any:
        if hasattr(tool, "ainvoke"):
            return await tool.ainvoke(kwargs)
        if hasattr(tool, "invoke"):
            return tool.invoke(kwargs)
        if callable(tool):
            return tool(**kwargs)
        return None

    return handler


__all__ = [
    "MCPTooling",
    "cache_mcp_handlers",
    "get_mcp_handlers",
    "load_mcp_tooling",
]
