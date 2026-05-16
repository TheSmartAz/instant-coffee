from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from ..config import get_settings


class ThumbnailService:
    """Creates cached mobile screenshots for project home pages."""

    def __init__(self, *, timeout_seconds: int = 45) -> None:
        self.timeout_seconds = timeout_seconds
        self.output_dir = Path(get_settings().output_dir).expanduser()
        self.repo_root = Path(__file__).resolve().parents[4]

    def thumbnail_path(self, session_id: str) -> Path:
        return (self.output_dir / session_id / "thumbnails" / "home.png").resolve()

    def has_thumbnail(self, session_id: str) -> bool:
        path = self.thumbnail_path(session_id)
        return path.exists() and path.is_file()

    def invalidate(self, session_id: str) -> None:
        try:
            self.thumbnail_path(session_id).unlink(missing_ok=True)
        except Exception:
            pass

    async def capture_html(self, session_id: str, html: str) -> Path | None:
        script = self.repo_root / "packages" / "web" / "scripts" / "capture-thumbnail.mjs"
        web_dir = self.repo_root / "packages" / "web"
        if not script.exists() or not (web_dir / "node_modules" / "playwright").exists():
            return None

        out_path = self.thumbnail_path(session_id)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", suffix=".html", encoding="utf-8", delete=False) as handle:
            handle.write(html)
            html_path = Path(handle.name)

        command = ["node", str(script), "--html", str(html_path), "--out", str(out_path)]
        try:
            proc = await asyncio.create_subprocess_exec(
                *command,
                cwd=str(web_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                await asyncio.wait_for(proc.communicate(), timeout=self.timeout_seconds)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return None
            if proc.returncode != 0 or not out_path.exists():
                return None
            return out_path
        finally:
            try:
                html_path.unlink(missing_ok=True)
            except Exception:
                pass


__all__ = ["ThumbnailService"]
