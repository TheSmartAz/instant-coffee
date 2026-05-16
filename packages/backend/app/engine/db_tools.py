"""DB-backed file tools — subclass agent file tools to persist to the database.

``DBWriteFile`` and ``DBEditFile`` intercept writes to special paths:

- ``PRODUCT.md`` → upsert ``product_docs`` table + create history
- Everything else → filesystem only (delegates to parent)
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Optional

from ic.tools.base import ToolResult
from ic.tools.file import WriteFile, EditFile, MultiEditFile, _resolve

from ..events.emitter import EventEmitter
from ..events.models import WorkflowEvent
from ..events.types import EventType

logger = logging.getLogger(__name__)

_PRODUCT_DOC_NAMES = {"product.md", "product-doc.md"}


def _is_product_doc(file_path: str) -> bool:
    return os.path.basename(file_path).lower() in _PRODUCT_DOC_NAMES


def _normalize_execution_mode(mode: str | None) -> str:
    if mode == "yolo":
        return "auto"
    return mode if mode in {"plan", "agent", "auto"} else "agent"


def _plan_blocked_result(tool_name: str, file_path: str, emitter: Optional[EventEmitter]) -> ToolResult:
    message = (
        f"{tool_name} blocked in Plan only mode for {file_path or 'unknown path'}. "
        "Switch to Agent or Auto to write files."
    )
    if emitter is not None:
        emitter.emit(
            WorkflowEvent(
                type=EventType.TOOL_POLICY_BLOCKED,
                payload={
                    "tool_name": tool_name,
                    "file_path": file_path,
                    "execution_mode": "plan",
                    "reason": "Plan only mode is read-only.",
                },
            )
        )
    return ToolResult(error=message, is_error=True)


class DBWriteFile(WriteFile):
    """WriteFile that also persists PRODUCT.md to the database."""

    def __init__(
        self,
        workspace: Path | None = None,
        *,
        db_session: Any = None,
        session_id: str = "",
        emitter: Optional[EventEmitter] = None,
        engine: Any = None,
        deferred_buffer: Any = None,
        execution_mode: str = "agent",
    ):
        super().__init__(workspace, engine=engine)
        self._db = db_session
        self._session_id = session_id
        self._emitter = emitter
        self._deferred_buffer = deferred_buffer
        self._execution_mode = _normalize_execution_mode(execution_mode)

    async def execute(self, **kwargs: Any) -> ToolResult:
        file_path = kwargs.get("file_path", "")
        content = kwargs.get("content", "")
        if self._execution_mode == "plan":
            return _plan_blocked_result("write_file", file_path, self._emitter)

        # Always write to filesystem first
        result = await super().execute(**kwargs)
        if result.is_error:
            return result

        # Persist to DB (or buffer for deferred flush)
        try:
            if _is_product_doc(file_path):
                self._persist_product_doc(content, file_path)
        except Exception:
            logger.exception("DB persistence failed for %s", file_path)

        return result

    def _persist_product_doc(self, content: str, file_path: str = "") -> None:
        if not self._db or not self._session_id:
            return
        if self._deferred_buffer is not None:
            self._deferred_buffer.record_product_doc(file_path, content)
            return
        from ..services.product_doc import ProductDocService

        svc = ProductDocService(self._db, event_emitter=self._emitter)
        existing = svc.get_by_session_id(self._session_id)

        if existing is None:
            svc.create(
                session_id=self._session_id,
                content=content,
                structured={},
            )
        else:
            svc.update(
                existing.id,
                content=content,
                change_summary="Updated via engine write_file",
            )
        self._db.commit()

class DBEditFile(EditFile):
    """EditFile that also updates PRODUCT.md in the database."""

    def __init__(
        self,
        workspace: Path | None = None,
        *,
        db_session: Any = None,
        session_id: str = "",
        emitter: Optional[EventEmitter] = None,
        engine: Any = None,
        deferred_buffer: Any = None,
        execution_mode: str = "agent",
    ):
        super().__init__(workspace, engine=engine)
        self._db = db_session
        self._session_id = session_id
        self._emitter = emitter
        self._deferred_buffer = deferred_buffer
        self._execution_mode = _normalize_execution_mode(execution_mode)

    async def execute(self, **kwargs: Any) -> ToolResult:
        file_path = kwargs.get("file_path", "")
        if self._execution_mode == "plan":
            return _plan_blocked_result("edit_file", file_path, self._emitter)

        # Execute the edit on filesystem
        result = await super().execute(**kwargs)
        if result.is_error:
            return result

        # Re-read the file and persist to DB (or buffer)
        try:
            resolved = _resolve(file_path, self._workspace)
            if resolved.exists():
                updated_content = resolved.read_text(encoding="utf-8")
                if _is_product_doc(file_path):
                    self._persist_product_doc(updated_content, file_path)
        except Exception:
            logger.exception("DB persistence failed for edit of %s", file_path)

        return result

    def _persist_product_doc(self, content: str, file_path: str = "") -> None:
        if not self._db or not self._session_id:
            return
        if self._deferred_buffer is not None:
            self._deferred_buffer.record_product_doc(file_path, content)
            return
        from ..services.product_doc import ProductDocService

        svc = ProductDocService(self._db, event_emitter=self._emitter)
        existing = svc.get_by_session_id(self._session_id)

        if existing is None:
            svc.create(
                session_id=self._session_id,
                content=content,
                structured={},
            )
        else:
            svc.update(
                existing.id,
                content=content,
                change_summary="Updated via engine edit_file",
            )
        self._db.commit()

class DBMultiEditFile(MultiEditFile):
    """MultiEditFile that also persists PRODUCT.md to the database."""

    def __init__(
        self,
        workspace: Path | None = None,
        *,
        db_session: Any = None,
        session_id: str = "",
        emitter: Optional[EventEmitter] = None,
        deferred_buffer: Any = None,
        execution_mode: str = "agent",
    ):
        super().__init__(workspace)
        self._db = db_session
        self._session_id = session_id
        self._emitter = emitter
        self._deferred_buffer = deferred_buffer
        self._execution_mode = _normalize_execution_mode(execution_mode)

    async def execute(self, **kwargs: Any) -> ToolResult:
        file_path = kwargs.get("file_path", "")
        if self._execution_mode == "plan":
            return _plan_blocked_result("multi_edit_file", file_path, self._emitter)

        result = await super().execute(**kwargs)
        if result.is_error:
            return result

        # Re-read the file and persist to DB (or buffer)
        try:
            resolved = _resolve(file_path, self._workspace)
            if resolved.exists():
                updated_content = resolved.read_text(encoding="utf-8")
                if _is_product_doc(file_path):
                    self._persist_product_doc(updated_content, file_path)
        except Exception:
            logger.exception("DB persistence failed for multi_edit of %s", file_path)

        return result

    def _persist_product_doc(self, content: str, file_path: str = "") -> None:
        if not self._db or not self._session_id:
            return
        if self._deferred_buffer is not None:
            self._deferred_buffer.record_product_doc(file_path, content)
            return
        from ..services.product_doc import ProductDocService

        svc = ProductDocService(self._db, event_emitter=self._emitter)
        existing = svc.get_by_session_id(self._session_id)

        if existing is None:
            svc.create(session_id=self._session_id, content=content, structured={})
        else:
            svc.update(existing.id, content=content, change_summary="Updated via engine multi_edit_file")
        self._db.commit()
