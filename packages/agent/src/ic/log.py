"""Structured JSON logging for the IC agent engine.

Logs LLM calls, tool executions, and errors in JSON format
for production debugging and observability.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any


class JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "ts": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # Merge extra structured data
        if hasattr(record, "data"):
            entry["data"] = record.data  # type: ignore[attr-defined]
        if record.exc_info and record.exc_info[1]:
            entry["error"] = str(record.exc_info[1])
        return json.dumps(entry, ensure_ascii=False, default=str)


def setup_logging(
    log_dir: Path | None = None,
    level: int = logging.INFO,
) -> logging.Logger:
    """Configure structured logging for the IC agent.

    Args:
        log_dir: Directory for log files. If None, logs to stderr only.
        level: Logging level.

    Returns:
        The root 'ic' logger.
    """
    logger = logging.getLogger("ic")
    logger.setLevel(level)

    # Avoid duplicate handlers on repeated calls
    if logger.handlers:
        return logger

    fmt = JSONFormatter()

    # File handler (JSON lines)
    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_dir / "agent.jsonl", encoding="utf-8")
        fh.setFormatter(fmt)
        fh.setLevel(level)
        logger.addHandler(fh)

    # Stderr handler (only warnings+)
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    sh.setLevel(logging.WARNING)
    logger.addHandler(sh)

    return logger


class LLMCallLogger:
    """Context manager for logging a single LLM API call."""

    def __init__(self, model: str, attempt: int = 0):
        self.model = model
        self.attempt = attempt
        self.start_time = 0.0
        self._logger = logging.getLogger("ic.llm")

    def __enter__(self) -> LLMCallLogger:
        self.start_time = time.monotonic()
        return self

    def __exit__(self, *exc_info: Any) -> None:
        pass

    def success(self, usage: dict, finish_reason: str = "", tool_count: int = 0):
        elapsed = time.monotonic() - self.start_time
        self._logger.info(
            "llm_call",
            extra={"data": {
                "model": self.model,
                "attempt": self.attempt,
                "elapsed_s": round(elapsed, 3),
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "finish_reason": finish_reason,
                "tool_calls": tool_count,
            }},
        )

    def error(self, error: str, partial_text_len: int = 0):
        elapsed = time.monotonic() - self.start_time
        self._logger.warning(
            "llm_call_error",
            extra={"data": {
                "model": self.model,
                "attempt": self.attempt,
                "elapsed_s": round(elapsed, 3),
                "error": error,
                "partial_text_len": partial_text_len,
            }},
        )


def log_tool_execution(
    tool_name: str,
    elapsed_s: float,
    output_len: int,
    is_error: bool = False,
):
    """Log a tool execution result."""
    logger = logging.getLogger("ic.tool")
    logger.info(
        "tool_exec",
        extra={"data": {
            "tool": tool_name,
            "elapsed_s": round(elapsed_s, 3),
            "output_len": output_len,
            "is_error": is_error,
        }},
    )


def log_turn(
    step: int,
    text_len: int,
    tool_calls: int,
    cost: dict[str, Any],
):
    """Log a completed agent turn step."""
    logger = logging.getLogger("ic.engine")
    logger.info(
        "turn_step",
        extra={"data": {
            "step": step,
            "text_len": text_len,
            "tool_calls": tool_calls,
            **cost,
        }},
    )
