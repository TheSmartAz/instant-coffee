from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, List, Optional

from .base import BaseAgent
from .prompts import get_sitemap_prompt
from ..events.models import SitemapProposedEvent
from ..llm.model_pool import ModelRole
from ..schemas.sitemap import GlobalStyle, NavItem, SitemapPage, SitemapResult as SitemapSchema
from ..utils.style import build_global_style, normalize_hex_color
from ..utils.product_doc import extract_pages_from_markdown


@dataclass
class SitemapResult:
    pages: List[SitemapPage]
    nav: List[NavItem]
    global_style: GlobalStyle
    tokens_used: int = 0

    def to_dict(self) -> dict:
        return {
            "pages": [page.model_dump() if hasattr(page, "model_dump") else page.dict() for page in self.pages],
            "nav": [item.model_dump() if hasattr(item, "model_dump") else item.dict() for item in self.nav],
            "global_style": self.global_style.model_dump()
            if hasattr(self.global_style, "model_dump")
            else self.global_style.dict(),
            "tokens_used": self.tokens_used,
        }


class SitemapAgent(BaseAgent):
    agent_type = "sitemap"

    def __init__(self, db, session_id: str, settings, event_emitter=None, agent_id=None, task_id=None) -> None:
        super().__init__(
            db,
            session_id,
            settings,
            event_emitter=event_emitter,
            agent_id=agent_id,
            task_id=task_id,
            model_role=ModelRole.EXPANDER,
        )
        self.system_prompt = get_sitemap_prompt()

    async def generate(
        self,
        product_doc: Any,
        multi_page: bool = True,
        explicit_multi_page: bool = False,
    ) -> SitemapResult:
        structured = _coerce_structured(product_doc)
        structured = _merge_structured_pages(structured, product_doc)
        design_direction = _extract_design_direction(structured)

        messages = self._build_messages(structured=structured, multi_page=multi_page)
        response = await self._call_llm(
            messages=messages,
            agent_type=self.agent_type,
            temperature=self.settings.temperature,
            context="sitemap",
        )

        tokens_used = response.token_usage.total_tokens if response.token_usage else 0
        payload = self._parse_response(response.content or "")
        normalized = self._normalize_payload(
            payload=payload,
            structured=structured,
            design_direction=design_direction,
            multi_page=multi_page,
            explicit_multi_page=explicit_multi_page,
        )

        sitemap = self._validate_sitemap(normalized)
        if sitemap is None:
            sitemap = self._build_fallback(structured, design_direction, multi_page, explicit_multi_page)

        if self.event_emitter:
            self.event_emitter.emit(
                SitemapProposedEvent(
                    pages_count=len(sitemap.pages),
                    sitemap=sitemap.model_dump() if hasattr(sitemap, "model_dump") else sitemap.dict(),
                )
            )

        return SitemapResult(
            pages=list(sitemap.pages),
            nav=list(sitemap.nav),
            global_style=sitemap.global_style,
            tokens_used=tokens_used,
        )

    def _build_messages(self, *, structured: dict, multi_page: bool) -> List[dict]:
        messages: List[dict] = [{"role": "system", "content": self.system_prompt}]
        payload = {
            "multi_page": multi_page,
            "structured": structured,
        }
        user_message = "Create a sitemap for the following ProductDoc structured JSON:\n" + json.dumps(
            payload, ensure_ascii=False
        )
        messages.append({"role": "user", "content": user_message})
        return messages

    def _parse_response(self, content: str) -> Optional[dict]:
        text = (content or "").strip()
        if not text:
            return None
        try:
            payload = json.loads(text)
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError:
            pass

        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                payload = json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return None
            if isinstance(payload, dict):
                return payload
        return None

    def _normalize_payload(
        self,
        *,
        payload: Optional[dict],
        structured: dict,
        design_direction: dict,
        multi_page: bool,
        explicit_multi_page: bool = False,
    ) -> dict:
        payload = payload or {}
        pages_payload = payload.get("pages") if isinstance(payload.get("pages"), list) else None
        if pages_payload is None:
            pages_payload = structured.get("pages") if isinstance(structured.get("pages"), list) else []

        pages = self._normalize_pages(pages_payload, structured, multi_page, explicit_multi_page)
        nav_payload = payload.get("nav") if isinstance(payload.get("nav"), list) else None
        nav = self._normalize_nav(pages, nav_payload)
        global_style = self._normalize_global_style(payload, design_direction)

        return {"pages": pages, "nav": nav, "global_style": global_style}

    def _normalize_pages(
        self,
        pages_payload: List[Any],
        structured: dict,
        multi_page: bool,
        explicit_multi_page: bool = False,
    ) -> List[dict]:
        normalized: List[dict] = []
        for idx, raw_page in enumerate(pages_payload):
            if not isinstance(raw_page, dict):
                continue
            page = _normalize_page(raw_page, index=idx)
            if page:
                normalized.append(page)

        if not normalized:
            normalized = _fallback_pages(structured)

        normalized = _ensure_index_page(normalized, structured)

        if not multi_page:
            normalized = [page for page in normalized if page.get("slug") == "index"]
            if not normalized:
                normalized = _fallback_pages(structured, single_only=True)

        if explicit_multi_page:
            normalized = _ensure_minimum_pages(normalized, structured)

        normalized = _dedupe_pages(normalized)
        if len(normalized) > 8:
            normalized = normalized[:8]
        return normalized

    def _normalize_nav(self, pages: List[dict], nav_payload: Optional[List[Any]]) -> List[dict]:
        label_map: dict[str, str] = {}
        if isinstance(nav_payload, list):
            for item in nav_payload:
                if not isinstance(item, dict):
                    continue
                slug = str(item.get("slug") or "")
                label = str(item.get("label") or "")
                if slug and label:
                    label_map[slug] = label

        nav: List[dict] = []
        for idx, page in enumerate(pages):
            slug = page.get("slug") or ""
            label = label_map.get(slug) or page.get("title") or slug
            nav.append({"slug": slug, "label": label, "order": idx})
        return nav

    def _normalize_global_style(self, payload: dict, design_direction: dict) -> dict:
        default_style = build_global_style(design_direction)
        raw_style = payload.get("global_style") or payload.get("globalStyle") or {}
        if not isinstance(raw_style, dict):
            raw_style = {}

        primary_color = normalize_hex_color(
            raw_style.get("primary_color") or raw_style.get("primaryColor"),
            default_style.get("primary_color"),
        )
        secondary_input = raw_style.get("secondary_color") or raw_style.get("secondaryColor")
        secondary_color = normalize_hex_color(secondary_input, default_style.get("secondary_color"))

        font_family = raw_style.get("font_family") or raw_style.get("fontFamily") or default_style.get(
            "font_family"
        )

        return {
            "primary_color": primary_color,
            "secondary_color": secondary_color,
            "font_family": str(font_family),
            "font_size_base": str(raw_style.get("font_size_base") or raw_style.get("fontSizeBase") or "16px"),
            "font_size_heading": str(
                raw_style.get("font_size_heading") or raw_style.get("fontSizeHeading") or "24px"
            ),
            "button_height": str(raw_style.get("button_height") or raw_style.get("buttonHeight") or "44px"),
            "spacing_unit": str(raw_style.get("spacing_unit") or raw_style.get("spacingUnit") or "8px"),
            "border_radius": str(raw_style.get("border_radius") or raw_style.get("borderRadius") or "8px"),
        }

    def _validate_sitemap(self, payload: dict) -> Optional[SitemapSchema]:
        try:
            if hasattr(SitemapSchema, "model_validate"):
                return SitemapSchema.model_validate(payload)
            return SitemapSchema.parse_obj(payload)
        except Exception:
            return None

    def _build_fallback(
        self,
        structured: dict,
        design_direction: dict,
        multi_page: bool,
        explicit_multi_page: bool,
    ) -> SitemapSchema:
        pages = _fallback_pages(structured)
        pages = _ensure_index_page(pages, structured)
        if not multi_page:
            pages = [page for page in pages if page.get("slug") == "index"]
        if explicit_multi_page:
            pages = _ensure_minimum_pages(pages, structured)
        nav = self._normalize_nav(pages, None)
        global_style = self._normalize_global_style({}, design_direction)
        payload = {"pages": pages[:8], "nav": nav, "global_style": global_style}
        if hasattr(SitemapSchema, "model_validate"):
            return SitemapSchema.model_validate(payload)
        return SitemapSchema.parse_obj(payload)


