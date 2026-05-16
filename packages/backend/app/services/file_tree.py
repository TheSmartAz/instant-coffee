from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.parse import unquote

from sqlalchemy.orm import Session as DbSession

from ..config import get_settings
from ..db.models import Page, Session as SessionModel
from ..schemas.files import FileTreeNode
from ..services.page import PageService
from ..services.page_version import PageVersionService
from ..services.product_doc import ProductDocService
from ..services.state_store import StateStoreService
from ..services.version import VersionService
import re

from ..utils.html import ensure_css_link
from ..utils.style import build_site_css


@dataclass
class FileContent:
    path: str
    content: str
    language: str
    size: int


def _content_size(content: str) -> int:
    return len((content or "").encode("utf-8"))


def _get_language(path: str) -> str:
    if path.endswith(".tsx") or path.endswith(".jsx"):
        return "tsx"
    if path.endswith(".ts"):
        return "typescript"
    if path.endswith(".html"):
        return "html"
    if path.endswith(".css"):
        return "css"
    if path.endswith(".js"):
        return "javascript"
    if path.endswith(".md"):
        return "markdown"
    return "plaintext"


def _normalize_path(path: str) -> str:
    resolved = unquote(path or "")
    resolved = resolved.strip()
    if resolved.startswith("/"):
        resolved = resolved.lstrip("/")
    return resolved


