from __future__ import annotations

from pathlib import Path
from typing import Optional


class FilesystemService:
    def __init__(self, output_dir: str) -> None:
        self.output_dir = Path(output_dir)

    def create_output_directory(self) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        return self.output_dir

    def create_session_directory(self, session_id: str) -> Path:
        base = self.create_output_directory()
        session_dir = base / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        return session_dir

    def save_html(self, session_id: str, html: str, filename: Optional[str] = None) -> Path:
        directory = self.create_session_directory(session_id)
        name = filename or f"{session_id}.html"
        path = directory / name
        path.write_text(html, encoding="utf-8")
        return path


__all__ = ["FilesystemService"]
