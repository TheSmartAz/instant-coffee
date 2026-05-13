"""Shared tool error formatting and classification helpers."""

from __future__ import annotations

import asyncio
import re
from typing import Literal


ToolErrorKind = Literal[
    "cancelled",
    "exception",
    "exit_code",
    "invalid_json",
    "not_found",
    "policy_blocked",
    "retry_exhausted",
    "timeout",
    "tool_error",
    "transient",
    "unknown_tool",
    "validation",
]

_ERROR_PREFIX = re.compile(r"^Error\[(?P<kind>[a-z_]+)\]:", re.MULTILINE)


def format_tool_error(kind: ToolErrorKind, message: str) -> str:
    """Return a stable, user-visible tool error string."""
    return f"Error[{kind}]: {message}"


def classify_tool_error(
    output: str | None = None,
    exception: BaseException | None = None,
) -> str | None:
    """Classify tool failures from new stable prefixes or legacy output text."""
    if exception is not None:
        if isinstance(exception, asyncio.CancelledError):
            return "cancelled"
        if isinstance(exception, asyncio.TimeoutError) or type(exception).__name__.endswith("TimeoutError"):
            return "timeout"
        if isinstance(exception, (ConnectionError, OSError, TimeoutError)):
            return "transient"
        return "exception"

    text = (output or "").strip()
    if not text:
        return None

    prefixed = _ERROR_PREFIX.match(text)
    if prefixed:
        return prefixed.group("kind")

    lower = text.lower()
    if lower.startswith("command blocked") or "blocked for safety" in lower:
        return "policy_blocked"
    if lower.startswith("exit code:"):
        return "exit_code"
    if "timed out" in lower or "timeout" in lower:
        return "timeout"
    if "was cancelled" in lower or "cancelled" in lower:
        return "cancelled"
    if lower.startswith("validation errors:"):
        return "validation"
    if "invalid json arguments" in lower:
        return "invalid_json"
    if "unknown tool" in lower:
        return "unknown_tool"
    if "failed after" in lower and "attempt" in lower:
        return "retry_exhausted"
    if lower.startswith("error"):
        return "exception"
    return None
