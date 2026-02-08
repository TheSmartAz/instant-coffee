from __future__ import annotations

import inspect
from typing import Any, Awaitable, Callable, TypeVar

from .state import GraphState


MAX_RETRIES = 3

StateInput = GraphState | dict[str, Any]
NodeCallable = Callable[[StateInput], Any]
F = TypeVar("F", bound=NodeCallable)


def _as_dict(state: Any) -> dict[str, Any]:
    if isinstance(state, dict):
        return dict(state)
    if hasattr(state, "__dict__"):
        return dict(state.__dict__)
    return {}


async def _call_node(node: NodeCallable, state: StateInput) -> dict[str, Any]:
    result = node(state)
    if inspect.isawaitable(result):
        result = await result
    if isinstance(result, dict):
        return result
    if hasattr(result, "model_dump"):
        return result.model_dump()  # type: ignore[no-any-return]
    return _as_dict(result)


def with_retry(node: F, *, max_retries: int = MAX_RETRIES) -> Callable[[StateInput], Awaitable[dict[str, Any]]]:
    async def wrapper(state: StateInput) -> dict[str, Any]:
        current_state = _as_dict(state)
        retry_count = int(current_state.get("retry_count") or 0)

        while True:
            try:
                return await _call_node(node, current_state)
            except Exception as exc:  # pragma: no cover - exercised in retry tests
                retry_count += 1
                current_state = dict(current_state)
                current_state["retry_count"] = retry_count
                current_state["error"] = str(exc)
                if retry_count >= max_retries:
                    current_state["build_status"] = "failed"
                    return current_state

    return wrapper


__all__ = ["MAX_RETRIES", "with_retry"]