class FileTreeService:
    def __init__(
        self,
        db: DbSession,
        *,
        page_service: Optional[PageService] = None,
        page_version_service: Optional[PageVersionService] = None,
        product_doc_service: Optional[ProductDocService] = None,
    ) -> None:
        self.db = db
        self._page_service = page_service or PageService(db)
        self._page_version_service = page_version_service or PageVersionService(db)
        self._product_doc_service = product_doc_service or ProductDocService(db)

    def get_tree(self, session_id: str) -> List[FileTreeNode]:
        pages = self._page_service.list_by_session(session_id)
        index_page = next((page for page in pages if page.slug == "index"), None)
        other_pages = [page for page in pages if page.slug != "index"]
        index_html = self._resolve_index_html(session_id)

        tree: List[FileTreeNode] = [
            FileTreeNode(
                name="index.html",
                path="index.html",
                type="file",
                size=_content_size(index_html),
            )
        ]

        if other_pages:
            children = [
                FileTreeNode(
                    name=f"{page.slug}.html",
                    path=f"pages/{page.slug}.html",
                    type="file",
                    size=_content_size(self._get_page_html(page)),
                )
                for page in other_pages
            ]
            tree.append(
                FileTreeNode(
                    name="pages",
                    path="pages",
                    type="directory",
                    children=children,
                )
            )

        site_css = self._build_site_css(session_id)
        tree.append(
            FileTreeNode(
                name="assets",
                path="assets",
                type="directory",
                children=[
                    FileTreeNode(
                        name="site.css",
                        path="assets/site.css",
                        type="file",
                        size=_content_size(site_css),
                    )
                ],
            )
        )

        product_doc = self._product_doc_service.get_by_session_id(session_id)
        if product_doc is not None:
            tree.append(
                FileTreeNode(
                    name="product-doc.md",
                    path="product-doc.md",
                    type="file",
                    size=_content_size(product_doc.content or ""),
                )
            )

        workspace_children = self._workspace_tree(session_id)
        if workspace_children:
            tree.append(
                FileTreeNode(
                    name="workspace",
                    path="workspace",
                    type="directory",
                    children=workspace_children,
                )
            )

        return tree

    def get_file_content(self, session_id: str, path: str) -> Optional[FileContent]:
        resolved_path = _normalize_path(path)
        if not resolved_path:
            return None

        content = None
        if resolved_path == "index.html":
            content = self._resolve_index_html(session_id)
        elif resolved_path == "assets/site.css":
            content = self._build_site_css(session_id)
        elif resolved_path == "product-doc.md":
            product_doc = self._product_doc_service.get_by_session_id(session_id)
            if product_doc is None:
                return None
            content = product_doc.content or ""
        elif resolved_path.startswith("pages/") and resolved_path.endswith(".html"):
            slug = resolved_path[len("pages/") : -len(".html")]
            if not slug:
                return None
            page = self._page_service.get_by_slug(session_id, slug)
            if page is None:
                return None
            content = self._get_page_html(page)
        elif resolved_path.startswith("workspace/"):
            content = self._read_workspace_file(session_id, resolved_path[len("workspace/") :])
            if content is None:
                return None
        else:
            return None

        content = content or ""
        return FileContent(
            path=resolved_path,
            content=content,
            language=_get_language(resolved_path),
            size=_content_size(content),
        )

    def _workspace_root(self, session_id: str) -> Optional[Path]:
        root = (Path(get_settings().output_dir).expanduser() / session_id).resolve()
        if not root.is_dir():
            return None
        return root

    def _workspace_tree(self, session_id: str) -> list[FileTreeNode]:
        root = self._workspace_root(session_id)
        if root is None:
            return []
        files: list[Path] = []
        for candidate in root.rglob("*"):
            if len(files) >= 200:
                break
            if not candidate.is_file() or self._skip_workspace_file(root, candidate):
                continue
            files.append(candidate)
        return self._nodes_from_workspace_files(root, sorted(files))

    def _skip_workspace_file(self, root: Path, path: Path) -> bool:
        try:
            rel = path.relative_to(root)
        except ValueError:
            return True
        parts = set(rel.parts)
        if parts & {"node_modules", "__pycache__", ".pytest_cache", ".visual-check", "visual-check", "dist"}:
            return True
        name = path.name.lower()
        if name in {"product.md", "product-doc.md"}:
            return True
        if name.endswith((".html", ".db", ".sqlite", ".png", ".jpg", ".jpeg", ".gif", ".webp")):
            return True
        try:
            return path.stat().st_size > 1_000_000
        except OSError:
            return True

    def _nodes_from_workspace_files(self, root: Path, files: list[Path]) -> list[FileTreeNode]:
        tree: dict[str, dict] = {}
        for file_path in files:
            rel = file_path.relative_to(root)
            cursor = tree
            for part in rel.parts[:-1]:
                cursor = cursor.setdefault(part, {})
            cursor[rel.parts[-1]] = {"__file__": file_path}

        def build_nodes(prefix: str, branch: dict[str, dict]) -> list[FileTreeNode]:
            nodes: list[FileTreeNode] = []
            for name, value in sorted(branch.items()):
                path = f"{prefix}/{name}" if prefix else name
                file_path = value.get("__file__") if isinstance(value, dict) else None
                if isinstance(file_path, Path):
                    nodes.append(
                        FileTreeNode(
                            name=name,
                            path=f"workspace/{path}",
                            type="file",
                            size=file_path.stat().st_size,
                        )
                    )
                else:
                    nodes.append(
                        FileTreeNode(
                            name=name,
                            path=f"workspace/{path}",
                            type="directory",
                            children=build_nodes(path, value),
                        )
                    )
            return nodes

        return build_nodes("", tree)

    def _read_workspace_file(self, session_id: str, relative_path: str) -> Optional[str]:
        root = self._workspace_root(session_id)
        if root is None:
            return None
        try:
            candidate = (root / _normalize_path(relative_path)).resolve()
        except OSError:
            return None
        if candidate != root and root not in candidate.parents:
            return None
        if not candidate.is_file() or self._skip_workspace_file(root, candidate):
            return None
        try:
            return candidate.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return None
        except OSError:
            return None

    def _resolve_index_html(self, session_id: str) -> str:
        page = self._page_service.get_by_slug(session_id, "index")
        if page is not None:
            return self._get_page_html(page)
        dist_html = self._read_dist_page_html(session_id, "index")
        if dist_html is not None:
            return dist_html
        legacy_html = self._get_legacy_index_html(session_id)
        return legacy_html or ""

    def _get_page_html(self, page: Page) -> str:
        version = self._page_version_service.get_current(page.id)
        if version is None:
            versions = self._page_version_service.list_by_page(page.id)
            version = versions[0] if versions else None
        html = (version.html or "") if version is not None else ""
        if html.strip():
            html = self._strip_site_css(html)
            css_href = "assets/site.css" if page.slug == "index" else "../assets/site.css"
            return ensure_css_link(html, css_href)

        dist_html = self._read_dist_page_html(page.session_id, page.slug)
        if dist_html is not None:
            return dist_html
        return ""

    def _read_dist_page_html(self, session_id: str, slug: str) -> Optional[str]:
        dist_dir = self._resolve_dist_dir(session_id)
        if dist_dir is None:
            return None

        candidates: list[Path] = []
        if slug == "index":
            candidates.append(dist_dir / "index.html")
        else:
            candidates.append(dist_dir / "pages" / slug / "index.html")
            candidates.append(dist_dir / "pages" / f"{slug}.html")

        for candidate in candidates:
            try:
                resolved = candidate.resolve()
            except OSError:
                continue
            if resolved != dist_dir and dist_dir not in resolved.parents:
                continue
            if not resolved.is_file():
                continue
            try:
                return resolved.read_text(encoding="utf-8")
            except OSError:
                continue

        return None

    def _resolve_dist_dir(self, session_id: str) -> Optional[Path]:
        metadata = StateStoreService(self.db).get_metadata(session_id)
        candidate: Optional[Path] = None
        artifacts = metadata.build_artifacts if metadata is not None else None
        if isinstance(artifacts, dict):
            dist_path = artifacts.get("dist_path")
            if isinstance(dist_path, str) and dist_path.strip():
                candidate = Path(dist_path).expanduser()

        if candidate is None:
            candidate = Path("~/.instant-coffee/sessions").expanduser() / session_id / "dist"

        try:
            resolved = candidate.resolve()
        except OSError:
            return None

        if not resolved.is_dir():
            return None
        return resolved

    def _get_legacy_index_html(self, session_id: str) -> Optional[str]:
        session = self.db.get(SessionModel, session_id)
        if session is None:
            return None
        version_service = VersionService(self.db)
        version = None
        if session.current_version is not None:
            version = version_service.get_version(session_id, session.current_version)
        if version is None:
            versions = version_service.get_versions(session_id, limit=1)
            version = versions[0] if versions else None
        return version.html if version is not None else None

    def _build_site_css(self, session_id: str) -> str:
        raw_style, design_direction = self._get_style_inputs(session_id)
        return build_site_css(raw_style, design_direction)

    def _strip_site_css(self, html: str) -> str:
        if not html:
            return html
        pattern = re.compile(
            r"<style[^>]*>.*?Site-wide Design System.*?</style>",
            re.IGNORECASE | re.DOTALL,
        )
        return pattern.sub("", html, count=1)

    def _get_style_inputs(self, session_id: str) -> Tuple[dict, dict]:
        product_doc = self._product_doc_service.get_by_session_id(session_id)
        structured = product_doc.structured if product_doc and isinstance(product_doc.structured, dict) else {}

        design_direction = structured.get("design_direction") or structured.get("designDirection") or {}
        if not isinstance(design_direction, dict):
            design_direction = {}

        raw_style = structured.get("global_style") or structured.get("globalStyle") or {}
        if not isinstance(raw_style, dict):
            raw_style = {}

        return raw_style, design_direction


__all__ = ["FileContent", "FileTreeService"]