def _coerce_structured(product_doc: Any) -> dict:
    structured = getattr(product_doc, "structured", None)
    if not isinstance(structured, dict):
        return {}
    return structured


def _merge_structured_pages(structured: dict, product_doc: Any) -> dict:
    if not isinstance(structured, dict):
        structured = {}

    existing_pages = structured.get("pages")
    if isinstance(existing_pages, list) and len(existing_pages) > 1:
        return structured

    content = getattr(product_doc, "content", "") if product_doc is not None else ""
    derived_pages = extract_pages_from_markdown(content or "")
    if not derived_pages:
        return structured

    merged = dict(structured)
    merged["pages"] = derived_pages
    return merged


def _extract_design_direction(structured: dict) -> dict:
    if not isinstance(structured, dict):
        return {}
    return structured.get("design_direction") or structured.get("designDirection") or {}


def _fallback_pages(structured: dict, single_only: bool = False) -> List[dict]:
    description = structured.get("description") or ""
    title = structured.get("project_name") or structured.get("projectName") or "Home"
    index_page = {
        "title": str(title),
        "slug": "index",
        "purpose": str(description or "Primary landing page"),
        "sections": ["hero", "features", "cta"],
        "required": True,
    }
    if single_only:
        return [index_page]

    features = structured.get("features") or []
    feature_sections = []
    if isinstance(features, list):
        for feature in features:
            if isinstance(feature, dict):
                name = feature.get("name")
                if name:
                    feature_sections.append(str(name))
    if feature_sections:
        index_page["sections"] = feature_sections[:6]

    return [index_page]


