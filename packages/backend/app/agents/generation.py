from __future__ import annotations

import html as html_lib
import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, List, Optional, Sequence

from .base import BaseAgent
from .prompts import get_generation_prompt, get_generation_prompt_multipage
from .style_refiner import StyleRefiner
from ..llm.model_pool import ModelRole
from ..llm.tool_handlers import MAX_WRITE_BYTES
from ..llm.tools import get_filesystem_tools
from ..schemas.sitemap import GlobalStyle, NavItem, SitemapPage
from ..services.app_data_store import get_app_data_store
from ..services.component_registry import ComponentRegistryService
from ..services.data_protocol import DataProtocolGenerator
from ..services.filesystem import FilesystemService
from ..services.page_version import PageVersionService
from ..utils.component_assembler import assemble_components
from ..utils.html import (
    build_nav_html,
    ensure_css_link,
    inline_css,
    ensure_dom_ids,
    normalize_internal_links,
    strip_prompt_artifacts,
)
from ..utils.guardrails import guardrails_to_prompt
from ..utils.style import build_global_style_css, build_site_css
from ..generators.mobile_html import build_fallback_excerpt
from ..exceptions import HTMLExtractionError, new_trace_id

logger = logging.getLogger(__name__)

ALLOWED_ENCODINGS = {"utf-8", "gbk"}
ALLOWED_WRITE_EXTENSIONS = {".html"}
MAX_HTML_RETRIES = 3
STRICT_RETRY_TEMPERATURE = 0.2
STRICT_HTML_RETRY_INSTRUCTIONS = (
    "Your last response did not include a complete HTML document. "
    "Return ONLY a complete HTML document that starts with <!doctype html> "
    "and includes <html>, <head>, and <body> tags. "
    "Do not include markdown, code fences, or explanations. "
    "Wrap the HTML in <HTML_OUTPUT>...</HTML_OUTPUT>."
)

_STYLE_TAG_RE = re.compile(r"<style\b[^>]*>(.*?)</style>", re.IGNORECASE | re.DOTALL)


@dataclass
class GenerationProgress:
    message: str
    progress: int


@dataclass
class GenerationResult:
    html: str
    preview_url: str
    filepath: str
    token_usage: Optional[dict] = None
    page_id: Optional[str] = None
    version: Optional[int] = None
    warnings: List[str] = field(default_factory=list)
    fallback_used: bool = False
    fallback_excerpt: Optional[str] = None


