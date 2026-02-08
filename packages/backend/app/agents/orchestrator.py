from __future__ import annotations

import asyncio
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
from ..schemas.style_reference import StyleReference, StyleScope
from ..services.plan import PlanService
from ..services.page import PageService
from ..services.page_version import PageVersionService
from ..services.product_doc import ProductDocService
from ..services.skills import load_style_profiles, route_style_profile
from ..services.style_reference import (
    StyleReferenceService,
    merge_style_tokens,
    normalize_style_tokens,
    tokens_to_global_style,
)
from ..services.token_tracker import TokenTrackerService
from ..services.version import VersionService
from ..executor.manager import ExecutorManager
from ..executor.parallel import ParallelExecutor
from .base import AgentResult
from .generation import GenerationAgent
from .expander import ExpanderAgent
from .interview import InterviewAgent
from .intent_classifier import IntentClassifier
from .multipage_decider import AutoMultiPageDecider
from .orchestrator_routing import OrchestratorRouter, RoutingDecision
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
    "\u4ea7\u54c1\u6587\u6863",
    "\u9700\u6c42\u6587\u6863",
    "\u9700\u6c42",
    "\u529f\u80fd\u9700\u6c42",
    "\u9875\u9762\u7ed3\u6784",
    "\u9875\u9762\u89c4\u5212",
    "\u7ad9\u70b9\u5730\u56fe",
    "\u65b0\u589e\u9875\u9762",
    "\u6dfb\u52a0\u9875\u9762",
    "\u5220\u9664\u9875\u9762",
    "\u4fee\u6539\u9875\u9762",
    "\u8bbe\u8ba1\u65b9\u5411",
    "\u8bbe\u8ba1\u98ce\u683c",
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
    "regenerate",
    "go ahead",
    "\u786e\u8ba4",
    "\u5f00\u59cb",
    "\u5f00\u59cb\u751f\u6210",
    "\u751f\u6210",
    "\u7ee7\u7eed",
    "\u53ef\u4ee5",
    "\u597d",
    "\u6ca1\u95ee\u9898",
    "\u76f4\u63a5\u751f\u6210",
    "\u5f00\u59cb\u6784\u5efa",
    "\u91cd\u65b0\u751f\u6210",
]

PAGE_REFINEMENT_KEYWORDS = [
    "change",
    "modify",
    "update",
    "adjust",
    "fix",
    "\u4fee\u6539",
    "\u8c03\u6574",
    "\u66f4\u65b0",
    "\u4fee\u590d",
    "\u4f18\u5316",
]

