from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import re
from uuid import uuid4
from typing import AsyncGenerator, Optional, Sequence

from sqlalchemy.orm import Session as DbSession

from ..config import get_settings
from ..db.models import Page, ProductDoc, ProductDocStatus, Session as SessionModel
from ..events.emitter import EventEmitter
from ..events.models import PlanCreatedEvent
from ..events.models import DoneEvent, ErrorEvent
from ..schemas.page import PageCreate
from ..services.plan import PlanService
from ..services.page import PageService
from ..services.page_version import PageVersionService
from ..services.product_doc import ProductDocService
from ..services.token_tracker import TokenTrackerService
from ..services.version import VersionService
from ..executor.manager import ExecutorManager
from ..executor.parallel import ParallelExecutor
from .generation import GenerationAgent
from .interview import InterviewAgent
from .multipage_decider import AutoMultiPageDecider
from .product_doc import ProductDocAgent
from .refinement import DisambiguationResult, RefinementAgent
from .sitemap import SitemapAgent

logger = logging.getLogger(__name__)

PRODUCT_DOC_KEYWORDS = [
    "requirements",
    "goals",
    "features",
    "page structure",
    "add page",
    "remove page",
    "modify feature",
    "design direction",
    "product doc",
    "product document",
]

CONFIRMATION_KEYWORDS = [
    "looks good",
    "okay",
    "confirm",
    "start",
    "generate",
    "proceed",
    "lgtm",
    "continue",
]

PAGE_REFINEMENT_KEYWORDS = ["change", "modify", "update", "adjust", "fix"]

PRODUCT_DOC_CONTEXT_TEMPLATE = """
=== Product Document Context ===
Project: {project_name}
Description: {description}
Target Audience: {target_audience}

Goals:
{goals_list}

Design Direction:
- Style: {style}
- Colors: {color_preference}
- Tone: {tone}

Pages:
{pages_list}

Constraints:
{constraints_list}
=== End Product Document ===
"""


@dataclass
class OrchestratorResponse:
    session_id: str
    phase: str
    message: str
    is_complete: bool
    preview_url: Optional[str] = None
    preview_html: Optional[str] = None
    progress: Optional[int] = None
    questions: Optional[list[dict]] = None
    action: Optional[str] = None
    product_doc_updated: Optional[bool] = None
    affected_pages: Optional[list[str]] = None
    active_page_slug: Optional[str] = None

    def to_payload(self) -> dict:
        payload = {
            "session_id": self.session_id,
            "phase": self.phase,
            "message": self.message,
            "is_complete": self.is_complete,
        }
        if self.preview_url is not None:
            payload["preview_url"] = self.preview_url
        if self.preview_html is not None:
            payload["preview_html"] = self.preview_html
        if self.progress is not None:
            payload["progress"] = self.progress
        if self.questions is not None:
            payload["questions"] = self.questions
        if self.action is not None:
            payload["action"] = self.action
        if self.product_doc_updated is not None:
            payload["product_doc_updated"] = self.product_doc_updated
        if self.affected_pages is not None:
            payload["affected_pages"] = self.affected_pages
        if self.active_page_slug is not None:
            payload["active_page_slug"] = self.active_page_slug
        return payload


@dataclass
class RouteResult:
    route: str
    target_page: Page | None = None
    disambiguation: DisambiguationResult | None = None
    generate_now: bool = False
    page_mode_override: Optional[str] = None


@dataclass
class SessionState:
    product_doc: ProductDoc | None
    status: ProductDocStatus | None
    pages: list[Page]

    @property
    def has_pages(self) -> bool:
        return bool(self.pages)


