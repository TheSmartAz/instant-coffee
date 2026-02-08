from __future__ import annotations

import json
import logging
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Sequence

from sqlalchemy.orm import Session as DbSession

from ..config import get_settings
from ..db.models import Page, ProductDocStatus, Session as SessionModel
from ..services.data_protocol import DataProtocolGenerator
from ..services.filesystem import FilesystemService
from ..services.page import PageService
from ..services.page_version import PageVersionService
from ..services.product_doc import ProductDocService
from ..services.version import VersionService
from ..services.mobile_shell import ensure_mobile_shell
from ..utils.html import ensure_css_link, rewrite_internal_links_for_export, strip_prompt_artifacts
from ..utils.style import build_site_css, normalize_global_style

logger = logging.getLogger(__name__)

_FLOW_PRODUCT_TYPES = {"ecommerce", "travel", "manual", "kanban", "booking", "dashboard"}
_STATIC_PRODUCT_TYPES = {"landing", "card", "invitation"}


@dataclass
class PageExportInfo:
    slug: str
    title: str
    path: Optional[str]
    status: str
    size: Optional[int] = None
    version: Optional[int] = None
    error: Optional[str] = None


@dataclass
class ExportResult:
    export_dir: Path
    manifest: dict
    success: bool
    errors: List[str]