INTENT_FALLBACK_MIN_CONFIDENCE = 0.55

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
        self._router = OrchestratorRouter(
            db=self.db,
            session_id=self.session.id,
            settings=self.settings,
        )
        self._routing_decision: RoutingDecision | None = None

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

    def _normalize_target_pages(self, targets: Optional[list[str]]) -> list[str]:
        if not targets:
            return []
        resolved: list[str] = []
        seen = set()
        for item in targets:
            slug = str(item or "").strip()
            if not slug or slug in seen:
                continue
            resolved.append(slug)
            seen.add(slug)
        return resolved

    def _resolve_target_pages(
        self,
        explicit_targets: Optional[list[str]],
        routing_decision: RoutingDecision | None,
    ) -> list[str]:
        resolved = self._normalize_target_pages(explicit_targets)
        if resolved:
            return resolved
        if routing_decision and routing_decision.target_pages:
            return self._normalize_target_pages(routing_decision.target_pages)
        return []

    def _schema_contains_key(self, value: object, keys: set[str]) -> bool:
        if isinstance(value, dict):
            for key, item in value.items():
                if str(key).lower() in keys:
                    return True
                if self._schema_contains_key(item, keys):
                    return True
        if isinstance(value, list):
            return any(self._schema_contains_key(item, keys) for item in value)
        return False

    def _should_expand(self, product_doc: ProductDoc | None) -> bool:
        if product_doc is None:
            return False
        structured = getattr(product_doc, "structured", None)
        if not isinstance(structured, dict):
            return False
        product_type = str(structured.get("product_type") or "").strip().lower()
        pages = structured.get("pages") if isinstance(structured.get("pages"), list) else []
        data_flow = structured.get("data_flow") if isinstance(structured.get("data_flow"), list) else []
        component_inventory = (
            structured.get("component_inventory") if isinstance(structured.get("component_inventory"), list) else []
        )
        state_contract = structured.get("state_contract") if isinstance(structured.get("state_contract"), dict) else {}

        if product_type in {"ecommerce", "travel", "manual", "kanban", "booking", "dashboard"}:
            return True
        if len(pages) > 1:
            return True
        if data_flow:
            return True
        if len(component_inventory) >= 6:
            return True
        schema = state_contract.get("schema") if isinstance(state_contract, dict) else None
        if schema and self._schema_contains_key(schema, {"cart", "draft"}):
            return True
        return False

    def _should_expand_page(self, page_spec: object, *, page_index: int, total_pages: int) -> bool:
        if total_pages <= 1:
            return True
        slug = getattr(page_spec, "slug", None) or ""
        if slug == "index":
            return False
        return page_index > 0

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
            "start building",
        ]
        chinese_keywords = [
            "\u91cd\u65b0\u751f\u6210",
            "\u91cd\u65b0\u5f00\u59cb",
            "\u4ece\u5934\u751f\u6210",
            "\u4ece\u5934\u5f00\u59cb",
            "\u91cd\u65b0\u6784\u5efa",
            "\u91cd\u505a",
            "\u518d\u751f\u6210",
            "\u91cd\u65b0\u505a",
        ]
        if any(keyword in lower for keyword in english_keywords):
            return True
        if any(keyword in message for keyword in chinese_keywords):
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
            "\u5355\u9875",
            "\u5355\u9875\u9762",
            "\u4e00\u4e2a\u9875\u9762",
            "\u5408\u5e76\u6210\u4e00\u4e2a\u9875\u9762",
            "\u5408\u5e76\u4e3a\u4e00\u4e2a\u9875\u9762",
            "\u5408\u5e76\u4e3a\u5355\u9875",
            "\u5355\u9875\u6a21\u5f0f",
        ]
        multi_keywords = [
            "multi page",
            "multi-page",
            "multiple pages",
            "multi pages",
            "separate pages",
            "split into pages",
            "\u591a\u9875",
            "\u591a\u9875\u9762",
            "\u591a\u4e2a\u9875\u9762",
            "\u5206\u6210\u591a\u4e2a\u9875\u9762",
            "\u62c6\u5206\u9875\u9762",
            "\u62c6\u6210\u591a\u4e2a\u9875\u9762",
            "\u591a\u9875\u6a21\u5f0f",
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

    def _build_style_router_text(self, user_message: str, product_doc: ProductDoc | None) -> str:
        parts = [user_message or ""]
        if product_doc is not None:
            structured = getattr(product_doc, "structured", None)
            if isinstance(structured, dict):
                design = structured.get("design_direction") or structured.get("designDirection") or {}
                if isinstance(design, dict):
                    style = design.get("style")
                    tone = design.get("tone")
                    color_pref = design.get("color_preference") or design.get("colorPreference")
                    if style:
                        parts.append(str(style))
                    if tone:
                        parts.append(str(tone))
                    if color_pref:
                        parts.append(str(color_pref))
        return " ".join(part for part in parts if part)

    def _resolve_style_profile_tokens(
        self,
        user_message: str,
        product_doc: ProductDoc | None,
        *,
        profile_id_override: Optional[str] = None,
        allowed_profiles: Optional[list[str]] = None,
    ) -> tuple[str, dict]:
        router_text = self._build_style_router_text(user_message, product_doc)
        profile_id = profile_id_override or route_style_profile(router_text)
        profiles = load_style_profiles()
        if allowed_profiles and profile_id not in allowed_profiles:
            profile_id = allowed_profiles[0] if allowed_profiles else profile_id
        profile = profiles.get(profile_id) or profiles.get("clean-modern") or next(iter(profiles.values()), None)
        if profile is None:
            return profile_id, {}
        return profile_id, normalize_style_tokens(profile.tokens)

    def _fallback_interview_result(self, reason: str) -> AgentResult:
        hint = "timed out" if reason == "timeout" else "hit an error"
        message = (
            "I ran into an issue while preparing the interview "
            f"({hint}). Please answer these quick questions so I can continue:"
        )
        questions = [
            {
                "id": "goal",
                "type": "text",
                "title": "What is the primary goal of this page?",
                "placeholder": "e.g., collect leads, sell a product, announce an event",
            },
            {
                "id": "audience",
                "type": "text",
                "title": "Who is the target audience?",
                "placeholder": "e.g., busy professionals, students, coffee lovers",
            },
            {
                "id": "style",
                "type": "text",
                "title": "What style or brand cues should I follow?",
                "placeholder": "e.g., clean, bold, minimal; colors or fonts you prefer",
            },
            {
                "id": "sections",
                "type": "text",
                "title": "What key sections should the page include?",
                "placeholder": "e.g., hero, features, testimonials, CTA",
            },
        ]
        return AgentResult(message=message, is_complete=False, confidence=0.0, questions=questions)

    async def _resolve_style_context(
        self,
        *,
        style_reference: Optional[dict],
        user_message: str,
        target_pages: Optional[list[str]],
        product_doc: ProductDoc | None,
        profile_id_override: Optional[str] = None,
        allowed_profiles: Optional[list[str]] = None,
    ) -> Optional[dict]:
        profile_id, profile_tokens = self._resolve_style_profile_tokens(
            user_message,
            product_doc,
            profile_id_override=profile_id_override,
            allowed_profiles=allowed_profiles,
        )
        reference_tokens: Optional[dict] = None
        scope = StyleScope()

        if style_reference:
            try:
                style_ref = StyleReference.model_validate(style_reference)
                scope = style_ref.scope
                if style_ref.tokens is not None:
                    reference_tokens = normalize_style_tokens(style_ref.tokens.model_dump())
                elif style_ref.images:
                    resolved_product_type = None
                    if product_doc is not None:
                        resolved_product_type = getattr(product_doc, "product_type", None)
                    if resolved_product_type is None:
                        resolved_product_type = getattr(self.session, "product_type", None)
                    service = StyleReferenceService(
                        settings=self.settings,
                        product_type=resolved_product_type,
                    )
                    extracted = await service.extract_style(
                        style_ref.images,
                        mode=style_ref.mode,
                        product_type=resolved_product_type,
                    )
                    if extracted is not None:
                        reference_tokens = normalize_style_tokens(extracted.model_dump())
            except Exception as exc:
                logger.warning("Failed to resolve style reference context: %s", exc)

        merged_tokens = merge_style_tokens(profile_tokens, reference_tokens)
        if not merged_tokens:
            return None

        resolved_product_type = None
        if product_doc is not None:
            resolved_product_type = getattr(product_doc, "product_type", None)
        if resolved_product_type is None:
            resolved_product_type = getattr(self.session, "product_type", None)
        service = StyleReferenceService(settings=self.settings, product_type=resolved_product_type)

        tokens_by_page: dict[str, dict] = {}
        if profile_tokens:
            tokens_by_page["*"] = profile_tokens

        unscoped_reference_tokens = None
        if reference_tokens:
            scoped_reference = service.apply_scope(reference_tokens, scope, target_pages)
            if scoped_reference:
                for page, scoped_tokens in scoped_reference.items():
                    tokens_by_page[page] = merge_style_tokens(profile_tokens, scoped_tokens)
            elif scope.type == "model_decide" and not target_pages:
                unscoped_reference_tokens = reference_tokens

        return {
            "profile_id": profile_id,
            "tokens": merged_tokens,
            "tokens_by_page": tokens_by_page,
            "unscoped_reference_tokens": unscoped_reference_tokens,
            "scope": scope.model_dump(),
        }

    def _merge_global_style(self, base: dict, style_tokens: Optional[dict]) -> dict:
        if not style_tokens:
            return base
        override = tokens_to_global_style(style_tokens)
        if not override:
            return base
        merged = dict(base)
        merged.update({k: v for k, v in override.items() if v is not None})
        return merged

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
        style_tokens: Optional[dict] = None,
        unscoped_style_tokens: Optional[dict] = None,
        expansion_notes: Optional[str] = None,
    ) -> str:
        base = user_message.strip() if user_message else ""
        if style_tokens:
            style_payload = json.dumps(style_tokens, ensure_ascii=False, indent=2)
            if base:
                base = f"{base}\n\nStyle Tokens (scoped):\n{style_payload}"
            else:
                base = f"Style Tokens (scoped):\n{style_payload}"
        if unscoped_style_tokens:
            style_payload = json.dumps(unscoped_style_tokens, ensure_ascii=False, indent=2)
            if base:
                base = f"{base}\n\nStyle Tokens (model decide):\n{style_payload}"
            else:
                base = f"Style Tokens (model decide):\n{style_payload}"
        if expansion_notes:
            if base:
                base = f"{base}\n\nExpansion Notes:\n{expansion_notes}"
            else:
                base = f"Expansion Notes:\n{expansion_notes}"
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

    async def _resolve_routing_decision(
        self,
        *,
        user_message: str,
        target_pages: Optional[list[str]],
        state: SessionState,
    ) -> RoutingDecision | None:
        try:
            decision = await self._router.route(
                user_message,
                project_pages=state.pages,
                explicit_targets=target_pages,
                product_doc=state.product_doc,
                session=self.session,
            )
        except Exception:
            logger.exception("Failed to resolve routing decision")
            return None

        if decision:
            self._routing_decision = decision
            self._apply_routing_metadata(decision)
        return decision

    def _apply_routing_metadata(self, decision: RoutingDecision) -> None:
        if decision.product_type and decision.product_type != "unknown":
            self.session.product_type = decision.product_type
        if decision.complexity and decision.complexity != "unknown":
            self.session.complexity = decision.complexity
        if decision.skill_id:
            self.session.skill_id = decision.skill_id
        if decision.doc_tier:
            self.session.doc_tier = decision.doc_tier
        if decision.model_prefs:
            self.session.model_classifier = decision.model_prefs.get("classifier") or self.session.model_classifier
            self.session.model_writer = decision.model_prefs.get("writer") or self.session.model_writer
            self.session.model_expander = decision.model_prefs.get("expander") or self.session.model_expander
            self.session.model_validator = decision.model_prefs.get("validator") or self.session.model_validator
            self.session.model_style_refiner = decision.model_prefs.get("style_refiner") or self.session.model_style_refiner
        try:
            self.db.add(self.session)
            self.db.commit()
        except Exception:
            logger.exception("Failed to persist routing metadata")

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

    async def _llm_intent_fallback(
        self,
        message: str,
        state: SessionState,
        *,
        generate_now: bool,
        page_mode_override: Optional[str],
    ) -> RouteResult | None:
        if not message:
            return None

        classifier = IntentClassifier(
            self.db,
            self.session.id,
            self.settings,
        )
        result = await classifier.classify(message, pages=state.pages, product_doc=state.product_doc)
        if result.confidence < INTENT_FALLBACK_MIN_CONFIDENCE:
            return None

        intent = result.intent
        if intent == "product_doc_update":
            return RouteResult(
                route="product_doc_update",
                generate_now=generate_now,
                page_mode_override=page_mode_override,
            )
        if intent == "generation_pipeline":
            return RouteResult(
                route="generation_pipeline",
                generate_now=generate_now,
                page_mode_override=page_mode_override,
            )
        if intent != "page_refine":
            return None

        if not state.has_pages:
            return RouteResult(
                route="generation_pipeline",
                generate_now=generate_now,
                page_mode_override=page_mode_override,
            )

        refinement_agent = RefinementAgent(
            self.db,
            self.session.id,
            self.settings,
            event_emitter=self.event_emitter,
            agent_id="refinement_1",
        )

        if result.target_pages:
            slug_map: dict[str, Page] = {}
            for page in state.pages:
                slug = str(page.slug or "").strip()
                if slug:
                    slug_map[slug.lower()] = page
            resolved = []
            for slug in result.target_pages:
                page = slug_map.get(str(slug).lower())
                if page and page not in resolved:
                    resolved.append(page)
            if len(resolved) == 1:
                return RouteResult(route="refinement", target_page=resolved[0], generate_now=generate_now)
            if resolved:
                return RouteResult(
                    route="refinement",
                    disambiguation=DisambiguationResult(
                        candidates=resolved,
                        message=refinement_agent._format_disambiguation_message(resolved),
                    ),
                    generate_now=generate_now,
                )

        detection = await refinement_agent.detect_target_page(message, state.pages)
        if isinstance(detection, Page):
            return RouteResult(route="refinement", target_page=detection, generate_now=generate_now)
        return RouteResult(route="refinement", disambiguation=detection, generate_now=generate_now)

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

        if state.has_pages and self._wants_new_generation(cleaned_message):
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

        llm_route = await self._llm_intent_fallback(
            cleaned_message,
            state,
            generate_now=generate_now,
            page_mode_override=page_mode_override,
        )
        if llm_route is not None:
            return llm_route

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
        style_reference: Optional[dict] = None,
        target_pages: Optional[list[str]] = None,
        resume: Optional[dict] = None,
    ) -> AsyncGenerator[OrchestratorResponse, None]:
        _ = resume
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
            try:
                timeout_seconds = float(getattr(self.settings, "interview_timeout_seconds", 0.0) or 0.0)
                if timeout_seconds > 0:
                    interview_result = await asyncio.wait_for(
                        interview.process(user_message, history=history),
                        timeout=timeout_seconds,
                    )
                else:
                    interview_result = await interview.process(user_message, history=history)
            except asyncio.TimeoutError:
                timeout_value = getattr(self.settings, "interview_timeout_seconds", None)
                logger.warning("Interview agent timed out after %ss", timeout_value)
                emitter.emit(
                    ErrorEvent(
                        message="Interview agent timed out",
                        details=f"timeout_after={timeout_value}s",
                    )
                )
                interview_result = self._fallback_interview_result("timeout")
            except Exception as exc:
                logger.warning("Interview agent failed: %s", exc)
                emitter.emit(
                    ErrorEvent(
                        message="Interview agent failed",
                        details=str(exc),
                    )
                )
                interview_result = self._fallback_interview_result("error")
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

        routing_decision = await self._resolve_routing_decision(
            user_message=cleaned_user_message or user_message,
            target_pages=target_pages,
            state=state,
        )
        resolved_targets = self._resolve_target_pages(target_pages, routing_decision)
        guardrails = routing_decision.guardrails if routing_decision else None
        style_profile_override = routing_decision.style_profile if routing_decision else None

        route_result = await self.route(
            cleaned_user_message,
            self.session,
            generate_now=resolved_generate_now,
        )

        try:
            if route_result.route in ("product_doc_generation", "product_doc_generation_generate_now"):
                style_context = await self._resolve_style_context(
                    style_reference=style_reference,
                    user_message=cleaned_user_message or user_message,
                    target_pages=resolved_targets,
                    product_doc=None,
                    profile_id_override=style_profile_override,
                )
                style_tokens = style_context.get("tokens") if style_context else None
                product_doc_agent = ProductDocAgent(
                    self.db,
                    self.session.id,
                    self.settings,
                    event_emitter=emitter,
                    agent_id="product_doc_1",
                )
                try:
                    timeout_seconds = float(
                        getattr(self.settings, "product_doc_timeout_seconds", 0.0) or 0.0
                    )
                    if timeout_seconds > 0:
                        result = await asyncio.wait_for(
                            product_doc_agent.generate(
                                session_id=self.session.id,
                                user_message=cleaned_user_message or user_message,
                                interview_context=interview_context,
                                history=history,
                                style_tokens=style_tokens,
                                guardrails=guardrails,
                            ),
                            timeout=timeout_seconds,
                        )
                    else:
                        result = await product_doc_agent.generate(
                            session_id=self.session.id,
                            user_message=cleaned_user_message or user_message,
                            interview_context=interview_context,
                            history=history,
                            style_tokens=style_tokens,
                            guardrails=guardrails,
                        )
                except asyncio.TimeoutError:
                    timeout_value = getattr(self.settings, "product_doc_timeout_seconds", None)
                    logger.warning("Product doc generation timed out after %ss", timeout_value)
                    emitter.emit(
                        ErrorEvent(
                            message="Product doc generation timed out",
                            details=f"timeout_after={timeout_value}s",
                        )
                    )
                    summary = self._token_summary()
                    yield OrchestratorResponse(
                        session_id=self.session.id,
                        phase="product_doc",
                        message="Product doc generation is taking too long. Please retry or shorten the request.",
                        is_complete=True,
                        action="direct_reply",
                    )
                    emitter.emit(DoneEvent(summary="product_doc_timeout", token_usage=summary))
                    return
                except Exception as exc:
                    logger.warning("Product doc generation failed: %s", exc)
                    emitter.emit(
                        ErrorEvent(
                            message="Product doc generation failed",
                            details=str(exc),
                        )
                    )
                    summary = self._token_summary()
                    yield OrchestratorResponse(
                        session_id=self.session.id,
                        phase="product_doc",
                        message="Product doc generation failed. Please try again.",
                        is_complete=True,
                        action="direct_reply",
                    )
                    emitter.emit(DoneEvent(summary="product_doc_failed", token_usage=summary))
                    return
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
                            target_slugs=resolved_targets or None,
                            page_mode_override=route_result.page_mode_override,
                            allow_defer_on_suggest=not route_result.generate_now and not state.has_pages,
                            style_context=style_context,
                            guardrails=guardrails,
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

                style_context = None
                if style_reference:
                    style_context = await self._resolve_style_context(
                        style_reference=style_reference,
                        user_message=cleaned_user_message or user_message,
                        target_pages=resolved_targets,
                        product_doc=product_doc,
                        profile_id_override=style_profile_override,
                    )
                style_tokens = style_context.get("tokens") if style_context else None

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
                try:
                    timeout_seconds = float(
                        getattr(self.settings, "product_doc_timeout_seconds", 0.0) or 0.0
                    )
                    if timeout_seconds > 0:
                        update_result = await asyncio.wait_for(
                            product_doc_agent.update(
                                session_id=self.session.id,
                                current_doc=product_doc,
                                user_message=update_message,
                                history=history,
                                style_tokens=style_tokens,
                                guardrails=guardrails,
                            ),
                            timeout=timeout_seconds,
                        )
                    else:
                        update_result = await product_doc_agent.update(
                            session_id=self.session.id,
                            current_doc=product_doc,
                            user_message=update_message,
                            history=history,
                            style_tokens=style_tokens,
                            guardrails=guardrails,
                        )
                except asyncio.TimeoutError:
                    timeout_value = getattr(self.settings, "product_doc_timeout_seconds", None)
                    logger.warning("Product doc update timed out after %ss", timeout_value)
                    emitter.emit(
                        ErrorEvent(
                            message="Product doc update timed out",
                            details=f"timeout_after={timeout_value}s",
                        )
                    )
                    summary = self._token_summary()
                    yield OrchestratorResponse(
                        session_id=self.session.id,
                        phase="product_doc",
                        message="Product doc update is taking too long. Please retry.",
                        is_complete=True,
                        action="direct_reply",
                    )
                    emitter.emit(DoneEvent(summary="product_doc_timeout", token_usage=summary))
                    return
                except Exception as exc:
                    logger.warning("Product doc update failed: %s", exc)
                    emitter.emit(
                        ErrorEvent(
                            message="Product doc update failed",
                            details=str(exc),
                        )
                    )
                    summary = self._token_summary()
                    yield OrchestratorResponse(
                        session_id=self.session.id,
                        phase="product_doc",
                        message="Product doc update failed. Please try again.",
                        is_complete=True,
                        action="direct_reply",
                    )
                    emitter.emit(DoneEvent(summary="product_doc_failed", token_usage=summary))
                    return
                if resolved_targets:
                    try:
                        service.set_pending_regeneration(product_doc.id, resolved_targets)
                        update_result.affected_pages = list(resolved_targets)
                    except Exception:
                        logger.exception("Failed to set pending regeneration targets")
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
                style_context = await self._resolve_style_context(
                    style_reference=style_reference,
                    user_message=cleaned_user_message or user_message,
                    target_pages=resolved_targets,
                    product_doc=product_doc,
                    profile_id_override=style_profile_override,
                )
                pending_pages = resolved_targets or self._pending_regeneration_pages(product_doc)
                pipeline_result = await self._run_generation_pipeline(
                    product_doc=product_doc,
                    output_dir=output_dir,
                    history=history,
                    user_message=cleaned_user_message,
                    emitter=emitter,
                    target_slugs=pending_pages,
                    page_mode_override=route_result.page_mode_override,
                    allow_defer_on_suggest=False,
                    style_context=style_context,
                    guardrails=guardrails,
                )
                if product_doc.status != ProductDocStatus.CONFIRMED:
                    try:
                        service.confirm(product_doc.id)
                        self.db.commit()
                    except Exception:
                        logger.exception("Failed to confirm ProductDoc after regeneration")
                if pending_pages:
                    try:
                        remaining_pages = []
                        if resolved_targets:
                            current_pending = self._pending_regeneration_pages(product_doc)
                            remaining_pages = [page for page in current_pending if page not in pending_pages]
                        service.set_pending_regeneration(product_doc.id, remaining_pages)
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
                style_context = await self._resolve_style_context(
                    style_reference=style_reference,
                    user_message=cleaned_user_message or user_message,
                    target_pages=resolved_targets,
                    product_doc=product_doc,
                    profile_id_override=style_profile_override,
                )
                pipeline_result = await self._run_generation_pipeline(
                    product_doc=product_doc,
                    output_dir=output_dir,
                    history=history,
                    user_message=cleaned_user_message,
                    emitter=emitter,
                    target_slugs=resolved_targets or None,
                    page_mode_override=route_result.page_mode_override,
                    allow_defer_on_suggest=not state.has_pages,
                    style_context=style_context,
                    guardrails=guardrails,
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
                style_context = await self._resolve_style_context(
                    style_reference=style_reference,
                    user_message=cleaned_user_message or user_message,
                    target_pages=resolved_targets,
                    product_doc=product_doc,
                    profile_id_override=style_profile_override,
                )
                pipeline_result = await self._run_generation_pipeline(
                    product_doc=product_doc,
                    output_dir=output_dir,
                    history=history,
                    user_message=cleaned_user_message,
                    emitter=emitter,
                    target_slugs=resolved_targets or None,
                    page_mode_override=route_result.page_mode_override,
                    allow_defer_on_suggest=not state.has_pages,
                    style_context=style_context,
                    guardrails=guardrails,
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
                if resolved_targets:
                    target_pages = [page for page in state.pages if page.slug in resolved_targets]
                    if len(target_pages) == 1:
                        route_result.target_page = target_pages[0]
                    elif len(target_pages) > 1:
                        global_style = self._extract_global_style(state.product_doc)
                        batch_result = await refinement_agent.batch_refine(
                            session_id=self.session.id,
                            pages=target_pages,
                            user_message=cleaned_user_message,
                            product_doc=state.product_doc,
                            global_style=global_style,
                            history=list(history),
                        )
                        preview_html, active_slug = self._select_preview_from_batch(batch_result, target_pages)
                        try:
                            self.db.commit()
                        except Exception:
                            self.db.rollback()
                        summary = self._token_summary()
                        yield OrchestratorResponse(
                            session_id=self.session.id,
                            phase="refinement",
                            message=self._batch_refinement_message(batch_result, target_pages, cleaned_user_message),
                            is_complete=True,
                            preview_html=preview_html,
                            progress=100,
                            action="page_refined",
                            active_page_slug=active_slug,
                        )
                        emitter.emit(DoneEvent(summary="complete", token_usage=summary))
                        return
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
        style_context: Optional[dict] = None,
        guardrails: Optional[dict] = None,
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
        style_tokens_by_page = {}
        if style_context and isinstance(style_context.get("tokens_by_page"), dict):
            style_tokens_by_page = style_context["tokens_by_page"]
        unscoped_reference_tokens = None
        if style_context and isinstance(style_context.get("unscoped_reference_tokens"), dict):
            unscoped_reference_tokens = style_context["unscoped_reference_tokens"]
        global_override = style_tokens_by_page.get("*") if isinstance(style_tokens_by_page, dict) else None
        if isinstance(global_style_payload, dict) and global_override:
            global_style_payload = self._merge_global_style(global_style_payload, global_override)
        all_pages = [getattr(page_spec, "slug", None) or "index" for page_spec in sitemap_result.pages]
        selected_slugs = self._resolve_regeneration_targets(target_slugs, all_pages)
        product_doc_context = self._build_product_doc_context(product_doc)

        expansion_notes_by_page: dict[str, str] = {}
        if self._should_expand(product_doc):
            expander = ExpanderAgent(
                self.db,
                self.session.id,
                self.settings,
                event_emitter=emitter,
                agent_id="expander_1",
            )
            total_pages = len(sitemap_result.pages)
            for idx, page_spec in enumerate(sitemap_result.pages):
                slug = getattr(page_spec, "slug", None) or "index"
                if selected_slugs and slug not in selected_slugs:
                    continue
                if not self._should_expand_page(page_spec, page_index=idx, total_pages=total_pages):
                    continue
                try:
                    notes = await expander.expand_page(
                        user_message=user_message,
                        page_spec=_dump_model(page_spec),
                        product_doc_context=product_doc_context,
                    )
                except Exception:
                    logger.exception("Expander failed for page %s", slug)
                    notes = ""
                if notes:
                    expansion_notes_by_page[slug] = notes

        tasks_payload: list[dict] = []
        generation_task_ids: list[str] = []
        validator_task_ids: list[str] = []
        page_payloads: list[dict] = []
        component_plan_task_id = uuid4().hex
        component_build_task_id = uuid4().hex

        structured = getattr(product_doc, "structured", None)
        if not isinstance(structured, dict):
            structured = {}
        design_direction = structured.get("design_direction")
        if not isinstance(design_direction, dict):
            design_direction = {}

        component_plan_payload = {
            "sitemap_pages": [_dump_model(item) for item in sitemap_result.pages],
            "design_direction": design_direction,
        }
        tasks_payload.append(
            {
                "id": component_plan_task_id,
                "title": "Plan components",
                "description": json.dumps(component_plan_payload, ensure_ascii=False),
                "depends_on": [],
                "can_parallel": True,
                "agent_type": "component_plan",
            }
        )
        component_build_payload = {
            "design_direction": design_direction,
        }
        tasks_payload.append(
            {
                "id": component_build_task_id,
                "title": "Build components",
                "description": json.dumps(component_build_payload, ensure_ascii=False),
                "depends_on": [component_plan_task_id],
                "can_parallel": True,
                "agent_type": "component_build",
            }
        )
        for page_spec in sitemap_result.pages:
            slug = getattr(page_spec, "slug", None) or ""
            if selected_slugs and slug not in selected_slugs:
                continue
            page = page_by_slug.get(slug)
            if page is None:
                continue
            page_spec_payload = _dump_model(page_spec)
            page_style_tokens = None
            if isinstance(style_tokens_by_page, dict):
                page_style_tokens = style_tokens_by_page.get(slug) or style_tokens_by_page.get("*")
            page_global_style = (
                self._merge_global_style(global_style_payload, page_style_tokens)
                if isinstance(global_style_payload, dict) and page_style_tokens
                else global_style_payload
            )
            expansion_notes = expansion_notes_by_page.get(slug)
            effective_unscoped = unscoped_reference_tokens
            requirements = self._build_page_requirements(
                user_message=user_message,
                product_doc_context=product_doc_context,
                page_spec=page_spec_payload if isinstance(page_spec_payload, dict) else {},
                nav=nav_payload,
                global_style=page_global_style if isinstance(page_global_style, dict) else {},
                style_tokens=page_style_tokens,
                unscoped_style_tokens=effective_unscoped,
                expansion_notes=expansion_notes,
            )
            payload = {
                "page_id": page.id,
                "page_spec": page_spec_payload,
                "nav": nav_payload,
                "global_style": page_global_style,
                "all_pages": all_pages,
                "requirements": requirements,
                "guardrails": guardrails or {},
            }
            title = getattr(page_spec, "title", None) or slug or "Page"
            task_id = uuid4().hex
            tasks_payload.append(
                {
                    "id": task_id,
                    "title": f"Generate {title}",
                    "description": json.dumps(payload, ensure_ascii=False),
                    "depends_on": [component_build_task_id],
                    "can_parallel": True,
                    "agent_type": "generation",
                }
            )
            generation_task_ids.append(task_id)
            page_payloads.append(
                {
                    "page_id": page.id,
                    "slug": slug or "index",
                    "guardrails": guardrails or {},
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
            task_timeout_seconds=self.settings.task_timeout_seconds,
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
