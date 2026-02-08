from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Sequence

from .base import BaseAgent
from .prompts import get_refinement_prompt
from ..llm.model_pool import ModelRole
from ..db.models import Page, ProductDoc
from ..llm.tool_handlers import (
    DEFAULT_ALLOWED_EXTENSIONS,
    MAX_WRITE_BYTES,
    build_filesystem_read_handler,
)
from ..llm.tools import ToolResult, get_filesystem_tools
from ..schemas.sitemap import GlobalStyle
from ..services.data_protocol import DataProtocolGenerator
from ..services.filesystem import FilesystemService
from ..services.page_version import PageVersionService
from ..utils.html import (
    build_nav_html,
    normalize_internal_links,
)
from ..utils.style import build_global_style_css

logger = logging.getLogger(__name__)

_GLOBAL_CHANGE_KEYWORDS = {
    "all pages",
    "every page",
    "entire site",
    "whole site",
    "site-wide",
    "across all pages",
    "across the site",
    "global",
}


@dataclass
class DisambiguationResult:
    """Returned when page cannot be determined."""

    candidates: list[Page]
    message: str


@dataclass
class RefinementResult:
    page_id: Optional[str]
    html: str
    version: Optional[int]
    tokens_used: int
    changes_made: str
    preview_url: Optional[str] = None
    filepath: Optional[str] = None


@dataclass
class BatchRefinementResult:
    results: list[Optional[RefinementResult]]
    failures: list[tuple[str, str]]