class ExportService:
    _SITE_CSS_BLOCK_RE = re.compile(
        r"<style[^>]*>.*?Site-wide Design System.*?</style>",
        re.IGNORECASE | re.DOTALL,
    )

    def __init__(self, db: DbSession) -> None:
        self.db = db
        self._page_service = PageService(db)
        self._page_version_service = PageVersionService(db)
        self._product_doc_service = ProductDocService(db)
        self._version_service = VersionService(db)

    async def export_session(
        self,
        session_id: str,
        output_dir: Path | str | None = None,
        *,
        page_order: Optional[Sequence[dict]] = None,
        global_style: Optional[dict] = None,
        include_product_doc: bool = True,
    ) -> ExportResult:
        session = self.db.get(SessionModel, session_id)
        if session is None:
            raise ValueError("Session not found")

        settings = get_settings()
        resolved_dir = Path(output_dir or settings.output_dir)
        fs = FilesystemService(str(resolved_dir))
        export_dir = fs.create_session_directory(session_id)
        source_dir = Path(settings.output_dir) / session_id

        product_doc = self._product_doc_service.get_by_session_id(session_id)
        resolved_global_style, design_direction = self._resolve_style_inputs(
            product_doc,
            global_style,
        )

        pages = self._page_service.list_by_session(session_id)
        if not pages:
            return self._export_legacy(
                session=session,
                export_dir=export_dir,
                resolved_global_style=resolved_global_style,
                design_direction=design_direction,
                product_doc=product_doc,
                include_product_doc=include_product_doc,
            )

        ordered_pages = self._order_pages(pages, page_order)
        all_pages = [page.slug for page in ordered_pages]
        page_exports: List[PageExportInfo] = []
        errors: List[str] = []

        for page in ordered_pages:
            relative_path = "index.html" if page.slug == "index" else f"pages/{page.slug}.html"
            output_path = export_dir / relative_path
            css_path = "assets/site.css" if page.slug == "index" else "../assets/site.css"
            info = await self.export_page(
                page,
                output_path,
                css_path,
                relative_path=relative_path,
                all_pages=all_pages,
            )
            if info.status != "success" and info.error:
                errors.append(f"{page.slug}: {info.error}")
            page_exports.append(info)

        exported_success = [info for info in page_exports if info.status == "success"]
        if not exported_success:
            raise ValueError("No page versions to export")

        assets = self._write_assets(
            export_dir=export_dir,
            resolved_global_style=resolved_global_style,
            design_direction=design_direction,
        )
        assets.extend(self._copy_components(export_dir=export_dir, source_dir=source_dir))
        assets.extend(self._write_data_protocol_assets(export_dir, session, product_doc))

        product_doc_included = self._write_product_doc(
            export_dir=export_dir,
            product_doc=product_doc,
            include_product_doc=include_product_doc,
        )

        exported_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        manifest = self.generate_manifest(
            session_id=session_id,
            pages=page_exports,
            product_doc_status=self._product_doc_status(product_doc),
            exported_at=exported_at,
            assets=assets,
            global_style=self._summarize_global_style(resolved_global_style, design_direction),
            product_doc_included=product_doc_included,
        )

        manifest_path = export_dir / "export_manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

        return ExportResult(
            export_dir=export_dir,
            manifest=manifest,
            success=True,
            errors=errors,
        )

    async def export_page(
        self,
        page: Page,
        output_path: Path,
        css_path: str,
        *,
        relative_path: str,
        all_pages: Sequence[str],
    ) -> PageExportInfo:
        version = self._get_page_version(page)
        if version is None:
            return PageExportInfo(
                slug=page.slug,
                title=page.title,
                path=None,
                status="failed",
                error="missing_page_version",
            )

        html = version.html or ""
        html = strip_prompt_artifacts(html)
        html = self._strip_site_css(html)
        html, link_warnings = rewrite_internal_links_for_export(
            html,
            current_slug=page.slug,
            all_pages=all_pages,
        )
        if link_warnings:
            logger.warning(
                "ExportService detected broken internal links for %s: %s",
                page.slug,
                ", ".join(link_warnings),
            )
        html = ensure_css_link(html, css_path)
        html = ensure_mobile_shell(html)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")
        size = output_path.stat().st_size

        return PageExportInfo(
            slug=page.slug,
            title=page.title,
            path=relative_path,
            status="success",
            size=size,
            version=version.version,
        )

    def generate_manifest(
        self,
        session_id: str,
        pages: List[PageExportInfo],
        product_doc_status: str | None,
        *,
        exported_at: str,
        assets: Optional[List[dict]] = None,
        global_style: Optional[dict] = None,
        product_doc_included: bool = False,
    ) -> dict:
        return {
            "version": "1.0",
            "exported_at": exported_at,
            "session_id": session_id,
            "product_doc": {
                "status": product_doc_status,
                "included": product_doc_included,
            },
            "pages": [self._serialize_page(info) for info in pages],
            "assets": assets or [],
            "global_style": global_style or {},
        }

    def _export_legacy(
        self,
        *,
        session: SessionModel,
        export_dir: Path,
        resolved_global_style: dict,
        design_direction: dict,
        product_doc,
        include_product_doc: bool,
    ) -> ExportResult:
        version = None
        if session.current_version is not None:
            version = self._version_service.get_version(session.id, session.current_version)
        if version is None:
            versions = self._version_service.get_versions(session.id, limit=1)
            version = versions[0] if versions else None
        if version is None:
            raise ValueError("No version to export")

        html = version.html or ""
        html = self._strip_site_css(html)
        html = ensure_css_link(html, "assets/site.css")
        html = ensure_mobile_shell(html)

        output_path = export_dir / "index.html"
        output_path.write_text(html, encoding="utf-8")
        size = output_path.stat().st_size

        assets = self._write_assets(
            export_dir=export_dir,
            resolved_global_style=resolved_global_style,
            design_direction=design_direction,
        )
        settings = get_settings()
        source_dir = Path(settings.output_dir) / session.id
        assets.extend(self._copy_components(export_dir=export_dir, source_dir=source_dir))
        assets.extend(self._write_data_protocol_assets(export_dir, session, product_doc))

        product_doc_included = self._write_product_doc(
            export_dir=export_dir,
            product_doc=product_doc,
            include_product_doc=include_product_doc,
        )

        page_info = PageExportInfo(
            slug="index",
            title=session.title or "Index",
            path="index.html",
            status="success",
            size=size,
            version=version.version,
        )

        exported_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        manifest = self.generate_manifest(
            session_id=session.id,
            pages=[page_info],
            product_doc_status=self._product_doc_status(product_doc),
            exported_at=exported_at,
            assets=assets,
            global_style=self._summarize_global_style(resolved_global_style, design_direction),
            product_doc_included=product_doc_included,
        )

        manifest_path = export_dir / "export_manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

        return ExportResult(
            export_dir=export_dir,
            manifest=manifest,
            success=True,
            errors=[],
        )

    def _write_assets(
        self,
        *,
        export_dir: Path,
        resolved_global_style: dict,
        design_direction: dict,
    ) -> List[dict]:
        assets_dir = export_dir / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        site_css = build_site_css(resolved_global_style, design_direction)
        site_css_path = assets_dir / "site.css"
        site_css_path.write_text(site_css, encoding="utf-8")
        return [
            {
                "path": "assets/site.css",
                "size": site_css_path.stat().st_size,
            }
        ]

    def _copy_components(self, *, export_dir: Path, source_dir: Path) -> List[dict]:
        src_components = source_dir / "components"
        if not src_components.exists():
            return []
        dest_components = export_dir / "components"
        try:
            if source_dir.resolve() != export_dir.resolve():
                shutil.copytree(src_components, dest_components, dirs_exist_ok=True)
        except Exception:
            logger.exception("Failed to copy components directory")
            return []
        if not dest_components.exists():
            return []
        assets: List[dict] = []
        for path in dest_components.rglob("*"):
            if not path.is_file():
                continue
            try:
                rel_path = path.relative_to(export_dir).as_posix()
            except ValueError:
                rel_path = f"components/{path.name}"
            assets.append(
                {
                    "path": rel_path,
                    "size": path.stat().st_size,
                }
            )
        return assets

    def _write_data_protocol_assets(
        self,
        export_dir: Path,
        session: SessionModel,
        product_doc,
    ) -> List[dict]:
        product_type = self._resolve_product_type(product_doc, session)
        if product_type not in _FLOW_PRODUCT_TYPES and product_type not in _STATIC_PRODUCT_TYPES:
            return []
        generator = DataProtocolGenerator(
            output_dir=str(export_dir.parent),
            session_id=session.id,
            db=self.db,
        )
        contract = generator.generate_state_contract(product_type, skill_id=session.skill_id)
        include_client = product_type in _FLOW_PRODUCT_TYPES
        assets = generator.write_shared_assets(product_type, contract, include_client=include_client)
        output = [
            {
                "path": "shared/state-contract.json",
                "size": assets.contract_path.stat().st_size,
            },
            {
                "path": "shared/data-store.js",
                "size": assets.data_store_path.stat().st_size,
            },
        ]
        if assets.data_client_path is not None:
            output.append(
                {
                    "path": "shared/data-client.js",
                    "size": assets.data_client_path.stat().st_size,
                }
            )
        return output

    def _write_product_doc(
        self,
        *,
        export_dir: Path,
        product_doc,
        include_product_doc: bool,
    ) -> bool:
        if not include_product_doc or product_doc is None:
            return False
        (export_dir / "product-doc.md").write_text(product_doc.content or "", encoding="utf-8")
        return True

    def _strip_site_css(self, html: str) -> str:
        if not html:
            return html
        return self._SITE_CSS_BLOCK_RE.sub("", html, count=1)

    def _get_page_version(self, page: Page):
        version = self._page_version_service.get_current(page.id)
        if version is None:
            versions = self._page_version_service.list_by_page(page.id)
            version = versions[0] if versions else None
        return version

    def _order_pages(self, pages: List[Page], order: Optional[Sequence[dict]]) -> List[Page]:
        if not order:
            return pages
        page_lookup = {page.id: page for page in pages}
        slug_lookup = {page.slug: page for page in pages}
        ordered: List[Page] = []
        for item in order:
            if not isinstance(item, dict):
                continue
            page_id = item.get("page_id")
            slug = item.get("slug")
            if page_id in page_lookup and page_lookup[page_id] not in ordered:
                ordered.append(page_lookup[page_id])
                continue
            if slug in slug_lookup and slug_lookup[slug] not in ordered:
                ordered.append(slug_lookup[slug])
        for page in pages:
            if page not in ordered:
                ordered.append(page)
        return ordered

    def _resolve_product_type(self, product_doc, session: SessionModel) -> str:
        if product_doc is not None and isinstance(getattr(product_doc, "structured", None), dict):
            value = product_doc.structured.get("product_type") or product_doc.structured.get("productType")
            if value:
                return str(value).strip().lower()
        if session and session.product_type:
            return str(session.product_type).strip().lower()
        return "unknown"

    def _resolve_style_inputs(self, product_doc, global_style: Optional[dict]) -> tuple[dict, dict]:
        structured = {}
        if product_doc is not None and isinstance(product_doc.structured, dict):
            structured = product_doc.structured

        design_direction = structured.get("design_direction") or structured.get("designDirection") or {}
        if not isinstance(design_direction, dict):
            design_direction = {}

        resolved_global_style = global_style
        if not isinstance(resolved_global_style, dict):
            resolved_global_style = structured.get("global_style") or structured.get("globalStyle") or {}
        if not isinstance(resolved_global_style, dict):
            resolved_global_style = {}

        return resolved_global_style, design_direction

    def _summarize_global_style(self, global_style: dict, design_direction: dict) -> dict:
        resolved = normalize_global_style(global_style, design_direction)
        summary: dict = {}
        for key in ("primary_color", "secondary_color", "font_family"):
            value = resolved.get(key)
            if value:
                summary[key] = value
        return summary

    def _product_doc_status(self, product_doc) -> Optional[str]:
        if product_doc is None:
            return None
        status = product_doc.status
        if isinstance(status, ProductDocStatus):
            return status.value
        return str(status)

    def _serialize_page(self, info: PageExportInfo) -> dict:
        payload = {
            "slug": info.slug,
            "title": info.title,
            "status": info.status,
        }
        if info.path:
            payload["path"] = info.path
        if info.size is not None:
            payload["size"] = info.size
        if info.version is not None:
            payload["version"] = info.version
        if info.error:
            payload["error"] = info.error
        return payload


__all__ = ["ExportResult", "ExportService", "PageExportInfo"]
