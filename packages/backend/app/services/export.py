from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

from sqlalchemy.orm import Session as DbSession

from ..config import get_settings
from ..db.models import Page, Session as SessionModel
from ..schemas.files import FileTreeNode
from ..services.file_tree import FileTreeService
from ..services.page import PageService
from ..services.page_version import PageVersionService
from ..services.product_doc import ProductDocService
from ..utils.datetime import utcnow


@dataclass
class ExportResult:
    export_dir: str
    manifest: dict[str, Any]
    success: bool
    file_path: str
    assets_file: Optional[str] = None


def _iter_file_paths(nodes: Iterable[FileTreeNode]) -> Iterable[str]:
    for node in nodes:
        if node.type == "file":
            yield node.path
        if node.children:
            yield from _iter_file_paths(node.children)


def _destination_for_path(root: Path, relative_path: str) -> Path:
    target = Path(relative_path)
    if target.is_absolute() or ".." in target.parts:
        raise ValueError(f"Unsafe export path: {relative_path}")
    return root / target


def _page_export_path(page: Page) -> str:
    return "index.html" if page.slug == "index" else f"pages/{page.slug}.html"


def _serialize_version(version: Any) -> Optional[int]:
    if version is None:
        return None
    value = getattr(version, "version", None)
    return int(value) if value is not None else None


class ExportService:
    def __init__(self, db: DbSession) -> None:
        self.db = db

    def export_session(
        self,
        session_id: str,
        *,
        output_dir: Optional[str] = None,
        version: Optional[int] = None,
    ) -> ExportResult:
        session = self.db.get(SessionModel, session_id)
        if session is None:
            raise ValueError("Session not found")

        root = self._resolve_export_dir(session_id, output_dir)
        root.mkdir(parents=True, exist_ok=True)

        file_service = FileTreeService(self.db)
        tree = file_service.get_tree(session_id)
        paths = list(_iter_file_paths(tree))

        pages = PageService(self.db).list_by_session(session_id)
        page_entries = self._write_files(
            session=session,
            root=root,
            file_service=file_service,
            paths=paths,
            pages=pages,
            version=version,
        )
        asset_entries = self._asset_entries(root, paths)
        product_doc = ProductDocService(self.db).get_by_session_id(session_id)

        product_doc_status = None
        if product_doc is not None:
            product_doc_status = getattr(product_doc.status, "value", product_doc.status)

        manifest = {
            "version": "1.0",
            "exported_at": utcnow().isoformat(),
            "session_id": session_id,
            "product_doc": {
                "included": product_doc is not None,
                "status": product_doc_status if product_doc is not None else "missing",
            },
            "pages": page_entries,
            "assets": asset_entries,
        }

        manifest_path = root / "export_manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        success = all(page["status"] == "success" for page in page_entries)
        return ExportResult(
            export_dir=str(root),
            manifest=manifest,
            success=success,
            file_path=str(root / "index.html"),
            assets_file=str(manifest_path),
        )

    def _resolve_export_dir(self, session_id: str, output_dir: Optional[str]) -> Path:
        if output_dir and output_dir.strip():
            candidate = Path(output_dir).expanduser()
        else:
            candidate = Path(get_settings().output_dir).expanduser() / session_id / "export"
        return candidate.resolve()

    def _write_files(
        self,
        *,
        session: SessionModel,
        root: Path,
        file_service: FileTreeService,
        paths: list[str],
        pages: list[Page],
        version: Optional[int],
    ) -> list[dict[str, Any]]:
        page_entries = self._page_entries(session=session, pages=pages, paths=paths)
        page_entries_by_path = {entry["path"]: entry for entry in page_entries}
        is_react = (Path(get_settings().output_dir).expanduser() / session.id / "src" / "App.tsx").is_file()

        for path in paths:
            content_payload = file_service.get_file_content(session.id, path)
            content = content_payload.content if content_payload is not None else None
            if content is None or (path.endswith(".html") and not content.strip()):
                page_entry = page_entries_by_path.get(path)
                if page_entry is not None:
                    page_entry["status"] = "failed"
                    page_entry["error"] = "File content unavailable"
                continue

            destination = _destination_for_path(root, path)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(content, encoding="utf-8")

            # For React workspaces, also copy workspace files to the root so the
            # export is a runnable Vite project (src/ sits at the top level).
            if is_react and path.startswith("workspace/"):
                relative = path[len("workspace/"):]
                if relative:
                    alt = _destination_for_path(root, relative)
                    alt.parent.mkdir(parents=True, exist_ok=True)
                    alt.write_text(content, encoding="utf-8")

            page_entry = page_entries_by_path.get(path)
            if page_entry is not None:
                page_entry["status"] = "success"
                page_entry["size"] = len(content.encode("utf-8"))

        return page_entries

    def _page_entries(
        self,
        *,
        session: SessionModel,
        pages: list[Page],
        paths: list[str],
    ) -> list[dict[str, Any]]:
        if not pages:
            return [
                {
                    "slug": "index",
                    "title": session.title,
                    "path": "index.html",
                    "status": "failed",
                    "version": session.current_version,
                }
            ]

        version_service = PageVersionService(self.db)
        entries = []
        for page in pages:
            path = _page_export_path(page)
            current = version_service.get_current(page.id)
            entries.append(
                {
                    "slug": page.slug,
                    "title": page.title,
                    "path": path,
                    "status": "failed",
                    "version": _serialize_version(current),
                }
            )
        return entries

    def _asset_entries(self, root: Path, paths: list[str]) -> list[dict[str, Any]]:
        entries = []
        for path in paths:
            if not path.startswith("assets/"):
                continue
            destination = _destination_for_path(root, path)
            entries.append(
                {
                    "path": path,
                    "size": destination.stat().st_size if destination.exists() else 0,
                }
            )
        return entries

__all__ = ["ExportResult", "ExportService"]