class RefinementAgent(BaseAgent):
    agent_type = "refinement"

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
        self.system_prompt_template = get_refinement_prompt()
        self.system_prompt = self.system_prompt_template

    async def refine(
        self,
        *,
        session_id: Optional[str] = None,
        user_message: Optional[str] = None,
        user_input: Optional[str] = None,
        page: Optional[Page] = None,
        product_doc: ProductDoc | dict | None = None,
        global_style: GlobalStyle | dict | None = None,
        all_pages: Sequence[Page] | None = None,
        history: Optional[list] = None,
        current_html: Optional[str] = None,
        output_dir: Optional[str] = None,
    ) -> RefinementResult:
        history = history or []
        instructions = (user_message or user_input or "").strip() or "Refine the HTML based on feedback."

        if page is None:
            return await self._refine_single_page(
                instructions=instructions,
                current_html=current_html or "",
                output_dir=output_dir,
                history=history,
            )

        resolved_current_html = current_html or self._get_latest_page_html(page)
        html = ""
        response = None
        tokens_used = 0

        try:
            messages = self._build_messages(
                page=page,
                user_message=instructions,
                product_doc=product_doc,
                global_style=global_style,
                all_pages=all_pages,
                history=history,
                current_html=resolved_current_html,
            )
            self._emit_agent_progress(message="Analyzing changes...", progress=30)
            response = await self._call_llm(
                messages=messages,
                agent_type=self.agent_type,
                temperature=self.settings.temperature,
                stream=True,
                context="refinement",
            )
            html = self._extract_html(response.content)
            if not html:
                raise ValueError("No HTML detected in model response")
            tokens_used = response.token_usage.total_tokens if response.token_usage else 0
        except Exception:
            logger.exception("RefinementAgent failed to use LLM, falling back to template")
            html = self._fallback_html(user_input=instructions, current_html=resolved_current_html)

        resolved_pages = list(all_pages) if all_pages else [page]
        all_page_slugs = self._resolve_all_pages(resolved_pages, page)

        html, link_warnings = normalize_internal_links(html, all_pages=all_page_slugs)
        if link_warnings:
            logger.warning("RefinementAgent detected broken internal links: %s", ", ".join(link_warnings))
        html = self._apply_data_protocol(
            html,
            product_doc=product_doc,
            output_dir=output_dir,
            page_slug=page.slug,
        )

        preview_url = None
        filepath = None
        if output_dir:
            filepath, preview_url = self._save_page_html(output_dir=output_dir, slug=page.slug, html=html)

        version_number = None
        if self.db is not None:
            description = self._build_version_description(page, instructions)
            record = PageVersionService(self.db, event_emitter=self.event_emitter).create(
                page.id,
                html,
                description=description,
                preview_url=preview_url or None,
            )
            version_number = record.version

        self._emit_agent_progress(message="Refinement complete", progress=100)
        return RefinementResult(
            page_id=page.id,
            html=html,
            version=version_number,
            tokens_used=tokens_used,
            changes_made=self._summarize_changes(instructions),
            preview_url=preview_url,
            filepath=filepath,
        )

    async def detect_target_page(self, message: str, pages: list[Page]) -> Page | DisambiguationResult:
        if not pages:
            return DisambiguationResult(candidates=[], message="No pages available to refine.")

        cleaned = (message or "").strip()
        if len(pages) == 1:
            return pages[0]

        if not cleaned:
            return DisambiguationResult(candidates=pages, message="Which page do you want to modify?")

        lower_message = cleaned.lower()
        normalized_message = re.sub(r"\s+", "", lower_message)

        matches: list[tuple[int, Page]] = []
        for page in pages:
            score = 0
            slug = (page.slug or "").lower()
            if slug:
                pattern = re.compile(rf"(?<![a-z0-9-]){re.escape(slug)}(?![a-z0-9-])")
                if pattern.search(lower_message):
                    score += 2
                if slug.replace("-", "") in normalized_message:
                    score += 1

            title = (page.title or "").strip()
            if title:
                title_norm = re.sub(r"\s+", "", title.lower())
                if title_norm and title_norm in normalized_message:
                    score += 1

            if slug == "index" and "home" in normalized_message:
                score += 1

            if score:
                matches.append((score, page))

        if matches:
            matches.sort(key=lambda item: item[0], reverse=True)
            top_score = matches[0][0]
            top_pages = [page for score, page in matches if score == top_score]
            if len(top_pages) == 1:
                return top_pages[0]
            return DisambiguationResult(
                candidates=top_pages,
                message=self._format_disambiguation_message(top_pages),
            )

        if self.is_global_change(cleaned):
            return DisambiguationResult(
                candidates=pages,
                message="This sounds like a site-wide change. Should I apply it to all pages?",
            )

        return DisambiguationResult(candidates=pages, message=self._format_disambiguation_message(pages))

    async def batch_refine(
        self,
        *,
        session_id: str,
        pages: list[Page],
        user_message: str,
        product_doc: ProductDoc | dict | None,
        global_style: GlobalStyle | dict | None,
        history: Optional[list] = None,
    ) -> BatchRefinementResult:
        results: list[Optional[RefinementResult]] = []
        failures: list[tuple[str, str]] = []
        history = history or []

        for page in pages:
            try:
                result = await self.refine(
                    user_message=user_message,
                    page=page,
                    product_doc=product_doc,
                    global_style=global_style,
                    all_pages=pages,
                    history=history,
                )
                results.append(result)
            except Exception as exc:
                logger.exception("Batch refinement failed for page %s", page.id)
                results.append(None)
                failures.append((page.id, str(exc)))

        return BatchRefinementResult(results=results, failures=failures)

    def is_global_change(self, message: str) -> bool:
        lower = (message or "").lower()
        return any(keyword in lower for keyword in _GLOBAL_CHANGE_KEYWORDS)

    def _build_messages(
        self,
        *,
        page: Page,
        user_message: str,
        product_doc: ProductDoc | dict | None,
        global_style: GlobalStyle | dict | None,
        all_pages: Sequence[Page] | None,
        history: Sequence[dict],
        current_html: Optional[str],
    ) -> list[dict]:
        page_title = page.title or "Untitled"
        page_slug = page.slug or "index"
        page_purpose, sections = self._resolve_page_context(page, product_doc)
        sections_list = ", ".join(sections) if sections else "None specified"

        design_direction = self._extract_design_direction(product_doc)
        global_style_css = build_global_style_css(self._coerce_mapping(global_style), design_direction)

        resolved_pages = list(all_pages) if all_pages else [page]
        nav_items = self._build_nav_items(resolved_pages)
        nav_html = build_nav_html(nav_items, current_slug=page_slug, all_pages=self._resolve_all_pages(resolved_pages, page))
        product_doc_context = self._build_product_doc_context(product_doc)

        system_prompt = self.system_prompt_template.format(
            page_title=page_title,
            page_slug=page_slug,
            page_purpose=page_purpose or "No purpose specified",
            sections_list=sections_list,
            global_style_css=global_style_css,
            nav_html=nav_html or "<nav class=\"site-nav\"></nav>",
            product_doc_context=product_doc_context,
        )

        messages: list[dict] = [{"role": "system", "content": system_prompt}]
        self._append_history_messages(messages, history)

        instructions = user_message.strip() or "Refine the HTML based on feedback."
        html_text = current_html or ""
        content = f"Current HTML:\n{html_text}\n\nUser modification request:\n{instructions}"
        messages.append({"role": "user", "content": content})
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

    def _resolve_page_context(self, page: Page, product_doc: ProductDoc | dict | None) -> tuple[str, list[str]]:
        purpose = page.description or ""
        sections: list[str] = []
        structured = self._get_structured(product_doc)
        pages_payload = structured.get("pages") if isinstance(structured.get("pages"), list) else []

        matched = None
        for candidate in pages_payload:
            if not isinstance(candidate, dict):
                continue
            slug = str(candidate.get("slug") or "").strip().lower()
            title = str(candidate.get("title") or "").strip().lower()
            if slug and slug == (page.slug or "").lower():
                matched = candidate
                break
            if title and title == (page.title or "").strip().lower():
                matched = candidate
                break

        if matched:
            purpose = str(matched.get("purpose") or purpose or "")
            sections_value = matched.get("sections")
            if isinstance(sections_value, list):
                sections = [str(item) for item in sections_value if str(item).strip()]

        return purpose, sections

    def _build_product_doc_context(self, product_doc: ProductDoc | dict | None, max_chars: int = 1800) -> str:
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

        parts: list[str] = []
        if structured:
            project_name = structured.get("project_name") or structured.get("projectName")
            description = structured.get("description")
            target = structured.get("target_audience") or structured.get("targetAudience")
            goals = structured.get("goals") if isinstance(structured.get("goals"), list) else []
            features = structured.get("features") if isinstance(structured.get("features"), list) else []
            constraints = structured.get("constraints") if isinstance(structured.get("constraints"), list) else []
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

        if content.strip():
            excerpt = content.strip()
            if len(excerpt) > 900:
                excerpt = excerpt[:900] + "..."
            parts.append(f"ProductDoc excerpt:\n{excerpt}")

        if not parts:
            return "No product document available."

        context = "\n".join(parts)
        if len(context) > max_chars:
            context = context[:max_chars] + "..."
        return context

    def _extract_design_direction(self, product_doc: ProductDoc | dict | None) -> dict:
        structured = self._get_structured(product_doc)
        design = structured.get("design_direction") or structured.get("designDirection") or {}
        return design if isinstance(design, dict) else {}

    def _get_structured(self, product_doc: ProductDoc | dict | None) -> dict:
        if product_doc is None:
            return {}
        if isinstance(product_doc, dict):
            structured_value = product_doc.get("structured")
            return structured_value if isinstance(structured_value, dict) else {}
        structured_value = getattr(product_doc, "structured", None)
        return structured_value if isinstance(structured_value, dict) else {}

    def _build_nav_items(self, pages: Sequence[Page]) -> list[dict]:
        items: list[dict] = []
        for idx, page in enumerate(pages or []):
            slug = str(page.slug or "").strip()
            if not slug:
                continue
            label = str(page.title or slug).strip() or slug
            order = getattr(page, "order_index", idx)
            items.append({"slug": slug, "label": label, "order": order})
        return items

    def _resolve_all_pages(self, pages: Sequence[Page], current_page: Optional[Page]) -> list[str]:
        resolved: list[str] = []
        seen = set()

        def _add(slug: str) -> None:
            if slug and slug not in seen:
                resolved.append(slug)
                seen.add(slug)

        for page in pages or []:
            _add(str(page.slug or ""))
        if current_page is not None:
            _add(str(current_page.slug or ""))
        _add("index")
        return resolved

    def _format_disambiguation_message(self, pages: list[Page]) -> str:
        if not pages:
            return "Which page do you want to modify?"
        names = ", ".join(page.title or page.slug or "page" for page in pages)
        return f"Which page do you want to modify? Options: {names}."

    def _summarize_changes(self, message: str, max_len: int = 200) -> str:
        text = (message or "").strip()
        if not text:
            return "Refined page"
        if len(text) <= max_len:
            return text
        return text[: max_len - 3].rstrip() + "..."

    def _build_version_description(self, page: Page, message: str) -> str:
        title = (page.title or page.slug or "page").strip()
        summary = self._summarize_changes(message, max_len=160)
        if summary:
            return f"Refined {title}: {summary}"
        return f"Refined {title}"

    def _get_latest_page_html(self, page: Page) -> str:
        if self.db is None:
            return ""
        service = PageVersionService(self.db)
        version = service.get_current(page.id)
        if version is None:
            versions = service.list_by_page(page.id)
            version = versions[0] if versions else None
        return version.html if version is not None else ""

    async def _refine_single_page(
        self,
        *,
        instructions: str,
        current_html: str,
        output_dir: Optional[str],
        history: Sequence[dict],
    ) -> RefinementResult:
        html = ""
        tokens_used = 0
        preview_url = None
        filepath = None

        try:
            messages = self._build_messages_legacy(
                user_input=instructions,
                current_html=current_html,
                history=history,
            )
            self._emit_agent_progress(message="Analyzing changes...", progress=30)
            if output_dir:
                tools = get_filesystem_tools()
                tool_handlers = {
                    "filesystem_write": self._write_file_handler(output_dir),
                    "filesystem_read": build_filesystem_read_handler(output_dir),
                }
                response = await self._call_llm_with_tools(
                    messages=messages,
                    tools=tools,
                    tool_handlers=tool_handlers,
                    temperature=self.settings.temperature,
                    context="refinement",
                )
            else:
                response = await self._call_llm(
                    messages=messages,
                    agent_type=self.agent_type,
                    temperature=self.settings.temperature,
                    stream=True,
                    context="refinement",
                )
            html = self._extract_html(response.content)
            if not html:
                raise ValueError("No HTML detected in model response")
            tokens_used = response.token_usage.total_tokens if response.token_usage else 0
        except Exception:
            logger.exception("RefinementAgent failed to use LLM, falling back to template")
            html = self._fallback_html(user_input=instructions, current_html=current_html)

        html = self._apply_data_protocol(
            html,
            product_doc=None,
            output_dir=output_dir,
            page_slug="index",
        )

        if output_dir:
            path, preview_url = self._save_html(html=html, output_dir=output_dir)
            filepath = str(path)

        self._emit_agent_progress(message="Refinement complete", progress=100)
        return RefinementResult(
            page_id=None,
            html=html,
            version=None,
            tokens_used=tokens_used,
            changes_made=self._summarize_changes(instructions),
            preview_url=preview_url,
            filepath=filepath,
        )

    def _build_messages_legacy(
        self,
        *,
        user_input: str,
        current_html: str,
        history: Sequence[dict],
    ) -> list[dict]:
        system_prompt = self.system_prompt_template.format(
            page_title="Untitled",
            page_slug="index",
            page_purpose="No purpose specified",
            sections_list="None specified",
            global_style_css=build_global_style_css({}, {}),
            nav_html="<nav class=\"site-nav\"></nav>",
            product_doc_context="No product document available.",
        )
        messages: list[dict] = [
            {"role": "system", "content": system_prompt},
        ]
        self._append_history_messages(messages, history)

        instructions = user_input.strip() or "Refine the HTML based on feedback."
        html_text = current_html or ""
        content = f"Current HTML:\n{html_text}\n\nUser modification request:\n{instructions}"
        messages.append({"role": "user", "content": content})
        return messages

    def _extract_html(self, content: str) -> str:
        if not content:
            return ""

        marker_match = re.search(r"<HTML_OUTPUT>(.*?)</HTML_OUTPUT>", content, re.DOTALL | re.IGNORECASE)
        if marker_match:
            return marker_match.group(1).strip()

        lowered = content.lower()
        start = lowered.find("<!doctype html")
        end = lowered.rfind("</html>")
        if start != -1 and end != -1 and end > start:
            return content[start : end + len("</html>")].strip()

        html_match = re.search(r"<html\b[\s\S]*?</html>", content, re.IGNORECASE)
        if html_match:
            return html_match.group(0).strip()

        return ""

    def _save_html(self, *, html: str, output_dir: str) -> tuple[Path, str]:
        fs = FilesystemService(output_dir)
        index_path = fs.save_html(self.session_id, html, filename="index.html")
        timestamp = self._timestamp()
        version_name = f"v{timestamp}_refinement.html"
        fs.save_html(self.session_id, html, filename=version_name)
        absolute_path = Path(index_path).absolute()
        preview_url = absolute_path.as_uri()
        return absolute_path, preview_url

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

    def _apply_data_protocol(
        self,
        html: str,
        *,
        product_doc: ProductDoc | dict | None,
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
            logger.exception("RefinementAgent failed to apply data protocol injection")
            return html

    def _write_version_copy(self, path: Path, html: str) -> Path:
        timestamp = self._timestamp()
        version_path = path.with_name(f"v{timestamp}_{path.name}")
        version_path.write_text(html, encoding="utf-8")
        return version_path

    @staticmethod
    def _ensure_base_dir(base_dir: Path) -> Path:
        resolved = base_dir.resolve()
        resolved.mkdir(parents=True, exist_ok=True)
        return resolved

    @staticmethod
    def _validate_encoding(encoding: str) -> str:
        normalized = (encoding or "").lower()
        if normalized not in {"utf-8", "gbk"}:
            raise ValueError("Unsupported encoding")
        return normalized

    @staticmethod
    def _resolve_safe_path(
        base_dir: Path,
        path: str,
        *,
        allowed_extensions: Iterable[str],
    ) -> Path:
        if not path or not str(path).strip():
            raise ValueError("Path is required")

        base_dir = RefinementAgent._ensure_base_dir(base_dir)
        raw_path = Path(path)
        if raw_path.is_absolute():
            candidate = raw_path.resolve()
        else:
            candidate = (base_dir / raw_path).resolve()

        try:
            candidate.relative_to(base_dir)
        except ValueError as exc:
            raise ValueError("Path is outside of the allowed directory") from exc

        allowed = {ext.lower() for ext in allowed_extensions}
        if candidate.suffix.lower() not in allowed:
            raise ValueError("Unsupported file extension")

        return candidate

    def _write_file_handler(self, output_dir: str):
        base_dir = (Path(output_dir) / self.session_id).resolve()

        async def handler(path: str, content: str, encoding: str = "utf-8") -> ToolResult:
            resolved_encoding = self._validate_encoding(encoding)
            written_bytes = len(content.encode(resolved_encoding))
            if written_bytes > MAX_WRITE_BYTES:
                raise ValueError("Content exceeds maximum allowed size")
            target = self._resolve_safe_path(
                base_dir,
                path,
                allowed_extensions=DEFAULT_ALLOWED_EXTENSIONS,
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding=resolved_encoding)

            timestamp = self._timestamp()
            version_path = target.with_name(f"v{timestamp}_{target.name}")
            version_path.write_text(content, encoding=resolved_encoding)

            output = {
                "path": str(target),
                "version_path": str(version_path),
                "written_bytes": written_bytes,
                "version": timestamp,
            }

            if target.suffix.lower() == ".html" and target.name != "index.html":
                index_path = target.with_name("index.html")
                index_path.write_text(content, encoding=resolved_encoding)
                output["index_path"] = str(index_path)

            return ToolResult(success=True, output=output)

        return handler

    @staticmethod
    def _timestamp() -> int:
        return int(time.time() * 1000)

    def _fallback_html(self, *, user_input: str, current_html: str) -> str:
        if current_html:
            return current_html.replace("</body>", f"<p>{user_input}</p></body>")
        return ""

    def _coerce_mapping(self, value: object) -> dict:
        if value is None:
            return {}
        if isinstance(value, dict):
            return value
        if hasattr(value, "model_dump"):
            return value.model_dump()
        if hasattr(value, "dict"):
            return value.dict()
        return {}


__all__ = [
    "DisambiguationResult",
    "RefinementAgent",
    "RefinementResult",
    "BatchRefinementResult",
]