class GenerationAgent(BaseAgent):
    agent_type = "generation"

    def __init__(
        self,
        db,
        session_id: str,
        settings,
        event_emitter=None,
        agent_id=None,
        task_id=None,
        emit_lifecycle_events: bool = True,
    ) -> None:
        super().__init__(
            db,
            session_id,
            settings,
            event_emitter=event_emitter,
            agent_id=agent_id,
            task_id=task_id,
            emit_lifecycle_events=emit_lifecycle_events,
            model_role=ModelRole.WRITER,
        )
        self.system_prompt = get_generation_prompt()
        self.system_prompt_multipage = get_generation_prompt_multipage()
        self._current_html: Optional[str] = None

    def progress_steps(self) -> List[GenerationProgress]:
        return [
            GenerationProgress(message="Analyzing requirements", progress=20),
            GenerationProgress(message="Generating layout", progress=60),
            GenerationProgress(message="Finalizing output", progress=90),
        ]

    async def generate(
        self,
        *,
        requirements: Optional[str] = None,
        output_dir: Optional[str] = None,
        history: Sequence[dict] | None = None,
        current_html: Optional[str] = None,
        stream: bool = False,
        page_id: Optional[str] = None,
        page_spec: SitemapPage | dict | None = None,
        global_style: GlobalStyle | dict | None = None,
        nav: Sequence[NavItem | dict] | None = None,
        product_doc: Any | None = None,
        all_pages: Sequence[str] | None = None,
        css_mode: str = "inline",
        guardrails: dict | None = None,
    ) -> GenerationResult:
        history = history or []
        html = ""
        response = None
        warnings: List[str] = []
        fallback_used = False
        fallback_excerpt: Optional[str] = None
        resolved_current_html = current_html if current_html is not None else self._current_html
        multi_page = page_spec is not None

        if not multi_page and not output_dir:
            raise ValueError("output_dir is required for single-page generation")

        try:
            if multi_page:
                messages = self._build_messages_multipage(
                    page_spec=page_spec,
                    global_style=global_style,
                    nav=nav,
                    product_doc=product_doc,
                    all_pages=all_pages,
                    requirements=requirements,
                    history=history,
                    current_html=resolved_current_html,
                    guardrails=guardrails,
                )
            else:
                messages = self._build_messages(
                    requirements=requirements or "",
                    history=history,
                    current_html=resolved_current_html,
                    guardrails=guardrails,
                )
            if stream:
                response = await self._call_llm(
                    messages=messages,
                    agent_type=self.agent_type,
                    temperature=self.settings.temperature,
                    stream=True,
                    context="generation",
                )
            else:
                if multi_page:
                    response = await self._call_llm(
                        messages=messages,
                        agent_type=self.agent_type,
                        temperature=self.settings.temperature,
                        stream=False,
                        context="generation",
                    )
                else:
                    tools = get_filesystem_tools()
                    tool_handlers = {"filesystem_write": self._write_file_handler(output_dir)}
                    response = await self._call_llm_with_tools(
                        messages=messages,
                        tools=tools,
                        tool_handlers=tool_handlers,
                        temperature=self.settings.temperature,
                        context="generation",
                    )
            html, response = await self._extract_html_with_retry(
                messages=messages,
                initial_response=response,
                stream=stream,
            )
            if not html:
                fallback_excerpt = build_fallback_excerpt(getattr(response, "content", None))
                self._log_raw_response(response)
                trace_id = new_trace_id()
                raise HTMLExtractionError("No HTML detected in model response", trace_id=trace_id)
        except Exception as exc:
            fallback_used = True
            if fallback_excerpt is None:
                fallback_excerpt = build_fallback_excerpt(getattr(response, "content", None))
            if isinstance(exc, HTMLExtractionError):
                logger.warning("GenerationAgent fallback triggered: %s", exc.with_trace())
            else:
                logger.warning("GenerationAgent fallback triggered: %s", str(exc))
            logger.exception("GenerationAgent failed to use LLM, falling back to template")
            html = self._fallback_html(requirements or "")

        html = self._strip_prompt_artifacts(html)

        if multi_page:
            resolved_pages = self._resolve_all_pages(all_pages=all_pages, nav=nav, page_spec=page_spec)
            html, link_warnings = normalize_internal_links(html, all_pages=resolved_pages)
            if link_warnings:
                warnings.extend(link_warnings)
                logger.warning("GenerationAgent detected broken internal links: %s", ", ".join(link_warnings))

            global_style_css = self._build_site_css(global_style, product_doc)
            if css_mode == "external":
                css_href = self._resolve_css_href(page_spec)
                html = ensure_css_link(html, css_href)
            else:
                html = inline_css(html, global_style_css)
            html = self._apply_data_protocol(
                html,
                product_doc=product_doc,
                output_dir=output_dir,
                page_slug=self._get_page_slug(page_spec),
            )
            await self._provision_app_data_tables(product_doc=product_doc)
            html = self._apply_component_registry(
                html,
                product_doc=product_doc,
                output_dir=output_dir,
                page_slug=self._get_page_slug(page_spec),
            )
            html = await self._ensure_page_styles(html, product_doc=product_doc)
            html = ensure_dom_ids(html)

            filepath = ""
            preview_url = ""
            if output_dir:
                filepath, preview_url = self._save_page_html(
                    output_dir=output_dir,
                    slug=self._get_page_slug(page_spec),
                    html=html,
                )

            version_number = None
            if self.db is not None and page_id:
                service = PageVersionService(self.db, event_emitter=self.event_emitter)
                record = service.create(
                    page_id,
                    html,
                    description=self._build_version_description(page_spec),
                    preview_url=preview_url or None,
                    fallback_used=fallback_used,
                    fallback_excerpt=fallback_excerpt,
                )
                version_number = record.version

            self._current_html = html
            token_usage = self._serialize_token_usage(response)
            return GenerationResult(
                html=html,
                preview_url=preview_url,
                filepath=filepath,
                token_usage=token_usage,
                page_id=page_id,
                version=version_number,
                warnings=warnings,
                fallback_used=fallback_used,
                fallback_excerpt=fallback_excerpt,
            )

        html = self._apply_data_protocol(
            html,
            product_doc=product_doc,
            output_dir=output_dir,
            page_slug="index",
        )
        await self._provision_app_data_tables(product_doc=product_doc)
        html = self._apply_component_registry(
            html,
            product_doc=product_doc,
            output_dir=output_dir,
            page_slug="index",
        )
        html = await self._ensure_page_styles(html, product_doc=product_doc)
        html = ensure_dom_ids(html)

        filepath, preview_url = self._save_html(output_dir=output_dir, html=html)
        self._current_html = html
        token_usage = self._serialize_token_usage(response)
        return GenerationResult(
            html=html,
            preview_url=preview_url,
            filepath=filepath,
            token_usage=token_usage,
            warnings=warnings,
            fallback_used=fallback_used,
            fallback_excerpt=fallback_excerpt,
        )

    def _build_messages(
        self,
        *,
        requirements: str,
        history: Sequence[dict],
        current_html: Optional[str],
        guardrails: dict | None,
    ) -> list[dict]:
        resolved_current_html = current_html if current_html is not None else self._current_html
        messages: list[dict] = [{"role": "system", "content": self.system_prompt}]
        guardrails_text = guardrails_to_prompt(guardrails)
        if guardrails_text:
            messages.append({"role": "system", "content": guardrails_text})
        self._append_history_messages(messages, history)

        requirements_text = requirements.strip() or "Generate a mobile-first HTML page."
        user_parts = [f"Requirements:\n{requirements_text}"]
        if resolved_current_html:
            user_parts.append(f"Current HTML:\n{resolved_current_html}")
        messages.append({"role": "user", "content": "\n\n".join(user_parts)})
        return messages

    def _build_messages_multipage(
        self,
        *,
        page_spec: SitemapPage | dict,
        global_style: GlobalStyle | dict | None,
        nav: Sequence[NavItem | dict] | None,
        product_doc: Any | None,
        all_pages: Sequence[str] | None,
        requirements: Optional[str],
        history: Sequence[dict],
        current_html: Optional[str],
        guardrails: dict | None,
    ) -> list[dict]:
        page_title = self._get_page_field(page_spec, "title")
        page_slug = self._get_page_field(page_spec, "slug")
        page_purpose = self._get_page_field(page_spec, "purpose")
        sections = self._get_page_sections(page_spec)
        sections_list = ", ".join(sections) if sections else "None specified"

        design_direction = self._extract_design_direction(product_doc)
        global_style_css = build_global_style_css(self._coerce_mapping(global_style), design_direction)
        resolved_pages = self._resolve_all_pages(all_pages=all_pages, nav=nav, page_spec=page_spec)
        nav_list = self._format_nav_list(nav) if nav else "\n".join(f"- {slug} ({slug})" for slug in resolved_pages)
        nav_html = build_nav_html(nav or [], current_slug=page_slug, all_pages=resolved_pages)
        product_doc_context = self._build_product_doc_context(product_doc)
        requirements_text = (requirements or "").strip() or "None"

        system_prompt = self.system_prompt_multipage.format(
            page_title=page_title or "Untitled",
            page_slug=page_slug or "index",
            page_purpose=page_purpose or "No purpose specified",
            sections_list=sections_list,
            global_style_css=global_style_css,
            nav_list=nav_list,
            current_slug=page_slug or "index",
            nav_html=nav_html or "<nav class=\"site-nav\"></nav>",
            product_doc_context=product_doc_context,
            requirements=requirements_text,
        )

        messages: list[dict] = [{"role": "system", "content": system_prompt}]
        guardrails_text = guardrails_to_prompt(guardrails)
        if guardrails_text:
            messages.append({"role": "system", "content": guardrails_text})
        self._append_history_messages(messages, history)

        resolved_current_html = current_html if current_html is not None else self._current_html
        if resolved_current_html:
            messages.append({"role": "user", "content": f"Current HTML:\n{resolved_current_html}"})
        return messages

    def _append_history_messages(self, messages: list[dict], history: Sequence[dict]) -> None:
        for item in history:
            role = item.get("role", "user")
            content = item.get("content", "")
            if content and "<INTERVIEW_ANSWERS>" in content:
                content = re.sub(
                    r"<INTERVIEW_ANSWERS>.*?</INTERVIEW_ANSWERS>",
                    "",
                    content,
                    flags=re.DOTALL,
                )
                content = re.sub(r"^Answer summary:.*$", "", content, flags=re.MULTILINE | re.IGNORECASE).strip()
            if content:
                messages.append({"role": role, "content": content})

    def _coerce_page_spec(self, page_spec: SitemapPage | dict) -> dict:
        if isinstance(page_spec, dict):
            return page_spec
        if hasattr(page_spec, "model_dump"):
            return page_spec.model_dump()
        if hasattr(page_spec, "dict"):
            return page_spec.dict()
        return {
            "title": getattr(page_spec, "title", ""),
            "slug": getattr(page_spec, "slug", ""),
            "purpose": getattr(page_spec, "purpose", ""),
            "sections": getattr(page_spec, "sections", []),
        }

    def _get_page_field(self, page_spec: SitemapPage | dict, field: str) -> str:
        payload = self._coerce_page_spec(page_spec)
        return str(payload.get(field) or "")

    def _get_page_sections(self, page_spec: SitemapPage | dict) -> List[str]:
        payload = self._coerce_page_spec(page_spec)
        sections = payload.get("sections")
        if isinstance(sections, list):
            return [str(item) for item in sections if str(item).strip()]
        return []

    def _get_page_slug(self, page_spec: SitemapPage | dict) -> str:
        slug = self._get_page_field(page_spec, "slug") or "index"
        return slug

    def _format_nav_list(self, nav: Sequence[NavItem | dict] | None) -> str:
        items: List[str] = []
        for item in nav or []:
            payload = self._coerce_mapping(item)
            slug = str(payload.get("slug") or "").strip()
            label = str(payload.get("label") or "").strip()
            if not slug:
                continue
            if not label:
                label = slug
            items.append(f"- {label} ({slug})")
        return "\n".join(items) if items else "- index (index)"

    def _coerce_mapping(self, value: Any) -> dict:
        if value is None:
            return {}
        if isinstance(value, dict):
            return value
        if hasattr(value, "model_dump"):
            return value.model_dump()
        if hasattr(value, "dict"):
            return value.dict()
        return {}

    def _build_product_doc_context(self, product_doc: Any, max_chars: int = 1800) -> str:
        if product_doc is None:
            return "No product document available."

        content = ""
        structured: dict = {}
        if isinstance(product_doc, dict):
            content = str(product_doc.get("content") or "")
            structured_value = product_doc.get("structured")
            if isinstance(structured_value, dict):
                structured = structured_value
        else:
            content = str(getattr(product_doc, "content", "") or "")
            structured_value = getattr(product_doc, "structured", None)
            if isinstance(structured_value, dict):
                structured = structured_value

        parts: List[str] = []
        if structured:
            project_name = structured.get("project_name") or structured.get("projectName")
            description = structured.get("description")
            target = structured.get("target_audience") or structured.get("targetAudience")
            goals = structured.get("goals") if isinstance(structured.get("goals"), list) else []
            features = structured.get("features") if isinstance(structured.get("features"), list) else []
            constraints = structured.get("constraints") if isinstance(structured.get("constraints"), list) else []
            component_inventory = structured.get("component_inventory")
            if not isinstance(component_inventory, list):
                component_inventory = structured.get("components") if isinstance(structured.get("components"), list) else []
            design = structured.get("design_direction") or structured.get("designDirection") or {}

            if project_name:
                parts.append(f"Project: {project_name}")
            if description:
                parts.append(f"Description: {description}")
            if target:
                parts.append(f"Target audience: {target}")
            if goals:
                parts.append(f"Goals: {', '.join(map(str, goals[:6]))}")
            if features:
                feature_names = []
                for feature in features[:6]:
                    if isinstance(feature, dict):
                        name = feature.get("name")
                        priority = feature.get("priority")
                        if name and priority:
                            feature_names.append(f"{name} ({priority})")
                        elif name:
                            feature_names.append(str(name))
                    else:
                        feature_names.append(str(feature))
                if feature_names:
                    parts.append(f"Key features: {', '.join(feature_names)}")
            if constraints:
                parts.append(f"Constraints: {', '.join(map(str, constraints[:6]))}")
            if component_inventory:
                parts.append(f"Component inventory: {', '.join(map(str, component_inventory[:8]))}")
            if isinstance(design, dict) and design:
                style = design.get("style")
                tone = design.get("tone")
                color_pref = design.get("color_preference") or design.get("colorPreference")
                design_bits = []
                if style:
                    design_bits.append(f"style={style}")
                if tone:
                    design_bits.append(f"tone={tone}")
                if color_pref:
                    design_bits.append(f"colors={color_pref}")
                if design_bits:
                    parts.append(f"Design direction: {', '.join(design_bits)}")

        if not parts:
            if content:
                excerpt = content.strip()
                if len(excerpt) > max_chars:
                    excerpt = excerpt[:max_chars] + "..."
                return f"Product doc excerpt:\n{excerpt}"
            return "No product document available."

        context = "\n".join(parts)
        if len(context) > max_chars:
            context = context[:max_chars] + "..."
        return context

    def _extract_design_direction(self, product_doc: Any) -> dict:
        if product_doc is None:
            return {}
        structured = None
        if isinstance(product_doc, dict):
            structured = product_doc.get("structured")
        else:
            structured = getattr(product_doc, "structured", None)
        if not isinstance(structured, dict):
            return {}
        design = structured.get("design_direction") or structured.get("designDirection") or {}
        return design if isinstance(design, dict) else {}

    def _resolve_product_type(self, product_doc: Any) -> Optional[str]:
        if product_doc is None:
            return None
        structured = None
        if isinstance(product_doc, dict):
            structured = product_doc.get("structured")
        else:
            structured = getattr(product_doc, "structured", None)
        if isinstance(structured, dict):
            value = structured.get("product_type") or structured.get("productType")
            if value:
                return str(value).strip().lower()
        return None

    def _needs_page_css(self, html: str) -> bool:
        if not html:
            return True
        matches = _STYLE_TAG_RE.findall(html)
        if not matches:
            return True
        if len(matches) > 1:
            return False
        only = matches[0] or ""
        return "Site-wide Design System" in only

    async def _ensure_page_styles(self, html: str, *, product_doc: Any | None) -> str:
        if not self._needs_page_css(html):
            return html
        try:
            refiner = StyleRefiner(
                self.db,
                self.session_id,
                self.settings,
                event_emitter=self.event_emitter,
                agent_id="style_refiner_css",
                emit_lifecycle_events=False,
            )
            refined = await refiner.refine(
                html,
                product_type=self._resolve_product_type(product_doc),
            )
            return refined or html
        except Exception:
            logger.exception("Style refiner failed to add page CSS")
            return html

    def _resolve_all_pages(
        self,
        *,
        all_pages: Sequence[str] | None,
        nav: Sequence[NavItem | dict] | None,
        page_spec: SitemapPage | dict,
    ) -> List[str]:
        resolved: List[str] = []
        seen = set()

        def _add(slug: str) -> None:
            if slug and slug not in seen:
                resolved.append(slug)
                seen.add(slug)

        for slug in all_pages or []:
            _add(str(slug))
        for item in nav or []:
            payload = self._coerce_mapping(item)
            _add(str(payload.get("slug") or ""))

        _add(self._get_page_slug(page_spec))
        _add("index")
        return resolved

    def _build_site_css(self, global_style: GlobalStyle | dict | None, product_doc: Any) -> str:
        design_direction = self._extract_design_direction(product_doc)
        return build_site_css(self._coerce_mapping(global_style), design_direction, include_nav=False)

    def _build_version_description(self, page_spec: SitemapPage | dict) -> str:
        title = self._get_page_field(page_spec, "title")
        slug = self._get_page_slug(page_spec)
        if title:
            return f"Generated {title}"
        return f"Generated {slug}"

    def _resolve_css_href(self, page_spec: SitemapPage | dict) -> str:
        slug = self._get_page_slug(page_spec)
        if slug == "index":
            return "assets/site.css"
        return "../assets/site.css"

    def _extract_html(self, content: str) -> str:
        if not content:
            return ""
        candidate = content.strip()
        if not candidate:
            return ""

        candidate = html_lib.unescape(candidate)

        fence_match = re.search(r"```(?:html)?\s*(.*?)```", candidate, re.DOTALL | re.IGNORECASE)
        if fence_match:
            candidate = fence_match.group(1).strip()

        marker_match = re.search(r"<HTML_OUTPUT>(.*?)</HTML_OUTPUT>", candidate, re.DOTALL | re.IGNORECASE)
        if marker_match:
            return marker_match.group(1).strip()
        marker_start = re.search(r"<HTML_OUTPUT>", candidate, re.IGNORECASE)
        if marker_start:
            candidate = candidate[marker_start.end() :].strip()
            # If the model didn't close the marker, fall back to raw segment.
            if "</html>" not in candidate.lower() and "<html" not in candidate.lower():
                return candidate.strip()

        lowered = candidate.lower()
        start = lowered.find("<!doctype html")
        end = lowered.rfind("</html>")
        if start != -1:
            if end != -1 and end > start:
                return candidate[start : end + len("</html>")].strip()
            return candidate[start:].strip()

        html_match = re.search(r"<html\b[\s\S]*?</html>", candidate, re.IGNORECASE)
        if html_match:
            return html_match.group(0).strip()
        html_start = re.search(r"<html\b", candidate, re.IGNORECASE)
        if html_start:
            return candidate[html_start.start():].strip()

        logger.warning("GenerationAgent failed to extract HTML from response")
        return ""

    async def _extract_html_with_retry(
        self,
        *,
        messages: list[dict],
        initial_response: Any,
        stream: bool,
    ) -> tuple[str, Any]:
        response = initial_response
        html = self._extract_html(getattr(response, "content", "") or "")
        last_html = html
        if html and self._is_html_complete(html):
            return html, response

        if html and not self._is_html_complete(html):
            logger.warning("GenerationAgent received incomplete HTML from response")
            html = ""

        retry_temperature = min(self.settings.temperature, STRICT_RETRY_TEMPERATURE)
        for attempt in range(1, MAX_HTML_RETRIES + 1):
            logger.warning("GenerationAgent retrying HTML extraction (%s/%s)", attempt, MAX_HTML_RETRIES)
            retry_messages = list(messages) + [
                {"role": "user", "content": STRICT_HTML_RETRY_INSTRUCTIONS}
            ]
            response = await self._call_llm(
                messages=retry_messages,
                agent_type=self.agent_type,
                temperature=retry_temperature,
                stream=False,
                emit_progress=False,
                context=f"generation-strict-retry-{attempt}",
            )
            html = self._extract_html(getattr(response, "content", "") or "")
            if html:
                last_html = html
            if html and self._is_html_complete(html):
                return html, response
            if html:
                logger.warning("GenerationAgent received incomplete HTML on retry %s", attempt)
            else:
                logger.warning("GenerationAgent could not extract HTML on retry %s", attempt)

        if stream:
            logger.warning("GenerationAgent failed to extract HTML after streaming retries")
        return last_html or "", response

    def _strip_prompt_artifacts(self, html: str) -> str:
        cleaned = strip_prompt_artifacts(html)
        if cleaned != html:
            logger.warning("GenerationAgent stripped prompt artifacts from HTML output")
        return cleaned

    def _is_html_complete(self, html: str) -> bool:
        lowered = (html or "").lower()
        return "<html" in lowered and "</html>" in lowered and "<body" in lowered

    def _log_raw_response(self, response: Any) -> None:
        content = getattr(response, "content", None) if response is not None else None
        if not content:
            return
        snippet = " ".join(str(content).split())
        if len(snippet) > 800:
            snippet = f"{snippet[:400]} ... {snippet[-400:]}"
        logger.warning("GenerationAgent raw response (truncated): %s", snippet)

    def _save_html(self, *, output_dir: str, html: str) -> tuple[str, str]:
        fs = FilesystemService(output_dir)
        path = fs.save_html(self.session_id, html, filename="index.html")
        self._write_version_copy(path, html)
        preview_url = Path(path).absolute().as_uri()
        return str(Path(path).absolute()), preview_url

    def _save_page_html(self, *, output_dir: str, slug: str, html: str) -> tuple[str, str]:
        fs = FilesystemService(output_dir)
        session_dir = fs.create_session_directory(self.session_id)
        resolved_slug = slug or "index"
        if resolved_slug == "index":
            path = session_dir / "index.html"
        else:
            pages_dir = session_dir / "pages"
            pages_dir.mkdir(parents=True, exist_ok=True)
            path = pages_dir / f"{resolved_slug}.html"
        path.write_text(html, encoding="utf-8")
        self._write_version_copy(path, html)
        preview_url = path.absolute().as_uri()
        return str(path.absolute()), preview_url

    def _write_version_copy(self, path: Path, html: str) -> Path:
        timestamp = self._timestamp()
        version_path = path.with_name(f"v{timestamp}_{path.name}")
        version_path.write_text(html, encoding="utf-8")
        return version_path

    def _write_file_handler(self, output_dir: str) -> Callable[..., Any]:
        session_dir = (Path(output_dir).resolve() / self.session_id).resolve()

        async def handler(path: str, content: str, encoding: str = "utf-8") -> dict:
            resolved_encoding = self._validate_encoding(encoding)
            written_bytes = len(content.encode(resolved_encoding))
            if written_bytes > MAX_WRITE_BYTES:
                raise ValueError("Content exceeds maximum allowed size")
            target = self._resolve_safe_path(session_dir=session_dir, path=path)
            session_dir.mkdir(parents=True, exist_ok=True)
            preview_path = session_dir / "index.html"
            preview_path.write_text(content, encoding=resolved_encoding)
            timestamp = self._timestamp()
            version_name = f"v{timestamp}_{target.name}"
            version_path = session_dir / version_name
            version_path.write_text(content, encoding=resolved_encoding)
            output = {
                "preview_path": str(preview_path),
                "version_path": str(version_path.name),
                "version": timestamp,
                "written_bytes": written_bytes,
            }
            return {
                "success": True,
                "preview_path": output["preview_path"],
                "version_path": output["version_path"],
                "version": output["version"],
                "output": output,
            }

        return handler

    def _apply_data_protocol(
        self,
        html: str,
        *,
        product_doc: Any | None,
        output_dir: Optional[str],
        page_slug: str,
    ) -> str:
        if not output_dir:
            return html
        try:
            generator = DataProtocolGenerator(
                output_dir=output_dir,
                session_id=self.session_id,
                db=self.db,
            )
            return generator.prepare_html(html, product_doc=product_doc, page_slug=page_slug)
        except Exception:
            logger.exception("GenerationAgent failed to apply data protocol injection")
            return html

    async def _provision_app_data_tables(self, *, product_doc: Any | None) -> None:
        data_model = self._extract_data_model(product_doc)
        entities = data_model.get("entities") if isinstance(data_model, dict) else None
        if not isinstance(entities, dict) or not entities:
            return

        store = get_app_data_store()
        if not store.enabled:
            return

        try:
            schema = await store.create_schema(self.session_id)
            summary = await store.create_tables(self.session_id, data_model)
            logger.info(
                "GenerationAgent app data schema provisioned: session_id=%s schema=%s summary=%s",
                self.session_id,
                schema,
                summary,
            )
        except Exception:
            logger.warning(
                "GenerationAgent app data schema provisioning failed for session %s",
                self.session_id,
                exc_info=True,
            )

    def _extract_data_model(self, product_doc: Any | None) -> dict[str, Any]:
        if product_doc is None:
            return {}

        structured: Any = None
        if isinstance(product_doc, dict):
            structured = product_doc.get("structured") if isinstance(product_doc.get("structured"), dict) else None
            if structured is None:
                structured = product_doc
        else:
            maybe_structured = getattr(product_doc, "structured", None)
            if isinstance(maybe_structured, dict):
                structured = maybe_structured

        if not isinstance(structured, dict):
            return {}

        data_model = structured.get("data_model")
        if hasattr(data_model, "model_dump"):
            dumped = data_model.model_dump(by_alias=True, exclude_none=True)
            return dumped if isinstance(dumped, dict) else {}
        return data_model if isinstance(data_model, dict) else {}

    def _apply_component_registry(
        self,
        html: str,
        *,
        product_doc: Any | None,
        output_dir: Optional[str],
        page_slug: Optional[str] = None,
    ) -> str:
        if not output_dir or not product_doc:
            return html
        structured = None
        if isinstance(product_doc, dict):
            structured = product_doc.get("structured")
        else:
            structured = getattr(product_doc, "structured", None)
        if not isinstance(structured, dict):
            return html
        registry_info = structured.get("component_registry")
        if hasattr(registry_info, "model_dump"):
            registry_info = registry_info.model_dump()
        if not isinstance(registry_info, dict):
            return html
        registry_path = registry_info.get("path")
        if not registry_path:
            return html
        service = ComponentRegistryService(output_dir, self.session_id)
        resolved = service.resolve_relative_path(str(registry_path))
        if not resolved.exists():
            return html
        try:
            registry = json.loads(resolved.read_text(encoding="utf-8"))
        except Exception:
            logger.exception("Failed to load component registry")
            return html
        try:
            return assemble_components(
                html,
                registry,
                base_dir=service.session_dir,
                page_slug=page_slug,
            )
        except Exception:
            logger.exception("Component assembly failed; returning original HTML")
            return html

    def _resolve_safe_path(self, *, session_dir: Path, path: str) -> Path:
        if not path or not str(path).strip():
            raise ValueError("Path is required")
        candidate = Path(path)
        if candidate.is_absolute():
            resolved = candidate.resolve()
        else:
            resolved = (session_dir / candidate).resolve()
        session_resolved = session_dir.resolve()
        try:
            resolved.relative_to(session_resolved)
        except ValueError as exc:
            raise ValueError("Path is outside of the allowed directory") from exc
        if resolved.suffix.lower() not in ALLOWED_WRITE_EXTENSIONS:
            raise ValueError("Unsupported file extension")
        return resolved

    def _validate_encoding(self, encoding: str) -> str:
        normalized = (encoding or "").lower()
        if normalized not in ALLOWED_ENCODINGS:
            raise ValueError("Unsupported encoding")
        return normalized

    def _serialize_token_usage(self, response: Any) -> Optional[dict]:
        usage = getattr(response, "token_usage", None) if response is not None else None
        if usage is None:
            return None
        return {
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "total_tokens": usage.total_tokens,
            "cost_usd": usage.cost_usd,
        }

    def _timestamp(self) -> int:
        return int(time.time() * 1000)

    def _fallback_html(self, requirements: str) -> str:
        safe_text = requirements.strip() or "Generated Page"
        return (
            "<!doctype html>\n"
            "<html><head><meta charset=\"utf-8\"/>"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"/>"
            "<title>Instant Coffee</title>"
            "<style>body{font-family:Arial,sans-serif;padding:24px;}h1{font-size:24px;}</style>"
            "</head><body>"
            f"<h1>Generated Page</h1><p>{safe_text}</p>"
            "</body></html>"
        )


__all__ = ["GenerationAgent", "GenerationProgress", "GenerationResult"]
