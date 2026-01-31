from __future__ import annotations

from pathlib import Path
from typing import Dict

from sqlalchemy.orm import Session as DbSession

from ..config import get_settings
from ..db.models import Session as SessionModel
from .filesystem import FilesystemService
from .version import VersionService


class ExportService:
    def __init__(self, db: DbSession) -> None:
        self.db = db

    def export_session(self, session_id: str, output_dir: str | None = None) -> Dict[str, str]:
        session = self.db.get(SessionModel, session_id)
        if session is None:
            raise ValueError("Session not found")
        settings = get_settings()
        resolved_dir = output_dir or settings.output_dir
        version_service = VersionService(self.db)
        version = version_service.get_version(session_id, session.current_version)
        if version is None:
            raise ValueError("No version to export")
        fs = FilesystemService(resolved_dir)
        path = fs.save_html(session_id, version.html, filename="index.html")
        return {"output_file": str(path)}


__all__ = ["ExportService"]