class AgentOrchestrator:
    def __init__(self, db: DbSession, session: SessionModel, event_emitter: EventEmitter | None = None) -> None:
        self.db = db
        self.session = session
        self.settings = get_settings()
        self.event_emitter = event_emitter

    def _token_summary(self) -> dict | None:
        try:
            return TokenTrackerService(self.db).summarize_session(self.session.id)
        except Exception:
            logger.exception("Failed to build token usage summary")
            return None

    def _get_latest_html(self) -> Optional[str]:
        try:
            versions = VersionService(self.db).get_versions(self.session.id, limit=1)
        except Exception:
            logger.exception("Failed to load latest version")
            return None
        if not versions:
            return None
        return versions[0].html

    def _get_latest_page_html(self, page: Page) -> Optional[str]:
        try:
            service = PageVersionService(self.db)
            current = service.get_current(page.id)
            if current is not None:
                return current.html
            versions = service.list_by_page(page.id)
        except Exception:
            logger.exception("Failed to load latest page version")
            return None
        if not versions:
            return None
        return versions[0].html

    def _wants_new_generation(self, message: str) -> bool:
        if not message:
            return False
        lower = message.lower()
        english_keywords = [
            "new page",
            "new screen",
            "start over",
            "from scratch",
            "create a new",
            "make a new",
            "regenerate",
            "generate a new",
        ]
        if any(keyword in lower for keyword in english_keywords):
            return True
        return False

    def _parse_page_mode_override(self, message: str) -> Optional[str]:
        if not message:
            return None
        lower = message.lower()
        single_keywords = [
            "single page",
            "one page",
            "single-page",
            "merge into one page",
            "merge to one page",
            "combine into one page",
            "singlepage",
        ]
        multi_keywords = [
            "multi page",
            "multi-page",
            "multiple pages",
            "multi pages",
            "separate pages",
            "split into pages",
        ]
        if any(keyword in lower for keyword in single_keywords):
            return "single"
        if any(keyword in lower for keyword in multi_keywords):
            return "multi"
        return None

    def _strip_structured_payload(self, user_message: str) -> str:
        if not user_message:
            return ""
        text = re.sub(
            r"<INTERVIEW_ANSWERS>.*?</INTERVIEW_ANSWERS>",
            "",
            user_message,
            flags=re.DOTALL,
        )
        text = re.sub(r"^Answer summary:.*$", "", text, flags=re.MULTILINE | re.IGNORECASE)
        return text.strip()

    def _extract_structured_payload(self, user_message: str) -> dict | None:
        if not user_message:
            return None
        match = re.search(r"<INTERVIEW_ANSWERS>(.*?)</INTERVIEW_ANSWERS>", user_message, re.DOTALL)
        if not match:
            return None
        payload_text = match.group(1).strip()
        if not payload_text:
            return None
        try:
            payload = json.loads(payload_text)
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None
        return payload

    def _answers_to_context(self, answers: object, *, latest_update: str | None = None) -> str | None:
        if not isinstance(answers, list):
            return None
        info: dict[str, object] = {}
        for answer in answers:
            if not isinstance(answer, dict):
                continue
            key = answer.get("id") or answer.get("question_id") or answer.get("key")
            if not key:
                continue
            value = answer.get("label") or answer.get("labels") or answer.get("value")
            other = answer.get("other")
            if value is None and other:
                value = other
            info[str(key)] = value
        if latest_update:
            info["latest_user_update"] = latest_update
        return json.dumps(info) if info else None

    def _build_requirements(self, user_message: str, context: Optional[str]) -> str:
        base = user_message.strip() if user_message else ""
        if context:
            if base:
                return f"{base}\n\nCollected info:\n{context}"
            return f"Collected info:\n{context}"
        return base or "Generate a mobile-first HTML page."

    def _build_product_doc_context(self, product_doc: ProductDoc | None) -> Optional[str]:
        if product_doc is None:
            return None
        structured = getattr(product_doc, "structured", None)
        if not isinstance(structured, dict):
            structured = {}

        project_name = structured.get("project_name") or structured.get("projectName") or "Untitled"
        description = structured.get("description") or ""
        target_audience = structured.get("target_audience") or structured.get("targetAudience") or ""
        goals = structured.get("goals") or []
        design = structured.get("design_direction") or structured.get("designDirection") or {}
        pages = structured.get("pages") or []
        constraints = structured.get("constraints") or []

        goals_list = "- (none)"
        if isinstance(goals, list) and goals:
            goals_list = "\n".join(f"- {item}" for item in goals)

        pages_list = "- (none)"
        if isinstance(pages, list) and pages:
            lines = []
            for page in pages:
                if not isinstance(page, dict):
                    continue
                title = page.get("title") or "Page"
                slug = page.get("slug") or ""
                purpose = page.get("purpose") or ""
                sections = page.get("sections") or []
                line = f"- {title} ({slug}) - {purpose}" if slug else f"- {title} - {purpose}"
                if sections:
                    line += f" | Sections: {', '.join(str(item) for item in sections)}"
                lines.append(line)
            if lines:
                pages_list = "\n".join(lines)

        constraints_list = "- (none)"
        if isinstance(constraints, list) and constraints:
            constraints_list = "\n".join(f"- {item}" for item in constraints)

        style = ""
        color_preference = ""
        tone = ""
        if isinstance(design, dict):
            style = design.get("style") or ""
            color_preference = design.get("color_preference") or design.get("colorPreference") or ""
            tone = design.get("tone") or ""

        return PRODUCT_DOC_CONTEXT_TEMPLATE.format(
            project_name=project_name,
            description=description,
            target_audience=target_audience,
            goals_list=goals_list,
            style=style,
            color_preference=color_preference,
            tone=tone,
            pages_list=pages_list,
            constraints_list=constraints_list,
        ).strip()

    def _extract_global_style(self, product_doc: ProductDoc | None) -> dict:
        if product_doc is None:
            return {}
        structured = getattr(product_doc, "structured", None)
        if not isinstance(structured, dict):
            return {}
        raw_style = structured.get("global_style") or structured.get("globalStyle") or {}
        if not isinstance(raw_style, dict):
            return {}
        return raw_style

    def _batch_refinement_message(self, batch_result, pages: list[Page], user_message: str) -> str:
        total = len(pages)
        successes = len([item for item in batch_result.results if item is not None])
        failures = batch_result.failures or []

        if not failures:
            return f"Refined {successes}/{total} pages."

        page_lookup = {page.id: page for page in pages}
        failed_names = []
        for page_id, _error in failures:
            page = page_lookup.get(page_id)
            name = page.title or page.slug or page_id
            failed_names.append(name)

        failed_list = ", ".join(failed_names) if failed_names else "unknown"
        return f"Refined {successes}/{total} pages. Failed: {failed_list}."

    def _select_preview_from_batch(self, batch_result, pages: list[Page]) -> tuple[Optional[str], Optional[str]]:
        result_map = {item.page_id: item for item in batch_result.results if item is not None}
        index_page = next((page for page in pages if page.slug == "index"), None)
        if index_page is not None:
            result = result_map.get(index_page.id)
            if result is not None:
                return result.html, index_page.slug
        for page in pages:
            result = result_map.get(page.id)
            if result is not None:
                return result.html, page.slug
        return None, None

    def _build_page_requirements(
        self,
        *,
        user_message: str,
        product_doc_context: Optional[str],
        page_spec: dict,
        nav: list,
        global_style: dict,
    ) -> str:
        base = user_message.strip() if user_message else ""
        return base

    def _build_plan_goal(self, product_doc: ProductDoc | None) -> str:
        if product_doc is None:
            return "Generate project pages"
        structured = getattr(product_doc, "structured", None)
        if isinstance(structured, dict):
            project_name = structured.get("project_name") or structured.get("projectName")
            if project_name:
                return f"Generate pages for {project_name}"
        return "Generate project pages"

    def _select_preview_from_pages(
        self,
        page_by_slug: dict[str, Page],
        ordered_slugs: list[str],
    ) -> tuple[Optional[str], Optional[str]]:
        for slug in ordered_slugs:
            page = page_by_slug.get(slug)
            if page is None:
                continue
            html = self._get_latest_page_html(page)
            if html:
                return html, slug
        for page in page_by_slug.values():
            html = self._get_latest_page_html(page)
            if html:
                return html, page.slug
        return None, None

    def _normalize_title(self, title: str) -> str:
        return re.sub(r"\s+", " ", (title or "").strip().lower())

    def _sync_pages_with_sitemap(
        self,
        *,
        page_service: PageService,
        sitemap_pages: Sequence[object],
    ) -> dict[str, Page]:
        existing_pages = page_service.list_by_session(self.session.id)
        page_by_slug = {page.slug: page for page in existing_pages}
        desired_slugs = []
        for page_spec in sitemap_pages:
            slug = getattr(page_spec, "slug", None) or ""
            if slug:
                desired_slugs.append(slug)
        desired_slug_set = set(desired_slugs)

        title_map: dict[str, Page] = {}
        duplicate_titles: set[str] = set()
        for page in existing_pages:
            key = self._normalize_title(page.title)
            if not key:
                continue
            if key in title_map:
                duplicate_titles.add(key)
            else:
                title_map[key] = page
        for key in duplicate_titles:
            title_map.pop(key, None)

        used_ids: set[str] = set()
        to_create: list[PageCreate] = []
        for idx, page_spec in enumerate(sitemap_pages):
            slug = getattr(page_spec, "slug", None) or ""
            if not slug:
                continue
            title = getattr(page_spec, "title", None) or slug or "Page"
            description = getattr(page_spec, "purpose", None) or ""
            if slug in page_by_slug:
                page = page_by_slug[slug]
                page_service.update(
                    page.id,
                    title=title,
                    description=description,
                    order_index=idx,
                )
                used_ids.add(page.id)
                continue

            key = self._normalize_title(title)
            candidate = title_map.get(key)
            if candidate and candidate.id not in used_ids and candidate.slug not in desired_slug_set:
                old_slug = candidate.slug
                page_service.update(
                    candidate.id,
                    title=title,
                    slug=slug,
                    description=description,
                    order_index=idx,
                )
                used_ids.add(candidate.id)
                page_by_slug.pop(old_slug, None)
                page_by_slug[slug] = candidate
                continue

            to_create.append(
                PageCreate(
                    title=title,
                    slug=slug,
                    description=description,
                    order_index=idx,
                )
            )

        if to_create:
            created = page_service.create_batch(self.session.id, to_create)
            for page in created:
                page_by_slug[page.slug] = page

        for slug, page in list(page_by_slug.items()):
            if slug not in desired_slug_set:
                self.db.delete(page)
                page_by_slug.pop(slug, None)

        return page_by_slug

    def _get_session_state(self) -> SessionState:
        product_doc = ProductDocService(self.db).get_by_session_id(self.session.id)
        pages = PageService(self.db).list_by_session(self.session.id)
        status = product_doc.status if product_doc is not None else None
        return SessionState(product_doc=product_doc, status=status, pages=pages)

    def _contains_keyword(self, message: str, keywords: list[str], *, lower: bool = False) -> bool:
        if not message:
            return False
        haystack = message.lower() if lower else message
        return any(keyword in haystack for keyword in keywords)

    def _is_product_doc_intent(self, message: str) -> bool:
        if not message:
            return False
        return self._contains_keyword(message, PRODUCT_DOC_KEYWORDS, lower=True)

    def _is_confirmation(self, message: str, status: ProductDocStatus | None) -> bool:
        if not message:
            return False
        if status not in (ProductDocStatus.DRAFT, ProductDocStatus.OUTDATED):
            return False
        return self._contains_keyword(message, CONFIRMATION_KEYWORDS, lower=True)

    def _contains_refinement_keyword(self, message: str) -> bool:
        if not message:
            return False
        return self._contains_keyword(message, PAGE_REFINEMENT_KEYWORDS, lower=True)

    def _detect_target_page(self, message: str, pages: list[Page]) -> Page | None:
        if not message or not pages:
            return None
        lower_message = message.lower()
        normalized_message = re.sub(r"\s+", "", lower_message)
        matches: list[tuple[int, Page]] = []

        for page in pages:
            score = 0
            slug = (page.slug or "").lower()
            if slug:
                pattern = re.compile(rf"(?<![a-z0-9-]){re.escape(slug)}(?![a-z0-9-])")
                if pattern.search(lower_message):
                    score += 2
            title = (page.title or "").strip()
            if title:
                title_norm = re.sub(r"\s+", "", title.lower())
                if title_norm and title_norm in normalized_message:
                    score += 1
            if score:
                matches.append((score, page))

        if not matches:
            if len(pages) == 1 and self._contains_refinement_keyword(message):
                return pages[0]
            return None

        matches.sort(key=lambda item: item[0], reverse=True)
        top_score = matches[0][0]
        top_pages = [page for score, page in matches if score == top_score]
        if len(top_pages) == 1:
            return top_pages[0]
        return None

    async def route(
        self,
        user_message: str,
        session: SessionModel,
        generate_now: bool = False,
    ) -> RouteResult:
        state = self._get_session_state()
        cleaned_message = self._strip_structured_payload(user_message)
        page_mode_override = self._parse_page_mode_override(cleaned_message)

        if state.product_doc is None:
            if generate_now:
                return RouteResult(
                    route="product_doc_generation_generate_now",
                    generate_now=True,
                    page_mode_override=page_mode_override,
                )
            return RouteResult(
                route="product_doc_generation",
                generate_now=False,
                page_mode_override=page_mode_override,
            )

        if state.status == ProductDocStatus.DRAFT:
            if generate_now:
                return RouteResult(
                    route="product_doc_confirm",
                    generate_now=True,
                    page_mode_override=page_mode_override,
                )
            if page_mode_override:
                return RouteResult(
                    route="product_doc_confirm",
                    generate_now=False,
                    page_mode_override=page_mode_override,
                )
            if self._is_confirmation(cleaned_message, state.status):
                return RouteResult(
                    route="product_doc_confirm",
                    generate_now=False,
                    page_mode_override=page_mode_override,
                )
            return RouteResult(
                route="product_doc_update",
                generate_now=False,
                page_mode_override=page_mode_override,
            )

        if state.status == ProductDocStatus.OUTDATED:
            if self._is_product_doc_intent(cleaned_message):
                return RouteResult(
                    route="product_doc_update",
                    generate_now=generate_now,
                    page_mode_override=page_mode_override,
                )
            if page_mode_override:
                return RouteResult(
                    route="product_doc_regenerate",
                    generate_now=generate_now,
                    page_mode_override=page_mode_override,
                )
            if generate_now or self._is_confirmation(cleaned_message, state.status):
                return RouteResult(
                    route="product_doc_regenerate",
                    generate_now=generate_now,
                    page_mode_override=page_mode_override,
                )

        if self._is_product_doc_intent(cleaned_message):
            return RouteResult(
                route="product_doc_update",
                generate_now=generate_now,
                page_mode_override=page_mode_override,
            )

        if page_mode_override:
            return RouteResult(
                route="generation_pipeline",
                generate_now=generate_now,
                page_mode_override=page_mode_override,
            )

        if state.has_pages:
            refinement_agent = RefinementAgent(
                self.db,
                self.session.id,
                self.settings,
                event_emitter=self.event_emitter,
                agent_id="refinement_1",
            )
            detection = await refinement_agent.detect_target_page(cleaned_message, state.pages)
            if isinstance(detection, Page):
                return RouteResult(route="refinement", target_page=detection, generate_now=generate_now)
            candidate_ids = {page.id for page in detection.candidates}
            all_ids = {page.id for page in state.pages}
            if candidate_ids != all_ids or refinement_agent.is_global_change(cleaned_message):
                return RouteResult(route="refinement", disambiguation=detection, generate_now=generate_now)
            if self._contains_refinement_keyword(cleaned_message):
                return RouteResult(route="refinement", disambiguation=detection, generate_now=generate_now)

        if not state.has_pages:
            return RouteResult(
                route="generation_pipeline",
                generate_now=generate_now,
                page_mode_override=page_mode_override,
            )

        return RouteResult(
            route="direct_reply",
            generate_now=generate_now,
            page_mode_override=page_mode_override,
        )

    async def stream(
        self,
        *,
        user_message: str,
        output_dir: str,
        skip_interview: bool = False,
    ) -> AsyncGenerator[object, None]:
        emitter = self.event_emitter or EventEmitter(session_id=self.session.id)
        index = 0
        previous_emitter = self.event_emitter
        self.event_emitter = emitter

        def drain() -> list[object]:
            nonlocal index
            events, index = emitter.events_since(index)
            return events

        if not user_message.strip():
            emitter.emit(DoneEvent(summary="no message"))
            for event in drain():
                yield event
            return

        try:
            async for _response in self.stream_responses(
                user_message=user_message,
                output_dir=output_dir,
                history=[],
                trigger_interview=not skip_interview,
            ):
                for event in drain():
                    yield event

            for event in drain():
                yield event
        finally:
            self.event_emitter = previous_emitter

    async def stream_responses(
        self,
        *,
        user_message: str,
        output_dir: str,
        history: Sequence[dict] | None = None,
        trigger_interview: bool = True,
        generate_now: bool = False,
    ) -> AsyncGenerator[OrchestratorResponse, None]:
        history = history or []
        emitter = self.event_emitter or EventEmitter(session_id=self.session.id)
        cleaned_user_message = self._strip_structured_payload(user_message)
        structured = self._extract_structured_payload(user_message)
        interview_context = None
        resolved_generate_now = bool(generate_now)
        if structured:
            if structured.get("action") == "generate_now":
                resolved_generate_now = True
            interview_context = self._answers_to_context(
                structured.get("answers"), latest_update=cleaned_user_message or None
            )

        state = self._get_session_state()

        if trigger_interview and state.product_doc is None and not structured:
            interview = InterviewAgent(
                self.db,
                self.session.id,
                self.settings,
                event_emitter=emitter,
                agent_id="interview_1",
            )
            interview_result = await interview.process(user_message, history=history)
            if not interview_result.is_complete and not interview.should_generate():
                summary = self._token_summary()
                yield OrchestratorResponse(
                    session_id=self.session.id,
                    phase="interview",
                    message=interview_result.message,
                    is_complete=False,
                    questions=interview_result.questions,
                )
                emitter.emit(DoneEvent(summary="interview_incomplete", token_usage=summary))
                return
            interview_context = interview_result.context

        route_result = await self.route(
            cleaned_user_message,
            self.session,
            generate_now=resolved_generate_now,
        )

        try:
            if route_result.route in ("product_doc_generation", "product_doc_generation_generate_now"):
                product_doc_agent = ProductDocAgent(
                    self.db,
                    self.session.id,
                    self.settings,
                    event_emitter=emitter,
                    agent_id="product_doc_1",
                )
                result = await product_doc_agent.generate(
                    session_id=self.session.id,
                    user_message=cleaned_user_message or user_message,
                    interview_context=interview_context,
                    history=history,
                )
                self.db.commit()

                action = "product_doc_generated"
                if route_result.route == "product_doc_generation_generate_now" or route_result.generate_now:
                    product_doc = ProductDocService(self.db).get_by_session_id(self.session.id)
                    if product_doc is not None:
                        ProductDocService(self.db, event_emitter=emitter).confirm(product_doc.id)
                        self.db.commit()
                        pipeline_result = await self._run_generation_pipeline(
                            product_doc=product_doc,
                            output_dir=output_dir,
                            history=history,
                            user_message=cleaned_user_message,
                            emitter=emitter,
                            target_slugs=None,
                            page_mode_override=route_result.page_mode_override,
                            allow_defer_on_suggest=not route_result.generate_now and not state.has_pages,
                        )
                        if pipeline_result.get("deferred"):
                            summary = self._token_summary()
                            message = self._multipage_suggestion_message(
                                pipeline_result.get("decision", {}),
                                cleaned_user_message,
                            )
                            yield OrchestratorResponse(
                                session_id=self.session.id,
                                phase="generation",
                                message=message,
                                is_complete=True,
                                progress=100,
                                action="multipage_suggested",
                            )
                            emitter.emit(DoneEvent(summary="complete", token_usage=summary))
                            return
                        summary = self._token_summary()
                        yield OrchestratorResponse(
                            session_id=self.session.id,
                            phase="generation",
                            message=self._generation_complete_message(cleaned_user_message),
                            is_complete=True,
                            preview_html=pipeline_result.get("preview_html"),
                            active_page_slug=pipeline_result.get("active_page_slug"),
                            progress=100,
                            action="pages_generated",
                        )
                        emitter.emit(DoneEvent(summary="complete", token_usage=summary))
                        return
                    action = "product_doc_generated"

                summary = self._token_summary()
                yield OrchestratorResponse(
                    session_id=self.session.id,
                    phase="product_doc",
                    message=result.message,
                    is_complete=True,
                    progress=100,
                    action=action,
                    product_doc_updated=True,
                )
                emitter.emit(DoneEvent(summary="complete", token_usage=summary))
                return

            if route_result.route == "product_doc_update":
                service = ProductDocService(self.db, event_emitter=emitter)
                product_doc = state.product_doc or service.get_by_session_id(self.session.id)
                if product_doc is None:
                    yield OrchestratorResponse(
                        session_id=self.session.id,
                        phase="product_doc",
                        message=self._missing_product_doc_message(cleaned_user_message),
                        is_complete=True,
                        action="product_doc_generated",
                    )
                    emitter.emit(DoneEvent(summary="complete", token_usage=self._token_summary()))
                    return

                update_message = cleaned_user_message or user_message
                if interview_context:
                    update_message = f"{update_message}\n\nCollected info:\n{interview_context}".strip()

                product_doc_agent = ProductDocAgent(
                    self.db,
                    self.session.id,
                    self.settings,
                    event_emitter=emitter,
                    agent_id="product_doc_1",
                )
                update_result = await product_doc_agent.update(
                    session_id=self.session.id,
                    current_doc=product_doc,
                    user_message=update_message,
                    history=history,
                )
                if product_doc.status == ProductDocStatus.CONFIRMED:
                    try:
                        service.mark_outdated(product_doc.id)
                    except Exception:
                        logger.exception("Failed to mark ProductDoc outdated")
                self.db.commit()
                message = update_result.message
                if state.has_pages:
                    message = self._append_regeneration_prompt(message, update_message)
                summary = self._token_summary()
                yield OrchestratorResponse(
                    session_id=self.session.id,
                    phase="product_doc",
                    message=message,
                    is_complete=True,
                    progress=100,
                    action="product_doc_updated",
                    product_doc_updated=True,
                    affected_pages=list(update_result.affected_pages),
                )
                emitter.emit(DoneEvent(summary="complete", token_usage=summary))
                return

            if route_result.route == "product_doc_regenerate":
                service = ProductDocService(self.db, event_emitter=emitter)
                product_doc = state.product_doc or service.get_by_session_id(self.session.id)
                if product_doc is None:
                    yield OrchestratorResponse(
                        session_id=self.session.id,
                        phase="product_doc",
                        message=self._missing_product_doc_message(cleaned_user_message),
                        is_complete=True,
                        action="product_doc_generated",
                    )
                    emitter.emit(DoneEvent(summary="complete", token_usage=self._token_summary()))
                    return
                pending_pages = self._pending_regeneration_pages(product_doc)
                pipeline_result = await self._run_generation_pipeline(
                    product_doc=product_doc,
                    output_dir=output_dir,
                    history=history,
                    user_message=cleaned_user_message,
                    emitter=emitter,
                    target_slugs=pending_pages,
                    page_mode_override=route_result.page_mode_override,
                    allow_defer_on_suggest=False,
                )
                if product_doc.status != ProductDocStatus.CONFIRMED:
                    try:
                        service.confirm(product_doc.id)
                        self.db.commit()
                    except Exception:
                        logger.exception("Failed to confirm ProductDoc after regeneration")
                if pending_pages:
                    try:
                        service.set_pending_regeneration(product_doc.id, [])
                        self.db.commit()
                    except Exception:
                        logger.exception("Failed to clear pending regeneration pages")
                summary = self._token_summary()
                yield OrchestratorResponse(
                    session_id=self.session.id,
                    phase="generation",
                    message=self._regeneration_complete_message(cleaned_user_message),
                    is_complete=True,
                    preview_html=pipeline_result.get("preview_html"),
                    active_page_slug=pipeline_result.get("active_page_slug"),
                    progress=100,
                    action="pages_generated",
                )
                emitter.emit(DoneEvent(summary="complete", token_usage=summary))
                return

            if route_result.route == "product_doc_confirm":
                service = ProductDocService(self.db, event_emitter=emitter)
                product_doc = state.product_doc or service.get_by_session_id(self.session.id)
                if product_doc is None:
                    yield OrchestratorResponse(
                        session_id=self.session.id,
                        phase="product_doc",
                        message=self._missing_product_doc_message(cleaned_user_message),
                        is_complete=True,
                        action="product_doc_generated",
                    )
                    emitter.emit(DoneEvent(summary="complete", token_usage=self._token_summary()))
                    return
                if product_doc.status != ProductDocStatus.CONFIRMED:
                    service.confirm(product_doc.id)
                    self.db.commit()
                pipeline_result = await self._run_generation_pipeline(
                    product_doc=product_doc,
                    output_dir=output_dir,
                    history=history,
                    user_message=cleaned_user_message,
                    emitter=emitter,
                    target_slugs=None,
                    page_mode_override=route_result.page_mode_override,
                    allow_defer_on_suggest=not state.has_pages,
                )
                if pipeline_result.get("deferred"):
                    summary = self._token_summary()
                    message = self._multipage_suggestion_message(
                        pipeline_result.get("decision", {}),
                        cleaned_user_message,
                    )
                    yield OrchestratorResponse(
                        session_id=self.session.id,
                        phase="generation",
                        message=message,
                        is_complete=True,
                        progress=100,
                        action="multipage_suggested",
                    )
                    emitter.emit(DoneEvent(summary="complete", token_usage=summary))
                    return
                summary = self._token_summary()
                yield OrchestratorResponse(
                    session_id=self.session.id,
                    phase="generation",
                    message=self._generation_complete_message(cleaned_user_message),
                    is_complete=True,
                    preview_html=pipeline_result.get("preview_html"),
                    active_page_slug=pipeline_result.get("active_page_slug"),
                    progress=100,
                    action="pages_generated",
                )
                emitter.emit(DoneEvent(summary="complete", token_usage=summary))
                return

            if route_result.route == "generation_pipeline":
                product_doc = state.product_doc
                if product_doc is None:
                    yield OrchestratorResponse(
                        session_id=self.session.id,
                        phase="product_doc",
                        message=self._missing_product_doc_message(cleaned_user_message),
                        is_complete=True,
                        action="product_doc_generated",
                    )
                    emitter.emit(DoneEvent(summary="complete", token_usage=self._token_summary()))
                    return
                pipeline_result = await self._run_generation_pipeline(
                    product_doc=product_doc,
                    output_dir=output_dir,
                    history=history,
                    user_message=cleaned_user_message,
                    emitter=emitter,
                    target_slugs=None,
                    page_mode_override=route_result.page_mode_override,
                    allow_defer_on_suggest=not state.has_pages,
                )
                if pipeline_result.get("deferred"):
                    summary = self._token_summary()
                    message = self._multipage_suggestion_message(
                        pipeline_result.get("decision", {}),
                        cleaned_user_message,
                    )
                    yield OrchestratorResponse(
                        session_id=self.session.id,
                        phase="generation",
                        message=message,
                        is_complete=True,
                        progress=100,
                        action="multipage_suggested",
                    )
                    emitter.emit(DoneEvent(summary="complete", token_usage=summary))
                    return
                summary = self._token_summary()
                yield OrchestratorResponse(
                    session_id=self.session.id,
                    phase="generation",
                    message=self._generation_complete_message(cleaned_user_message),
                    is_complete=True,
                    preview_html=pipeline_result.get("preview_html"),
                    active_page_slug=pipeline_result.get("active_page_slug"),
                    progress=100,
                    action="pages_generated",
                )
                emitter.emit(DoneEvent(summary="complete", token_usage=summary))
                return

            if route_result.route == "refinement":
                refinement_agent = RefinementAgent(
                    self.db,
                    self.session.id,
                    self.settings,
                    event_emitter=emitter,
                    agent_id="refinement_1",
                )
                target_page = route_result.target_page
                if target_page is None:
                    if refinement_agent.is_global_change(cleaned_user_message) and state.pages:
                        global_style = self._extract_global_style(state.product_doc)
                        batch_result = await refinement_agent.batch_refine(
                            session_id=self.session.id,
                            pages=state.pages,
                            user_message=cleaned_user_message,
                            product_doc=state.product_doc,
                            global_style=global_style,
                            history=list(history),
                        )
                        preview_html, active_slug = self._select_preview_from_batch(batch_result, state.pages)
                        try:
                            self.db.commit()
                        except Exception:
                            self.db.rollback()
                        summary = self._token_summary()
                        yield OrchestratorResponse(
                            session_id=self.session.id,
                            phase="refinement",
                            message=self._batch_refinement_message(batch_result, state.pages, cleaned_user_message),
                            is_complete=True,
                            preview_html=preview_html,
                            progress=100,
                            action="page_refined",
                            active_page_slug=active_slug,
                        )
                        emitter.emit(DoneEvent(summary="complete", token_usage=summary))
                        return

                    disambiguation = route_result.disambiguation
                    yield OrchestratorResponse(
                        session_id=self.session.id,
                        phase="refinement",
                        message=disambiguation.message if disambiguation else self._missing_page_message(cleaned_user_message),
                        is_complete=True,
                        action="direct_reply",
                    )
                    emitter.emit(DoneEvent(summary="complete", token_usage=self._token_summary()))
                    return

                current_html = self._get_latest_page_html(target_page)
                if not current_html:
                    current_html = self._get_latest_html() or ""

                global_style = self._extract_global_style(state.product_doc)
                result = await refinement_agent.refine(
                    user_message=cleaned_user_message,
                    page=target_page,
                    product_doc=state.product_doc,
                    global_style=global_style,
                    all_pages=state.pages,
                    current_html=current_html,
                    output_dir=output_dir,
                    history=list(history),
                )
                try:
                    self.db.commit()
                except Exception:
                    self.db.rollback()
                preview_url = result.preview_url if target_page.slug == "index" else None
                summary = self._token_summary()
                yield OrchestratorResponse(
                    session_id=self.session.id,
                    phase="refinement",
                    message="Refinement complete",
                    is_complete=True,
                    preview_url=preview_url,
                    preview_html=result.html,
                    progress=100,
                    action="page_refined",
                    active_page_slug=target_page.slug,
                )
                emitter.emit(DoneEvent(summary="complete", token_usage=summary))
                return

            message = self._direct_reply_message(cleaned_user_message)
            summary = self._token_summary()
            yield OrchestratorResponse(
                session_id=self.session.id,
                phase="direct_reply",
                message=message,
                is_complete=True,
                progress=100,
                action="direct_reply",
            )
            emitter.emit(DoneEvent(summary="complete", token_usage=summary))
        except Exception as exc:
            logger.exception("Orchestrator failed")
            emitter.emit(ErrorEvent(message="Orchestrator failed", details=str(exc)))
            emitter.emit(DoneEvent(summary="failed", token_usage=self._token_summary()))
            raise

    def _generation_complete_message(self, user_message: str) -> str:
        return "Pages generated successfully."

    def _regeneration_complete_message(self, user_message: str) -> str:
        return "Pages regenerated successfully."

    def _multipage_suggestion_message(self, decision: dict, user_message: str) -> str:
        reasons = decision.get("reasons") if isinstance(decision, dict) else None
        reasons_text = ""
        if isinstance(reasons, list) and reasons:
            reasons_text = "Reasons: " + "; ".join(str(item) for item in reasons)
        prompt = "I suggest a multi-page site. Reply “multi page” to proceed or “single page” to merge into one."
        return "\n".join([item for item in [reasons_text, prompt] if item])

    def _missing_product_doc_message(self, user_message: str) -> str:
        return "I couldn't find a product doc yet. I'll generate a draft first."

    def _missing_page_message(self, user_message: str) -> str:
        return "I couldn't determine which page to refine. Please specify the page name."

    def _direct_reply_message(self, user_message: str) -> str:
        return "I can update the product doc or refine a specific page. Tell me what you'd like to change."

    def _append_regeneration_prompt(self, message: str, user_message: str) -> str:
        prompt = "Product doc updated. Regenerate the affected pages?"
        if prompt in message:
            return message
        if "regenerate" in message.lower():
            return message
        return f"{message}\n\n{prompt}".strip()

    def _pending_regeneration_pages(self, product_doc: ProductDoc | None) -> list[str]:
        if product_doc is None:
            return []
        pages = getattr(product_doc, "pending_regeneration_pages", None)
        if not isinstance(pages, list):
            return []
        resolved: list[str] = []
        for item in pages:
            slug = str(item or "").strip()
            if slug:
                resolved.append(slug)
        return resolved

    def _resolve_regeneration_targets(
        self,
        target_slugs: Optional[list[str]],
        all_slugs: list[str],
    ) -> list[str]:
        if not target_slugs:
            return []
        normalized = {str(slug).strip() for slug in target_slugs if str(slug or "").strip()}
        if not normalized:
            return []
        selected = [slug for slug in all_slugs if slug in normalized]
        return selected or []

    async def _run_generation_pipeline(
        self,
        *,
        product_doc: ProductDoc,
        output_dir: str,
        history: Sequence[dict],
        user_message: str,
        emitter: EventEmitter,
        target_slugs: Optional[list[str]] = None,
        page_mode_override: Optional[str] = None,
        allow_defer_on_suggest: bool = False,
    ) -> dict:
        decider = AutoMultiPageDecider(event_emitter=emitter)
        decision = None
        if not page_mode_override:
            decision = decider.decide(product_doc)

        if page_mode_override == "single":
            multi_page = False
        elif page_mode_override == "multi":
            multi_page = True
        else:
            multi_page = decision.decision in {"multi_page", "suggest_multi_page"} if decision else False

        if allow_defer_on_suggest and decision and decision.decision == "suggest_multi_page":
            return {
                "deferred": True,
                "decision": decision.to_dict(),
            }

        sitemap_agent = SitemapAgent(
            self.db,
            self.session.id,
            self.settings,
            event_emitter=emitter,
            agent_id="sitemap_1",
        )
        sitemap_result = await sitemap_agent.generate(
            product_doc,
            multi_page=multi_page,
            explicit_multi_page=page_mode_override == "multi",
        )

        page_service = PageService(self.db, event_emitter=emitter)
        page_by_slug = self._sync_pages_with_sitemap(
            page_service=page_service,
            sitemap_pages=sitemap_result.pages,
        )
        self.db.commit()

        def _dump_model(value: object) -> object:
            if hasattr(value, "model_dump"):
                return value.model_dump()  # type: ignore[return-value]
            if hasattr(value, "dict"):
                return value.dict()  # type: ignore[return-value]
            return value

        nav_payload = [_dump_model(item) for item in sitemap_result.nav]
        global_style_payload = _dump_model(sitemap_result.global_style)
        all_pages = [getattr(page_spec, "slug", None) or "index" for page_spec in sitemap_result.pages]
        selected_slugs = self._resolve_regeneration_targets(target_slugs, all_pages)
        product_doc_context = self._build_product_doc_context(product_doc)

        tasks_payload: list[dict] = []
        generation_task_ids: list[str] = []
        validator_task_ids: list[str] = []
        page_payloads: list[dict] = []
        for page_spec in sitemap_result.pages:
            slug = getattr(page_spec, "slug", None) or ""
            if selected_slugs and slug not in selected_slugs:
                continue
            page = page_by_slug.get(slug)
            if page is None:
                continue
            page_spec_payload = _dump_model(page_spec)
            requirements = self._build_page_requirements(
                user_message=user_message,
                product_doc_context=product_doc_context,
                page_spec=page_spec_payload if isinstance(page_spec_payload, dict) else {},
                nav=nav_payload,
                global_style=global_style_payload if isinstance(global_style_payload, dict) else {},
            )
            payload = {
                "page_id": page.id,
                "page_spec": page_spec_payload,
                "nav": nav_payload,
                "global_style": global_style_payload,
                "all_pages": all_pages,
                "requirements": requirements,
            }
            title = getattr(page_spec, "title", None) or slug or "Page"
            task_id = uuid4().hex
            tasks_payload.append(
                {
                    "id": task_id,
                    "title": f"Generate {title}",
                    "description": json.dumps(payload, ensure_ascii=False),
                    "depends_on": [],
                    "can_parallel": True,
                    "agent_type": "generation",
                }
            )
            generation_task_ids.append(task_id)
            page_payloads.append(
                {
                    "page_id": page.id,
                    "slug": slug or "index",
                }
            )

        for page_payload, gen_task_id in zip(page_payloads, generation_task_ids):
            validator_task_id = uuid4().hex
            tasks_payload.append(
                {
                    "id": validator_task_id,
                    "title": f"Validate {page_payload.get('slug')}",
                    "description": json.dumps(page_payload, ensure_ascii=False),
                    "depends_on": [gen_task_id],
                    "can_parallel": True,
                    "agent_type": "validator",
                }
            )
            validator_task_ids.append(validator_task_id)

        export_payload = {
            "mode": "multi_page",
            "pages": page_payloads,
            "global_style": global_style_payload,
        }
        export_depends_on = validator_task_ids or generation_task_ids
        if export_depends_on:
            tasks_payload.append(
                {
                    "id": uuid4().hex,
                    "title": "Export site",
                    "description": json.dumps(export_payload, ensure_ascii=False),
                    "depends_on": export_depends_on,
                    "can_parallel": False,
                    "agent_type": "export",
                }
            )

        if not tasks_payload:
            return {"preview_html": None, "active_page_slug": None}

        plan_service = PlanService(self.db)
        plan_goal = self._build_plan_goal(product_doc)
        plan = plan_service.create_plan(
            session_id=self.session.id,
            goal=plan_goal,
            tasks=tasks_payload,
        )
        emitter.emit(
            PlanCreatedEvent(
                plan={
                    "id": plan.id,
                    "goal": plan.goal,
                    "tasks": tasks_payload,
                }
            )
        )
        self.db.commit()

        executor = ParallelExecutor(
            db=self.db,
            plan=plan,
            emitter=emitter,
            settings=self.settings,
            output_dir=output_dir,
            user_message=user_message,
            history=list(history),
            max_concurrent=self.settings.max_concurrent_tasks,
        )
        manager = ExecutorManager.get_instance()
        manager.register(plan.id, executor)
        try:
            async for _event in executor.execute():
                pass
        finally:
            manager.unregister(plan.id)
        self.db.commit()

        preview_html, active_page_slug = self._select_preview_from_pages(
            page_by_slug,
            selected_slugs or all_pages,
        )
        return {
            "preview_html": preview_html,
            "active_page_slug": active_page_slug,
        }


__all__ = ["AgentOrchestrator", "OrchestratorResponse", "RouteResult", "SessionState"]
