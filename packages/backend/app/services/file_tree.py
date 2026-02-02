from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple
from urllib.parse import unquote

from sqlalchemy.orm import Session as DbSession

from ..db.models import Page, Session as SessionModel
from ..schemas.files import FileTreeNode
from ..services.page import PageService
from ..services.page_version import PageVersionService
from ..services.product_doc import ProductDocService
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

        index_html = ""
        if index_page is not None:
            index_html = self._get_page_html(index_page)
        else:
            legacy_html = self._get_legacy_index_html(session_id)
            if legacy_html is not None:
                index_html = legacy_html

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
        else:
            return None

        content = content or ""
        return FileContent(
            path=resolved_path,
            content=content,
            language=_get_language(resolved_path),
            size=_content_size(content),
        )

    def _resolve_index_html(self, session_id: str) -> str:
        page = self._page_service.get_by_slug(session_id, "index")
        if page is not None:
            return self._get_page_html(page)
        legacy_html = self._get_legacy_index_html(session_id)
        return legacy_html or ""

    def _get_page_html(self, page: Page) -> str:
        version = self._page_version_service.get_current(page.id)
        if version is None:
            versions = self._page_version_service.list_by_page(page.id)
            version = versions[0] if versions else None
        if version is None:
            return ""
        html = version.html or ""
        html = self._strip_site_css(html)
        css_href = "assets/site.css" if page.slug == "index" else "../assets/site.css"
        return ensure_css_link(html, css_href)

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