def _normalize_page(raw_page: dict, *, index: int) -> Optional[dict]:
    title = str(raw_page.get("title") or raw_page.get("name") or f"Page {index + 1}")
    slug = raw_page.get("slug") or title
    slug = _slugify(str(slug))
    if not slug:
        slug = f"page-{index + 1}"
    purpose = str(raw_page.get("purpose") or raw_page.get("description") or "")
    sections = raw_page.get("sections") or []
    if not isinstance(sections, list):
        sections = []
    sections = [str(section) for section in sections if section]
    if not sections:
        sections = _default_sections(slug)
    required = bool(raw_page.get("required", False))

    return {
        "title": title,
        "slug": slug,
        "purpose": purpose or "",
        "sections": sections,
        "required": required,
    }


def _ensure_index_page(pages: List[dict], structured: dict) -> List[dict]:
    has_index = any(page.get("slug") == "index" for page in pages)
    if has_index:
        return _ensure_index_required(pages)

    fallback_index = _fallback_pages(structured, single_only=True)[0]
    return [fallback_index] + pages


def _ensure_minimum_pages(pages: List[dict], structured: dict) -> List[dict]:
    if len(pages) >= 2:
        return pages
    existing_slugs = {page.get("slug") for page in pages if page.get("slug")}
    candidates = [
        ("about", "About", "Story and team"),
        ("services", "Services", "Offerings and pricing"),
        ("features", "Features", "Key capabilities"),
        ("contact", "Contact", "How to reach us"),
    ]
    for slug, title, purpose in candidates:
        if slug in existing_slugs:
            continue
        pages.append(
            {
                "title": title,
                "slug": slug,
                "purpose": purpose,
                "sections": _default_sections(slug),
                "required": False,
            }
        )
        break
    return pages


def _ensure_index_required(pages: List[dict]) -> List[dict]:
    for page in pages:
        if page.get("slug") == "index":
            page["required"] = True
    return pages


def _dedupe_pages(pages: List[dict]) -> List[dict]:
    seen = set()
    deduped = []
    for page in pages:
        slug = page.get("slug")
        if not slug or slug in seen:
            continue
        seen.add(slug)
        deduped.append(page)
    return deduped


def _slugify(text: str) -> str:
    value = text.strip().lower()
    value = re.sub(r"[^a-z0-9-]+", "-", value)
    value = re.sub(r"-+", "-", value)
    value = value.strip("-")
    return value[:40].rstrip("-")


def _default_sections(slug: str) -> List[str]:
    if slug in {"index", "home"}:
        return ["hero", "features", "cta"]
    if "about" in slug:
        return ["story", "values", "team"]
    if "pricing" in slug:
        return ["plans", "faq", "cta"]
    if "contact" in slug:
        return ["contact-form", "details"]
    if "blog" in slug:
        return ["posts", "categories", "cta"]
    return ["content"]


__all__ = ["SitemapAgent", "SitemapResult"]
