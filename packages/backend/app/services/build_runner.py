from __future__ import annotations

import logging
from pathlib import Path
from datetime import datetime, timezone
from threading import Event
from typing import Any

from sqlalchemy.orm import Session as DbSession

from ..config import get_settings
from ..renderer.builder import BuildError, ReactSSGBuilder
from ..renderer.html_to_react import PageHtml
from ..schemas.session_metadata import BuildInfo, BuildStatus
from .build_payload import generate_node
from .component_registry import ComponentRegistryService
from .page import PageService
from .product_doc import ProductDocService
from .state_store import StateStoreService

logger = logging.getLogger(__name__)


_FALLBACK_COMPONENT_IDS = [
    "nav-primary",
    "nav-bottom",
    "hero-banner",
    "section-header",
    "list-grid",
    "list-simple",
    "footer-simple",
    "button-primary",
    "button-secondary",
]


def _extract_build_payload(state: Any) -> dict[str, Any]:
    if not isinstance(state, dict):
        return {}
    return {
        "page_schemas": state.get("page_schemas") or [],
        "component_registry": state.get("component_registry") or {},
        "style_tokens": state.get("style_tokens") or {},
        "assets": state.get("assets"),
    }


def _ensure_component_registry(registry: Any) -> dict[str, Any]:
    if isinstance(registry, dict):
        components = registry.get("components")
        if isinstance(components, list) and components:
            return registry
    return {"components": [{"id": item} for item in _FALLBACK_COMPONENT_IDS]}


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

    async def _build(self, session_id: str, state: dict[str, Any] | None) -> dict[str, Any]:
        workspace_source = self._resolve_workspace_source(session_id)
        builder = ReactSSGBuilder(
            session_id,
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

        pages_html = self._fetch_pages_html(session_id)
        if pages_html:
            result = await builder.build_from_html(
                pages=pages_html,
                product_doc_content=self._fetch_product_doc(session_id),
            )
            result["source_mode"] = "html"
            return result

        payload = _extract_build_payload(state)
        if not payload.get("page_schemas"):
            payload = await self._fallback_build_payload(session_id, state)
            if not payload.get("page_schemas"):
                raise BuildError("No page schemas or HTML pages available for build", stage="payload")
            merged_state = dict(state or {})
            merged_state.update(
                {
                    "page_schemas": payload.get("page_schemas") or [],
                    "component_registry": payload.get("component_registry") or {},
                    "style_tokens": payload.get("style_tokens") or {},
                    "assets": payload.get("assets"),
                }
            )
            StateStoreService(self.db).update_metadata(session_id, {"graph_state": merged_state})

        result = await builder.build(
            page_schemas=payload.get("page_schemas") or [],
            component_registry=payload.get("component_registry") or {},
            style_tokens=payload.get("style_tokens") or {},
            assets=payload.get("assets"),
        )
        result["source_mode"] = "schema"
        return result

    def _resolve_workspace_source(self, session_id: str) -> Path | None:
        workspace = (Path(get_settings().output_dir).expanduser() / session_id).resolve()
        src_dir = workspace / "src"
        if not src_dir.is_dir():
            return None
        if (src_dir / "App.tsx").is_file() or any((src_dir / "pages").glob("*.tsx")):
            return workspace
        return None

    def _workspace_page_hints(self, session_id: str) -> list[dict[str, str]]:
        pages = PageService(self.db).list_by_session(session_id)
        return [{"slug": page.slug, "title": page.title} for page in pages] or [
            {"slug": "index", "title": "Index"}
        ]

    def _fetch_pages_html(self, session_id: str) -> list[PageHtml]:
        pages = PageService(self.db).list_by_session(session_id)
        result: list[PageHtml] = []
        for page in pages:
            html: str | None = None
            if page.current_version and hasattr(page.current_version, "html"):
                html = page.current_version.html
            if not html and page.versions:
                latest = sorted(page.versions, key=lambda item: item.version, reverse=True)
                for version in latest:
                    if version.html:
                        html = version.html
                        break
            if html:
                result.append(PageHtml(slug=page.slug, title=page.title, html=html))
        return result

    def _fetch_product_doc(self, session_id: str) -> str | None:
        doc = ProductDocService(self.db).get_by_session_id(session_id)
        if doc and doc.content:
            return doc.content
        return None

    async def _fallback_build_payload(
        self,
        session_id: str,
        state: dict[str, Any] | None,
    ) -> dict[str, Any]:
        state = state if isinstance(state, dict) else {}
        product_doc = ProductDocService(self.db).get_by_session_id(session_id)
        structured = product_doc.structured if product_doc and isinstance(product_doc.structured, dict) else None

        component_registry = state.get("component_registry")
        if not isinstance(component_registry, dict) or not component_registry:
            component_registry = self._load_component_registry(session_id)
        component_registry = _ensure_component_registry(component_registry)

        fallback_state: dict[str, Any] = {
            **state,
            "session_id": session_id,
            "component_registry": component_registry,
            "pages": self._resolve_pages_payload(session_id, structured),
        }
        if structured:
            fallback_state["product_doc"] = {"structured": structured}

        try:
            updated_state = await generate_node(fallback_state)
        except BuildError as exc:
            logger.exception("Fallback build payload generation failed for session %s", session_id)
            raise BuildError(
                f"Fallback build payload generation failed: {exc}",
                stage=exc.stage or "fallback_generate_payload",
                stdout=exc.stdout,
                stderr=exc.stderr,
            ) from exc
        except Exception as exc:
            logger.exception("Fallback build payload generation failed for session %s", session_id)
            raise BuildError(
                f"Fallback build payload generation failed: {exc}",
                stage="fallback_generate_payload",
            ) from exc

        payload = _extract_build_payload(updated_state)
        payload["component_registry"] = _ensure_component_registry(
            payload.get("component_registry") or component_registry
        )
        return payload

    def _load_component_registry(self, session_id: str) -> dict[str, Any]:
        settings = get_settings()
        try:
            service = ComponentRegistryService(settings.output_dir, session_id)
            registry = service.read_registry()
            if isinstance(registry, dict):
                return registry
        except Exception:
            logger.exception("Failed to read component registry for session %s", session_id)
        return {}

    def _resolve_pages_payload(
        self,
        session_id: str,
        structured: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        if structured and isinstance(structured.get("pages"), list):
            pages = [page for page in structured["pages"] if isinstance(page, dict)]
            if pages:
                return pages
        pages = PageService(self.db).list_by_session(session_id)
        return [
            {
                "slug": page.slug,
                "title": page.title,
                "role": "general",
            }
            for page in pages
        ]


__all__ = ["BuildRunner"]
