from __future__ import annotations

import logging
from pathlib import Path
from datetime import datetime, timezone
from threading import Event
from typing import Any

from sqlalchemy.orm import Session as DbSession

from ..config import get_settings
from ..renderer.builder import BuildError, ReactSSGBuilder
from ..schemas.session_metadata import BuildInfo, BuildStatus
from .page import PageService
from .state_store import StateStoreService

logger = logging.getLogger(__name__)


def build_artifact_base_dir() -> Path:
    """Directory used by ReactSSGBuilder for per-session build artifacts."""
    return Path(get_settings().output_dir).expanduser().resolve()


def build_artifact_session_dir(session_id: str) -> Path:
    return build_artifact_base_dir() / session_id


def build_artifact_dist_dir(session_id: str) -> Path:
    return build_artifact_session_dir(session_id) / "dist"


def build_artifact_log_path(session_id: str) -> Path:
    return build_artifact_session_dir(session_id) / "build.log"


def _format_build_error(exc: Exception) -> str:
    if isinstance(exc, BuildError):
        return exc.summary()
    return str(exc)


class BuildRunner:
    """Reusable build executor for API endpoints and run coordination."""

    def __init__(
        self,
        db: DbSession,
        *,
        event_emitter: Any | None = None,
        cancel_event: Event | None = None,
    ) -> None:
        self.db = db
        self.event_emitter = event_emitter
        self.cancel_event = cancel_event

    async def build_session(self, session_id: str) -> BuildInfo:
        store = StateStoreService(self.db)
        metadata = store.get_metadata(session_id)
        if metadata is None:
            raise ValueError("Session not found")

        started_at = datetime.now(timezone.utc)
        building_info = BuildInfo(
            status=BuildStatus.BUILDING,
            pages=[],
            started_at=started_at,
        )
        store.update_build_info(session_id, building_info)
        self.db.flush()

        try:
            result = await self._build(session_id, metadata.graph_state)
            completed_at = datetime.now(timezone.utc)
            info = BuildInfo(
                status=BuildStatus.SUCCESS,
                pages=(result or {}).get("pages") or [],
                dist_path=(result or {}).get("dist_path"),
                source_mode=(result or {}).get("source_mode"),
                started_at=started_at,
                completed_at=completed_at,
            )
        except Exception as exc:
            logger.exception("Build failed for session %s", session_id)
            completed_at = datetime.now(timezone.utc)
            info = BuildInfo(
                status=BuildStatus.FAILED,
                pages=[],
                error=_format_build_error(exc),
                started_at=started_at,
                completed_at=completed_at,
            )

        store.update_build_info(session_id, info)
        self.db.flush()
        return info

    async def _build(self, session_id: str, _state: dict[str, Any] | None) -> dict[str, Any]:
        workspace_source = self._resolve_workspace_source(session_id)
        builder = ReactSSGBuilder(
            session_id,
            base_dir=build_artifact_base_dir(),
            event_emitter=self.event_emitter,
            cancel_event=self.cancel_event,
        )
        if workspace_source is not None:
            result = await builder.build_from_workspace_source(
                workspace_source,
                pages=self._workspace_page_hints(session_id),
            )
            result["source_mode"] = "workspace"
            return result

        raise BuildError(
            "React app source not found. Generate `src/App.tsx` before building; "
            "static HTML and HTML-to-React builds are no longer supported.",
            stage="workspace_source",
        )

    def _resolve_workspace_source(self, session_id: str) -> Path | None:
        workspace = (Path(get_settings().output_dir).expanduser() / session_id).resolve()
        src_dir = workspace / "src"
        if not src_dir.is_dir():
            return None
        if (src_dir / "App.tsx").is_file():
            return workspace
        return None

    def _workspace_page_hints(self, session_id: str) -> list[dict[str, str]]:
        pages = PageService(self.db).list_by_session(session_id)
        return [{"slug": page.slug, "title": page.title} for page in pages] or [
            {"slug": "index", "title": "Index"}
        ]

__all__ = ["BuildRunner"]
