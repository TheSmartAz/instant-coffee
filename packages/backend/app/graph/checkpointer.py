from __future__ import annotations

import logging
import os
from typing import Any

from ..config import get_settings

logger = logging.getLogger(__name__)


def _normalize_mode(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    return normalized or "sqlite"


def _resolve_checkpoint_url(settings: Any) -> str:
    override = getattr(settings, "langgraph_checkpoint_url", None)
    if isinstance(override, str) and override.strip():
        return override.strip()
    return str(getattr(settings, "database_url", ""))


def _sqlite_path_from_url(url: str) -> str:
    if url.startswith("sqlite:////"):
        return "/" + url[len("sqlite:////") :]
    if url.startswith("sqlite:///"):
        return url[len("sqlite:///") :]
    if url.startswith("sqlite://"):
        return url[len("sqlite://") :]
    return url


def _is_test_env() -> bool:
    return bool(os.getenv("PYTEST_CURRENT_TEST"))


def build_checkpointer(settings: Any | None = None) -> Any | None:
    settings = settings or get_settings()
    mode = _normalize_mode(getattr(settings, "langgraph_checkpointer", None))
    if _is_test_env() and mode == "sqlite":
        mode = "memory"

    if mode in {"none", "off", "disabled"}:
        return None

    if mode == "memory":
        try:
            from langgraph.checkpoint.memory import MemorySaver
        except Exception:
            logger.warning("Memory checkpointer unavailable")
            return None
        return MemorySaver()

    if mode == "sqlite":
        url = _resolve_checkpoint_url(settings)
        path = _sqlite_path_from_url(url)
        if not path or path.startswith("postgres"):
            path = "instant-coffee-checkpoints.db"
        try:
            from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
        except Exception:
            try:
                from langgraph.checkpoint.sqlite import SqliteSaver
            except Exception:
                logger.warning("SQLite checkpointer unavailable; install langgraph-checkpoint-sqlite")
                return None
            return SqliteSaver.from_conn_string(path)
        return AsyncSqliteSaver.from_conn_string(path)

    if mode in {"postgres", "postgresql"}:
        url = _resolve_checkpoint_url(settings)
        try:
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        except Exception:
            try:
                from langgraph.checkpoint.postgres import PostgresSaver
            except Exception:
                logger.warning("Postgres checkpointer unavailable; install langgraph-checkpoint-postgres")
                return None
            return PostgresSaver.from_conn_string(url)
        return AsyncPostgresSaver.from_conn_string(url)

    logger.warning("Unknown LangGraph checkpointer mode '%s'", mode)
    return None


__all__ = ["build_checkpointer"]
