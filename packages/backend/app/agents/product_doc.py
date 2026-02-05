from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional, Sequence

from pydantic import ValidationError

from .base import BaseAgent
from .prompts import (
    PRODUCT_DOC_GENERATE_USER,
    PRODUCT_DOC_UPDATE_USER,
    get_product_doc_generate_prompt,
    get_product_doc_update_prompt,
)
from ..db.models import Session as SessionModel
from ..schemas.product_doc import (
    ProductDocChecklist,
    ProductDocExtended,
    ProductDocStandard,
    ProductDocStructured,
)
from ..services.product_doc import ProductDocService
from ..services.skills import SkillsRegistry
from ..llm.model_pool import FallbackTrigger, ModelRole
from ..utils.product_doc import extract_pages_from_markdown
from ..utils.guardrails import guardrails_to_prompt

logger = logging.getLogger(__name__)


@dataclass
class ProductDocGenerateResult:
    content: str
    structured: dict
    message: str
    tokens_used: int = 0

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "structured": self.structured,
            "message": self.message,
            "tokens_used": self.tokens_used,
        }


@dataclass
class ProductDocUpdateResult:
    content: str
    structured: dict
    change_summary: str
    affected_pages: List[str] = field(default_factory=list)
    message: str = ""
    tokens_used: int = 0

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "structured": self.structured,
            "change_summary": self.change_summary,
            "affected_pages": list(self.affected_pages),
            "message": self.message,
            "tokens_used": self.tokens_used,
        }


@dataclass
class _ParsedOutput:
    content: str = ""
    structured: dict = field(default_factory=dict)
    message: str = ""
    change_summary: str = ""
    affected_pages: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class ProductDocAgent(BaseAgent):
    agent_type = "product_doc"

    def __init__(
        self,
        db,
        session_id: str,
        settings,
        event_emitter=None,
        agent_id=None,
        task_id=None,
    ) -> None:
        super().__init__(
            db,
            session_id,
            settings,
            event_emitter=event_emitter,
            agent_id=agent_id,
            task_id=task_id,
            model_role=ModelRole.WRITER,
        )
        self.generate_prompt = get_product_doc_generate_prompt()
        self.update_prompt = get_product_doc_update_prompt()

    async def generate(
        self,
        session_id: Optional[str],
        user_message: str,
        interview_context: dict | None = None,
        history: Sequence[dict] | None = None,
        style_tokens: dict | None = None,
        guardrails: dict | None = None,
    ) -> ProductDocGenerateResult:
        resolved_session_id = session_id or self.session_id
        history = history or []
        product_type, complexity, doc_tier = self._resolve_routing_metadata(
            interview_context=interview_context,
            current_structured=None,
        )

        messages = self._build_generate_messages(
            user_message=user_message,
            interview_context=interview_context,
            history=history,
            product_type=product_type,
            complexity=complexity,
            doc_tier=doc_tier,
            style_tokens=style_tokens,
            guardrails=guardrails,
        )
        response = await self._call_llm(
            messages=messages,
            agent_type=self.agent_type,
            temperature=self.settings.temperature,
            max_tokens=self.settings.max_tokens,
            context="product-doc-generate",
            fallback_checker=self._build_fallback_checker(product_type),
        )
        tokens_used = response.token_usage.total_tokens if response.token_usage else 0

        parsed = self._parse_generate_response(
            response.content or "",
            user_message=user_message,
            interview_context=interview_context,
            product_type=product_type,
            complexity=complexity,
            doc_tier=doc_tier,
        )

        structured = self._ensure_index_page(parsed.structured, user_message=user_message)
        content = parsed.content or self._build_markdown(structured, user_message)
        message = parsed.message or self._default_message("generate", user_message)
        message = self._append_error_note(message, parsed.errors, user_message)

        if self.db is not None:
            service = ProductDocService(self.db, event_emitter=self.event_emitter)
            existing = service.get_by_session_id(resolved_session_id)
            if existing is None:
                service.create(resolved_session_id, content=content, structured=structured)
            else:
                service.update(existing.id, content=content, structured=structured)

        return ProductDocGenerateResult(
            content=content,
            structured=structured,
            message=message,
            tokens_used=tokens_used,
        )

    async def update(
        self,
        session_id: Optional[str],
        current_doc: Any,
        user_message: str,
        history: Sequence[dict] | None = None,
        style_tokens: dict | None = None,
        guardrails: dict | None = None,
    ) -> ProductDocUpdateResult:
        resolved_session_id = session_id or self.session_id
        history = history or []

        current_content = getattr(current_doc, "content", "") or ""
        current_structured = getattr(current_doc, "structured", None)
        if not isinstance(current_structured, dict):
            current_structured = {}
        product_type, complexity, doc_tier = self._resolve_routing_metadata(
            interview_context=None,
            current_structured=current_structured,
        )

        messages = self._build_update_messages(
            current_content=current_content,
            current_structured=current_structured,
            user_message=user_message,
            history=history,
            product_type=product_type,
            complexity=complexity,
            doc_tier=doc_tier,
            style_tokens=style_tokens,
            guardrails=guardrails,
        )
        response = await self._call_llm(
            messages=messages,
            agent_type=self.agent_type,
            temperature=self.settings.temperature,
            max_tokens=self.settings.max_tokens,
            context="product-doc-update",
            fallback_checker=self._build_fallback_checker(product_type),
        )
        tokens_used = response.token_usage.total_tokens if response.token_usage else 0

        parsed = self._parse_update_response(
            response.content or "",
            current_structured=current_structured,
            user_message=user_message,
            product_type=product_type,
            complexity=complexity,
            doc_tier=doc_tier,
        )

        structured = parsed.structured or current_structured
        content = parsed.content or current_content or self._build_markdown(structured, user_message)
        message = parsed.message or self._default_message("update", user_message)
        message = self._append_error_note(message, parsed.errors, user_message)

        change_summary = parsed.change_summary or self._default_change_summary(user_message)
        affected_pages = parsed.affected_pages or self._compute_affected_pages(
            current_structured,
            structured,
        )

        if self.db is not None:
            service = ProductDocService(self.db, event_emitter=self.event_emitter)
            doc_id = getattr(current_doc, "id", None)
            if doc_id:
                service.update(
                    doc_id,
                    content=content,
                    structured=structured,
                    change_summary=change_summary,
                    affected_pages=affected_pages,
                )
            else:
                existing = service.get_by_session_id(resolved_session_id)
                if existing is not None:
                    service.update(
                        existing.id,
                        content=content,
                        structured=structured,
                        change_summary=change_summary,
                        affected_pages=affected_pages,
                    )
                else:
                    service.create(resolved_session_id, content=content, structured=structured)

        return ProductDocUpdateResult(
            content=content,
            structured=structured,
            change_summary=change_summary,
            affected_pages=affected_pages,
            message=message,
            tokens_used=tokens_used,
        )

    def _build_generate_messages(
        self,
        *,
        user_message: str,
        interview_context: dict | None,
        history: Sequence[dict],
        product_type: str,
        complexity: str,
        doc_tier: str,
        style_tokens: dict | None,
        guardrails: dict | None,
    ) -> List[dict]:
        system_prompt = get_product_doc_generate_prompt(doc_tier=doc_tier)
        messages: List[dict] = [{"role": "system", "content": system_prompt}]
        guardrails_text = guardrails_to_prompt(guardrails)
        if guardrails_text:
            messages.append({"role": "system", "content": guardrails_text})
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

        interview_section = ""
        if interview_context:
            if isinstance(interview_context, dict):
                context_text = json.dumps(interview_context, ensure_ascii=False, indent=2)
            else:
                context_text = str(interview_context)
            interview_section = f"Interview Context:\n{context_text}"

        prompt = PRODUCT_DOC_GENERATE_USER.format(
            user_message=user_message.strip() or "No additional requirements provided.",
            interview_context_section=interview_section,
            product_type=product_type,
            complexity=complexity,
            doc_tier=doc_tier,
        ).strip()
        if style_tokens:
            style_section = json.dumps(style_tokens, ensure_ascii=False, indent=2)
            prompt = f"{prompt}\n\nStyle Reference Tokens:\n{style_section}"

        language_note = self._language_note(user_message, interview_section)
        if language_note:
            prompt = f"{prompt}\n\n{language_note}"
        messages.append({"role": "user", "content": prompt})
        return messages

    def _build_update_messages(
        self,
        *,
        current_content: str,
        current_structured: dict,
        user_message: str,
        history: Sequence[dict],
        product_type: str,
        complexity: str,
        doc_tier: str,
        style_tokens: dict | None,
        guardrails: dict | None,
    ) -> List[dict]:
        system_prompt = get_product_doc_update_prompt(doc_tier=doc_tier)
        messages: List[dict] = [{"role": "system", "content": system_prompt}]
        guardrails_text = guardrails_to_prompt(guardrails)
        if guardrails_text:
            messages.append({"role": "system", "content": guardrails_text})
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

        prompt = PRODUCT_DOC_UPDATE_USER.format(
            current_content=current_content or "(empty)",
            current_json=json.dumps(current_structured or {}, ensure_ascii=False, indent=2),
            user_message=user_message.strip() or "No change request provided.",
            product_type=product_type,
            complexity=complexity,
            doc_tier=doc_tier,
        ).strip()
        if style_tokens:
            style_section = json.dumps(style_tokens, ensure_ascii=False, indent=2)
            prompt = f"{prompt}\n\nStyle Reference Tokens:\n{style_section}"
        language_note = self._language_note(user_message, None)
        if language_note:
            prompt = f"{prompt}\n\n{language_note}"
        messages.append({"role": "user", "content": prompt})
        return messages

    def _resolve_routing_metadata(
        self,
        *,
        interview_context: dict | None,
        current_structured: dict | None,
    ) -> tuple[str, str, str]:
        product_type = None
        complexity = None
        doc_tier_override = None

        if isinstance(interview_context, dict):
            product_type = interview_context.get("product_type") or interview_context.get("productType")
            complexity = interview_context.get("complexity")
            doc_tier_override = interview_context.get("doc_tier") or interview_context.get("docTier")

        if isinstance(current_structured, dict):
            product_type = product_type or current_structured.get("product_type") or current_structured.get(
                "productType"
            )
            complexity = complexity or current_structured.get("complexity")
            if doc_tier_override is None:
                doc_tier_override = current_structured.get("doc_tier") or current_structured.get("docTier")

        if self.db is not None:
            session = self.db.get(SessionModel, self.session_id)
            if session is not None:
                product_type = product_type or session.product_type
                complexity = complexity or session.complexity
                if doc_tier_override is None:
                    doc_tier_override = session.doc_tier

        normalized_product = ProductDocService.normalize_product_type(product_type) or "unknown"
        normalized_complexity = ProductDocService.normalize_complexity(complexity) or "unknown"
        doc_tier = ProductDocService.select_doc_tier(
            normalized_product,
            normalized_complexity,
            doc_tier_override,
        )
        return normalized_product, normalized_complexity, doc_tier

    def _apply_routing_metadata(
        self,
        structured: dict,
        *,
        product_type: str,
        complexity: str,
        doc_tier: str,
    ) -> dict:
        if not isinstance(structured, dict):
            structured = {}
        if not structured.get("product_type") or structured.get("product_type") == "unknown":
            structured["product_type"] = product_type
        if not structured.get("complexity") or structured.get("complexity") == "unknown":
            structured["complexity"] = complexity
        structured["doc_tier"] = doc_tier
        return structured

    def _ensure_structured_fields(self, structured: dict) -> dict:
        if not isinstance(structured, dict):
            structured = {}
        structured.setdefault("product_type", "unknown")
        structured.setdefault("complexity", "unknown")
        structured.setdefault("doc_tier", "standard")
        structured.setdefault("goal", structured.get("goal") or "")
        structured.setdefault("pages", [])
        structured.setdefault("data_flow", [])
        structured.setdefault("component_inventory", [])
        product_type = ProductDocService.normalize_product_type(structured.get("product_type")) or "unknown"
        if not structured.get("component_inventory"):
            fallback = structured.get("components") or []
            if not fallback and isinstance(structured.get("features"), list):
                fallback = [
                    item.get("name")
                    for item in structured.get("features", [])
                    if isinstance(item, dict) and item.get("name")
                ]
            if not fallback:
                fallback = self._resolve_skill_components(product_type)
            structured["component_inventory"] = self._coerce_string_list(fallback)

        structured["product_type"] = product_type
        structured["complexity"] = (
            ProductDocService.normalize_complexity(structured.get("complexity")) or structured["complexity"]
        )
        structured["doc_tier"] = (
            ProductDocService.normalize_doc_tier(structured.get("doc_tier")) or structured["doc_tier"]
        )
        structured["state_contract"] = self._normalize_state_contract(
            structured.get("state_contract"),
            product_type=product_type,
        )
        if "style_reference" not in structured:
            structured["style_reference"] = None
        return structured

    def _resolve_skill_components(self, product_type: str) -> List[str]:
        try:
            registry = SkillsRegistry()
        except Exception:
            logger.exception("Failed to initialize SkillsRegistry")
            return []

        skill_id = None
        if self.db is not None:
            session = self.db.get(SessionModel, self.session_id)
            if session is not None:
                skill_id = session.skill_id
        manifest = registry.get(skill_id) if skill_id else registry.select_best(product_type)
        if manifest and manifest.components:
            return [str(item) for item in manifest.components if str(item).strip()]
        return []

    def _ensure_mermaid(self, structured: dict) -> dict:
        if not isinstance(structured, dict):
            return structured
        if str(structured.get("doc_tier") or "").lower() != "extended":
            return structured
        pages = structured.get("pages") if isinstance(structured.get("pages"), list) else []
        data_flow = structured.get("data_flow") if isinstance(structured.get("data_flow"), list) else []
        if not structured.get("mermaid_page_flow"):
            structured["mermaid_page_flow"] = self._build_mermaid_page_flow(pages)
        if not structured.get("mermaid_data_flow"):
            structured["mermaid_data_flow"] = self._build_mermaid_data_flow(data_flow, pages)
        return structured

    def _build_mermaid_page_flow(self, pages: List[dict]) -> Optional[str]:
        if not pages:
            return None
        lines = ["graph TD"]
        ids = {}
        for page in pages:
            if not isinstance(page, dict):
                continue
            slug = str(page.get("slug") or "").strip()
            title = str(page.get("title") or slug or "Page").strip()
            if not slug:
                continue
            node_id = self._mermaid_id(slug)
            ids[slug] = node_id
            label = title.replace('"', "'")
            lines.append(f'  {node_id}["{label}"]')
        slugs = [slug for slug in ids.keys()]
        for idx in range(len(slugs) - 1):
            lines.append(f"  {ids[slugs[idx]]} --> {ids[slugs[idx + 1]]}")
        return "\n".join(lines) if len(lines) > 1 else None

    def _build_mermaid_data_flow(self, data_flow: List[dict], pages: List[dict]) -> Optional[str]:
        if not data_flow:
            return None
        lines = ["graph LR"]
        ids = {}
        for page in pages or []:
            if not isinstance(page, dict):
                continue
            slug = str(page.get("slug") or "").strip()
            if not slug:
                continue
            ids[slug] = self._mermaid_id(slug)
        for flow in data_flow:
            if not isinstance(flow, dict):
                continue
            from_page = str(flow.get("from_page") or "").strip()
            to_page = str(flow.get("to_page") or "").strip()
            event = str(flow.get("event") or "").strip()
            if not from_page or not to_page:
                continue
            from_id = ids.get(from_page) or self._mermaid_id(from_page)
            to_id = ids.get(to_page) or self._mermaid_id(to_page)
            label = event.replace('"', "'")
            if label:
                lines.append(f'  {from_id} -->|{label}| {to_id}')
            else:
                lines.append(f"  {from_id} --> {to_id}")
        return "\n".join(lines) if len(lines) > 1 else None

    def _mermaid_id(self, value: str) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9_]", "_", value.strip())
        if not cleaned:
            cleaned = "node"
        if cleaned[0].isdigit():
            cleaned = f"n_{cleaned}"
        return cleaned

    def _parse_generate_response(
        self,
        content: str,
        *,
        user_message: str,
        interview_context: dict | None,
        product_type: str,
        complexity: str,
        doc_tier: str,
    ) -> _ParsedOutput:
        parsed = _ParsedOutput()
        sections = self._extract_sections(content)
        markdown = sections.get("MARKDOWN")
        json_section = sections.get("JSON")
        message = sections.get("MESSAGE")

        parsed.content = (markdown or "").strip()
        parsed.message = (message or "").strip()

        structured_raw, error = self._parse_json_section(json_section or "")
        if structured_raw is None:
            structured_raw, fallback_error = self._parse_json_section(content)
            if structured_raw is None:
                parsed.errors.append(error or fallback_error or "Missing structured JSON")
            elif fallback_error:
                parsed.errors.append(fallback_error)
        elif error:
            parsed.errors.append(error)

        if structured_raw:
            structured = self._normalize_structured(structured_raw)
            structured = self._apply_routing_metadata(
                structured,
                product_type=product_type,
                complexity=complexity,
                doc_tier=doc_tier,
            )
            validated, errors = self._validate_structured(structured)
            parsed.structured = validated
            parsed.errors.extend(errors)
        else:
            parsed.structured = {}

        if not parsed.content:
            parsed.content = self._build_markdown(parsed.structured, user_message)

        parsed.structured = self._merge_pages_from_markdown(parsed.structured, parsed.content)
        parsed.structured = self._ensure_structured_fields(parsed.structured)
        parsed.structured = self._ensure_mermaid(parsed.structured)

        if not parsed.message:
            parsed.message = self._default_message("generate", user_message)

        return parsed

    def _parse_update_response(
        self,
        content: str,
        *,
        current_structured: dict,
        user_message: str,
        product_type: str,
        complexity: str,
        doc_tier: str,
    ) -> _ParsedOutput:
        parsed = _ParsedOutput()
        sections = self._extract_sections(content)
        markdown = sections.get("MARKDOWN")
        json_section = sections.get("JSON")
        message = sections.get("MESSAGE")
        change_summary = sections.get("CHANGE_SUMMARY")
        affected_section = sections.get("AFFECTED_PAGES")

        parsed.content = (markdown or "").strip()
        parsed.message = (message or "").strip()
        parsed.change_summary = (change_summary or "").strip()
        parsed.affected_pages = self._parse_affected_pages(affected_section)

        structured_raw, error = self._parse_json_section(json_section or "")
        if structured_raw is None:
            structured_raw, fallback_error = self._parse_json_section(content)
            if structured_raw is None:
                parsed.errors.append(error or fallback_error or "Missing structured JSON")
            elif fallback_error:
                parsed.errors.append(fallback_error)
        elif error:
            parsed.errors.append(error)

        if structured_raw:
            structured = self._normalize_structured(structured_raw)
            structured = self._apply_routing_metadata(
                structured,
                product_type=product_type,
                complexity=complexity,
                doc_tier=doc_tier,
            )
            validated, errors = self._validate_structured(structured)
            parsed.structured = validated
            parsed.errors.extend(errors)
        else:
            parsed.structured = {}

        if not parsed.content:
            parsed.content = self._build_markdown(parsed.structured or current_structured, user_message)

        parsed.structured = self._merge_pages_from_markdown(parsed.structured, parsed.content)
        parsed.structured = self._ensure_structured_fields(parsed.structured)
        parsed.structured = self._ensure_mermaid(parsed.structured)

        if not parsed.change_summary:
            parsed.change_summary = self._default_change_summary(user_message)

        if not parsed.affected_pages:
            parsed.affected_pages = self._compute_affected_pages(current_structured, parsed.structured)

        if not parsed.message:
            parsed.message = self._default_message("update", user_message)

        return parsed

    def _build_fallback_checker(self, product_type: str) -> Callable[[Any], Optional[FallbackTrigger]]:
        normalized = ProductDocService.normalize_product_type(product_type) or ""
        flow_types = {"ecommerce", "booking", "dashboard"}

        def checker(response: Any) -> Optional[FallbackTrigger]:
            if normalized not in flow_types:
                return None
            content = getattr(response, "content", "") or ""
            sections = self._extract_sections(content)
            json_section = sections.get("JSON") or content
            structured_raw, _ = self._parse_json_section(json_section)
            if structured_raw is None or not isinstance(structured_raw, dict):
                return FallbackTrigger.INVALID_STRUCTURE
            if "state_contract" not in structured_raw and "stateContract" not in structured_raw:
                return FallbackTrigger.MISSING_FIELD
            return None

        return checker

    def _extract_sections(self, content: str) -> dict:
        if not content:
            return {}
        pattern = re.compile(r"---\s*([A-Z_]+)\s*---", re.IGNORECASE)
        matches = list(pattern.finditer(content))
        if not matches:
            return {}
        sections: dict[str, str] = {}
        for idx, match in enumerate(matches):
            key = match.group(1).strip().upper()
            start = match.end()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(content)
            sections[key] = content[start:end].strip()
        return sections

    def _parse_json_section(self, text: str) -> tuple[Optional[dict], Optional[str]]:
        if not text:
            return None, "Missing JSON section"
        cleaned = self._strip_code_fences(text).strip()
        if not cleaned:
            return None, "Empty JSON section"

        payload = self._try_parse_json(cleaned)
        if isinstance(payload, dict):
            return payload, None

        brace_payload = self._extract_brace_payload(cleaned)
        if brace_payload is not None:
            payload = self._try_parse_json(brace_payload)
            if isinstance(payload, dict):
                return payload, None

        return None, "Invalid JSON payload"

    def _strip_code_fences(self, text: str) -> str:
        fence_match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
        if fence_match:
            return fence_match.group(1).strip()
        return text

    def _try_parse_json(self, text: str) -> Any:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None

    def _extract_brace_payload(self, text: str) -> Optional[str]:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        return text[start : end + 1]

    def _normalize_structured(self, raw: dict) -> dict:
        if not isinstance(raw, dict):
            return {}

        normalized = dict(raw)
        key_map = {
            "productType": "product_type",
            "docTier": "doc_tier",
            "projectName": "project_name",
            "targetAudience": "target_audience",
            "designDirection": "design_direction",
            "dataFlow": "data_flow",
            "stateContract": "state_contract",
            "styleReference": "style_reference",
            "componentInventory": "component_inventory",
            "corePoints": "core_points",
            "userStories": "user_stories",
            "dataFlowExplanation": "data_flow_explanation",
            "mermaidPageFlow": "mermaid_page_flow",
            "mermaidDataFlow": "mermaid_data_flow",
            "detailedSpecs": "detailed_specs",
        }
        for src, dest in key_map.items():
            if src in normalized and dest not in normalized:
                normalized[dest] = normalized.pop(src)

        if "goal" not in normalized and "goals" in normalized:
            normalized["goal"] = normalized.get("goals")
        if "goals" not in normalized and "goal" in normalized:
            normalized["goals"] = normalized.get("goal")
        if "features" not in normalized and "feature" in normalized:
            normalized["features"] = normalized.pop("feature")

        design = normalized.get("design_direction")
        if not isinstance(design, dict):
            design = {}
        else:
            design = dict(design)
        design_map = {
            "colorPreference": "color_preference",
            "referenceSites": "reference_sites",
        }
        for src, dest in design_map.items():
            if src in design and dest not in design:
                design[dest] = design.pop(src)
        normalized["design_direction"] = design

        normalized["product_type"] = ProductDocService.normalize_product_type(normalized.get("product_type")) or ""
        normalized["complexity"] = ProductDocService.normalize_complexity(normalized.get("complexity")) or ""
        normalized["doc_tier"] = ProductDocService.normalize_doc_tier(normalized.get("doc_tier")) or ""
        if isinstance(normalized.get("goal"), list):
            normalized["goal"] = (
                normalized.get("goal")[0] if normalized.get("goal") else ""
            )
        if not normalized.get("goal"):
            goals = self._coerce_string_list(normalized.get("goals"))
            if goals:
                normalized["goal"] = goals[0]
            elif isinstance(normalized.get("description"), str):
                normalized["goal"] = normalized.get("description")

        normalized["goals"] = self._coerce_string_list(normalized.get("goals"))
        normalized["constraints"] = self._coerce_string_list(normalized.get("constraints"))
        normalized["core_points"] = self._coerce_string_list(normalized.get("core_points"))
        normalized["users"] = self._coerce_string_list(normalized.get("users"))
        normalized["user_stories"] = self._coerce_string_list(normalized.get("user_stories"))
        normalized["components"] = self._coerce_string_list(normalized.get("components"))
        normalized["component_inventory"] = self._coerce_string_list(normalized.get("component_inventory"))
        normalized["detailed_specs"] = self._coerce_string_list(normalized.get("detailed_specs"))
        normalized["appendices"] = self._coerce_string_list(normalized.get("appendices"))

        features = normalized.get("features")
        normalized["features"] = self._normalize_features(features)

        pages = normalized.get("pages")
        normalized["pages"] = self._normalize_pages(pages)

        data_flow = normalized.get("data_flow")
        normalized["data_flow"] = self._normalize_data_flow(data_flow)

        normalized["state_contract"] = self._normalize_state_contract(
            normalized.get("state_contract"),
            product_type=normalized.get("product_type") or "",
        )
        normalized["style_reference"] = self._normalize_style_reference(normalized.get("style_reference"))

        return normalized

    def _coerce_string_list(self, value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value.strip()] if value.strip() else []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return [str(value).strip()]

    def _normalize_features(self, features: Any) -> List[dict]:
        if not features:
            return []
        if isinstance(features, dict):
            features = [features]
        normalized: List[dict] = []
        if isinstance(features, list):
            for item in features:
                if isinstance(item, str):
                    name = item.strip()
                    if not name:
                        continue
                    normalized.append(
                        {
                            "name": name,
                            "description": "",
                            "priority": "should",
                        }
                    )
                elif isinstance(item, dict):
                    name = str(item.get("name") or "").strip()
                    if not name:
                        continue
                    feature = {
                        "name": name,
                        "description": str(item.get("description") or "").strip(),
                        "priority": str(item.get("priority") or "should").strip().lower(),
                    }
                    normalized.append(feature)
        return normalized

    def _normalize_pages(self, pages: Any) -> List[dict]:
        if not pages:
            return []
        if isinstance(pages, dict):
            pages = [pages]
        normalized: List[dict] = []
        if isinstance(pages, list):
            for item in pages:
                if not isinstance(item, dict):
                    continue
                title = str(item.get("title") or item.get("name") or "").strip()
                slug = str(item.get("slug") or "").strip()
                role = str(item.get("role") or item.get("page_role") or "").strip()
                purpose = str(item.get("purpose") or item.get("description") or "").strip()
                sections = item.get("sections")
                if isinstance(sections, str):
                    sections = [part.strip() for part in sections.split(",") if part.strip()]
                elif not isinstance(sections, list):
                    sections = []
                required = bool(item.get("required"))
                if not slug and title:
                    slug = self._slugify(title)
                if not slug:
                    slug = self._fallback_slug_from_title(title)
                if slug:
                    slug = self._truncate_slug(slug)
                if not slug:
                    continue
                if not role:
                    role = self._derive_page_role(slug, title, purpose)
                page_payload = {
                    "title": title or slug or "Page",
                    "slug": slug,
                    "role": role or "general",
                    "purpose": purpose,
                    "sections": [str(section).strip() for section in sections if str(section).strip()],
                    "required": required,
                }
                normalized.append(page_payload)
        return normalized

    def _normalize_data_flow(self, data_flow: Any) -> List[dict]:
        if not data_flow:
            return []
        if isinstance(data_flow, dict):
            data_flow = [data_flow]
        normalized: List[dict] = []
        if isinstance(data_flow, list):
            for item in data_flow:
                if not isinstance(item, dict):
                    continue
                from_page = str(item.get("from_page") or item.get("from") or item.get("source") or "").strip()
                event = str(item.get("event") or item.get("action") or "").strip()
                to_page = str(item.get("to_page") or item.get("to") or item.get("target") or "").strip()
                if not from_page or not to_page:
                    continue
                normalized.append(
                    {
                        "from_page": from_page,
                        "event": event,
                        "to_page": to_page,
                    }
                )
        return normalized

    def _normalize_state_contract(self, value: Any, *, product_type: str) -> Optional[dict]:
        normalized_type = ProductDocService.normalize_product_type(product_type) or "unknown"
        if normalized_type in {"ecommerce", "booking", "dashboard"}:
            if isinstance(value, dict):
                default_events = [
                    "add_to_cart",
                    "update_qty",
                    "remove_item",
                    "checkout_draft",
                    "submit_booking",
                    "submit_form",
                    "clear_cart",
                ]
                events = value.get("events")
                if isinstance(events, list):
                    normalized_events = [str(item) for item in events if str(item).strip()]
                else:
                    normalized_events = []
                if not normalized_events:
                    normalized_events = list(default_events)
                return {
                    "shared_state_key": value.get("shared_state_key") or "instant-coffee:state",
                    "records_key": value.get("records_key") or "instant-coffee:records",
                    "events_key": value.get("events_key") or "instant-coffee:events",
                    "schema": value.get("schema") if isinstance(value.get("schema"), dict) else {},
                    "events": normalized_events,
                }
            return {
                "shared_state_key": "instant-coffee:state",
                "records_key": "instant-coffee:records",
                "events_key": "instant-coffee:events",
                "schema": {},
                "events": [
                    "add_to_cart",
                    "update_qty",
                    "remove_item",
                    "checkout_draft",
                    "submit_booking",
                    "submit_form",
                    "clear_cart",
                ],
            }
        return None

    def _normalize_style_reference(self, value: Any) -> Optional[dict]:
        if not value:
            return None
        if not isinstance(value, dict):
            return None
        scope = value.get("scope")
        if not isinstance(scope, dict):
            scope = {}
        images = value.get("images")
        if isinstance(images, str):
            images = [images]
        if not isinstance(images, list):
            images = []
        images = [str(item) for item in images if str(item).strip()]
        mode = str(value.get("mode") or "full_mimic").strip()
        return {"mode": mode, "scope": scope, "images": images}

    def _fallback_slug_from_title(self, title: str) -> str:
        if not title:
            return ""
        lower = title.lower()
        if "\u9996\u9875" in title or "\u4e3b\u9875" in title or "home" in lower:
            return "index"
        if "\u5173\u4e8e" in title or "about" in lower:
            return "about"
        if "\u8054\u7cfb" in title or "contact" in lower:
            return "contact"
        if "\u670d\u52a1" in title or "service" in lower:
            return "services"
        if "\u4ea7\u54c1" in title or "product" in lower:
            return "products"
        if "\u4ef7\u683c" in title or "pricing" in lower or "price" in lower:
            return "pricing"
        if "\u535a\u5ba2" in title or "blog" in lower:
            return "blog"
        if "\u56e2\u961f" in title or "team" in lower:
            return "team"
        if "\u529f\u80fd" in title or "feature" in lower:
            return "features"
        return ""

    def _derive_page_role(self, slug: str, title: str, purpose: str) -> str:
        candidate = f"{slug} {title} {purpose}".lower()
        if "checkout" in candidate or "payment" in candidate or "cart" in candidate:
            return "checkout"
        if "catalog" in candidate or "product" in candidate or "shop" in candidate:
            return "catalog"
        if "profile" in candidate or "account" in candidate or "settings" in candidate:
            return "profile"
        if "booking" in candidate or "schedule" in candidate:
            return "booking"
        if "dashboard" in candidate or "admin" in candidate or "analytics" in candidate:
            return "dashboard"
        if slug == "index" or "landing" in candidate or "home" in candidate:
            return "landing"
        return "general"

    def _merge_pages_from_markdown(self, structured: dict, content: str) -> dict:
        if not content:
            return structured
        derived_pages = extract_pages_from_markdown(content)
        if not derived_pages:
            return structured

        normalized_pages = self._normalize_pages(derived_pages)
        if not normalized_pages:
            return structured

        if not isinstance(structured, dict):
            structured = {}
        existing_pages = structured.get("pages")
        if isinstance(existing_pages, list) and len(existing_pages) > 1:
            return structured

        merged = dict(structured)
        merged["pages"] = normalized_pages
        return merged

    def _validate_structured(self, structured: dict) -> tuple[dict, List[str]]:
        errors: List[str] = []
        model_cls = ProductDocStructured
        doc_tier = str(structured.get("doc_tier") or "").lower()
        if doc_tier == "checklist":
            model_cls = ProductDocChecklist
        elif doc_tier == "standard":
            model_cls = ProductDocStandard
        elif doc_tier == "extended":
            model_cls = ProductDocExtended
        try:
            model = model_cls.model_validate(structured)
        except ValidationError as exc:
            errors.append(str(exc))
            cleaned = self._sanitize_structured(structured)
            try:
                model = model_cls.model_validate(cleaned)
            except ValidationError as exc2:
                errors.append(str(exc2))
                return {}, errors
        payload = model.model_dump(exclude_none=True, exclude_unset=True)
        payload = self._ensure_structured_fields(payload)
        if doc_tier == "extended":
            payload = self._ensure_mermaid(payload)
        return payload, errors

    def _sanitize_structured(self, structured: dict) -> dict:
        if not isinstance(structured, dict):
            return {}
        allowed = set(ProductDocStructured.model_fields.keys())
        sanitized = {key: value for key, value in structured.items() if key in allowed}
        design = sanitized.get("design_direction")
        if isinstance(design, dict):
            allowed_design = {
                "style",
                "color_preference",
                "tone",
                "reference_sites",
            }
            sanitized["design_direction"] = {k: v for k, v in design.items() if k in allowed_design}
        features = sanitized.get("features")
        if isinstance(features, list):
            sanitized["features"] = [
                {
                    "name": item.get("name"),
                    "description": item.get("description"),
                    "priority": item.get("priority"),
                }
                for item in features
                if isinstance(item, dict)
            ]
        pages = sanitized.get("pages")
        if isinstance(pages, list):
            sanitized["pages"] = [
                {
                    "title": item.get("title"),
                    "slug": item.get("slug"),
                    "role": item.get("role"),
                    "purpose": item.get("purpose"),
                    "sections": item.get("sections"),
                    "required": item.get("required"),
                }
                for item in pages
                if isinstance(item, dict)
            ]
        data_flow = sanitized.get("data_flow")
        if isinstance(data_flow, list):
            sanitized["data_flow"] = [
                {
                    "from_page": item.get("from_page"),
                    "event": item.get("event"),
                    "to_page": item.get("to_page"),
                }
                for item in data_flow
                if isinstance(item, dict)
            ]
        state_contract = sanitized.get("state_contract")
        if isinstance(state_contract, dict):
            sanitized["state_contract"] = {
                "shared_state_key": state_contract.get("shared_state_key"),
                "records_key": state_contract.get("records_key"),
                "events_key": state_contract.get("events_key"),
                "schema": state_contract.get("schema"),
                "events": state_contract.get("events"),
            }
        style_reference = sanitized.get("style_reference")
        if isinstance(style_reference, dict):
            sanitized["style_reference"] = {
                "mode": style_reference.get("mode"),
                "scope": style_reference.get("scope"),
                "images": style_reference.get("images"),
            }
        return sanitized

    def _parse_affected_pages(self, text: Optional[str]) -> List[str]:
        if not text:
            return []
        cleaned = text.strip()
        if not cleaned:
            return []
        lowered = cleaned.lower()
        if lowered in {"none", "null", "n/a", "no", "false"}:
            return []

        if cleaned.startswith("["):
            payload = self._try_parse_json(cleaned)
            if isinstance(payload, list):
                return [self._sanitize_slug(item) for item in payload if self._sanitize_slug(item)]

        parts = re.split(r"[\n,]+", cleaned)
        slugs = []
        for part in parts:
            slug = self._sanitize_slug(part)
            if slug:
                slugs.append(slug)
        return slugs

    def _sanitize_slug(self, value: Any) -> str:
        if value is None:
            return ""
        slug = str(value).strip().strip("`")
        if not slug:
            return ""
        slug = slug.lower().strip()
        slug = re.sub(r"[^a-z0-9-]", "-", slug)
        slug = re.sub(r"-+", "-", slug).strip("-")
        return self._truncate_slug(slug)

    def _compute_affected_pages(self, current_structured: dict, updated_structured: dict) -> List[str]:
        current_pages = self._page_map(current_structured)
        updated_pages = self._page_map(updated_structured)
        affected: set[str] = set()

        for slug, new_page in updated_pages.items():
            old_page = current_pages.get(slug)
            if old_page is None or old_page != new_page:
                affected.add(slug)

        for slug in current_pages:
            if slug not in updated_pages:
                affected.add(slug)

        if self._non_page_changes(current_structured, updated_structured):
            affected.update(updated_pages.keys())

        if not affected:
            if updated_pages:
                affected.update(updated_pages.keys())
            else:
                affected.add("index")

        return sorted(affected)

    def _non_page_changes(self, current_structured: dict, updated_structured: dict) -> bool:
        if not isinstance(current_structured, dict) or not isinstance(updated_structured, dict):
            return False
        keys = {
            "product_type",
            "complexity",
            "doc_tier",
            "goal",
            "core_points",
            "users",
            "user_stories",
            "components",
            "component_inventory",
            "data_flow",
            "state_contract",
            "style_reference",
            "data_flow_explanation",
            "detailed_specs",
            "appendices",
            "mermaid_page_flow",
            "mermaid_data_flow",
            "project_name",
            "description",
            "target_audience",
            "goals",
            "features",
            "design_direction",
            "constraints",
        }
        for key in keys:
            if current_structured.get(key) != updated_structured.get(key):
                return True
        return False

    def _page_map(self, structured: dict) -> dict:
        pages = structured.get("pages") if isinstance(structured, dict) else None
        if not isinstance(pages, list):
            return {}
        result = {}
        for item in pages:
            if not isinstance(item, dict):
                continue
            slug = str(item.get("slug") or "").strip().lower()
            if not slug:
                continue
            result[slug] = {
                "title": item.get("title"),
                "slug": slug,
                "role": item.get("role"),
                "purpose": item.get("purpose"),
                "sections": item.get("sections"),
                "required": item.get("required"),
            }
        return result

    def _ensure_index_page(self, structured: dict, *, user_message: str) -> dict:
        if not isinstance(structured, dict):
            structured = {}
        pages = structured.get("pages")
        if not isinstance(pages, list):
            pages = []

        has_index = any(
            isinstance(page, dict) and str(page.get("slug") or "").strip().lower() == "index"
            for page in pages
        )
        if not has_index:
            index_page = {
                "title": "Home",
                "slug": "index",
                "role": "landing",
                "purpose": "Primary landing page",
                "sections": ["hero", "features", "cta"],
                "required": True,
            }
            pages = [index_page] + pages
        else:
            for page in pages:
                if isinstance(page, dict) and str(page.get("slug") or "").strip().lower() == "index":
                    page["required"] = True
                    if not page.get("role"):
                        page["role"] = "landing"

        structured["pages"] = pages
        return structured

    def _build_markdown(self, structured: dict, user_message: str) -> str:
        name = (structured.get("project_name") or "Untitled project") if isinstance(structured, dict) else "Untitled"
        description = structured.get("description") if isinstance(structured, dict) else None
        audience = structured.get("target_audience") if isinstance(structured, dict) else None
        goal = structured.get("goal") if isinstance(structured, dict) else None
        product_type = structured.get("product_type") if isinstance(structured, dict) else None
        complexity = structured.get("complexity") if isinstance(structured, dict) else None
        doc_tier = structured.get("doc_tier") if isinstance(structured, dict) else None
        goals = structured.get("goals") if isinstance(structured, dict) else []
        features = structured.get("features") if isinstance(structured, dict) else []
        design = structured.get("design_direction") if isinstance(structured, dict) else {}
        pages = structured.get("pages") if isinstance(structured, dict) else []
        data_flow = structured.get("data_flow") if isinstance(structured, dict) else []
        state_contract = structured.get("state_contract") if isinstance(structured, dict) else None
        component_inventory = structured.get("component_inventory") if isinstance(structured, dict) else []
        core_points = structured.get("core_points") if isinstance(structured, dict) else []
        users = structured.get("users") if isinstance(structured, dict) else []
        user_stories = structured.get("user_stories") if isinstance(structured, dict) else []
        constraints = structured.get("constraints") if isinstance(structured, dict) else []

        lines = ["# Product Document", "", f"## Project", f"- Name: {name}"]
        if description:
            lines.append(f"- Description: {description}")
        if audience:
            lines.append(f"- Target audience: {audience}")
        if product_type:
            lines.append(f"- Product type: {product_type}")
        if complexity:
            lines.append(f"- Complexity: {complexity}")
        if doc_tier:
            lines.append(f"- Doc tier: {doc_tier}")

        if goal:
            lines.append("\n## Goal")
            lines.append(f"- {goal}")

        if goals:
            lines.append("\n## Goals")
            for goal in goals:
                lines.append(f"- {goal}")

        if features:
            lines.append("\n## Features")
            for feature in features:
                if isinstance(feature, dict):
                    fname = feature.get("name") or "Feature"
                    fdesc = feature.get("description") or ""
                    priority = feature.get("priority") or ""
                    detail = f" ({priority})" if priority else ""
                    lines.append(f"- {fname}{detail}{': ' + fdesc if fdesc else ''}")

        if design and isinstance(design, dict):
            lines.append("\n## Design Direction")
            for key in ["style", "color_preference", "tone"]:
                value = design.get(key)
                if value:
                    lines.append(f"- {key.replace('_', ' ').title()}: {value}")
            refs = design.get("reference_sites") or []
            if refs:
                lines.append("- Reference sites: " + ", ".join(str(item) for item in refs))

        if pages:
            lines.append("\n## Pages")
            for page in pages:
                if not isinstance(page, dict):
                    continue
                title = page.get("title") or "Page"
                slug = page.get("slug") or ""
                role = page.get("role") or "general"
                purpose = page.get("purpose") or ""
                lines.append(f"- {title} ({slug}) [{role}] - {purpose}")
                sections = page.get("sections") or []
                if sections:
                    lines.append("  - Sections: " + ", ".join(str(item) for item in sections))

        if data_flow:
            lines.append("\n## Data Flow")
            for flow in data_flow:
                if not isinstance(flow, dict):
                    continue
                from_page = flow.get("from_page") or flow.get("from") or ""
                to_page = flow.get("to_page") or flow.get("to") or ""
                event = flow.get("event") or ""
                if from_page and to_page:
                    lines.append(f"- {from_page} -> {to_page} ({event})")

        if state_contract and isinstance(state_contract, dict):
            lines.append("\n## State Contract")
            lines.append(f"- shared_state_key: {state_contract.get('shared_state_key')}")
            lines.append(f"- records_key: {state_contract.get('records_key')}")
            lines.append(f"- events_key: {state_contract.get('events_key')}")
            events = state_contract.get("events")
            if isinstance(events, list) and events:
                lines.append("- events: " + ", ".join(str(item) for item in events))

        if component_inventory:
            lines.append("\n## Component Inventory")
            for item in component_inventory:
                lines.append(f"- {item}")

        if core_points:
            lines.append("\n## Core Points")
            for item in core_points:
                lines.append(f"- {item}")

        if users:
            lines.append("\n## Users")
            for item in users:
                lines.append(f"- {item}")

        if user_stories:
            lines.append("\n## User Stories")
            for item in user_stories:
                lines.append(f"- {item}")

        if constraints:
            lines.append("\n## Constraints")
            for item in constraints:
                lines.append(f"- {item}")

        if not description and user_message:
            lines.append("\n## User Request")
            lines.append(user_message.strip())

        return "\n".join(lines).strip()

    def _default_message(self, action: str, user_message: str) -> str:
        return "Product doc draft is ready. Let me know what to change." if action == "generate" else "Product doc updated. Let me know if you'd like further edits."

    def _default_change_summary(self, user_message: str) -> str:
        return "Updated the product document based on your request."

    def _append_error_note(self, message: str, errors: List[str], user_message: str) -> str:
        if not errors:
            return message
        note = "Note: I had trouble parsing some structured fields; please review."
        if note in message:
            return message
        return f"{message}\n\n{note}"

    def _language_note(self, user_message: str, interview_section: Optional[str]) -> str:
        return "Please respond in English."

    def _slugify(self, value: str) -> str:
        slug = value.strip().lower()
        slug = re.sub(r"[^a-z0-9]+", "-", slug)
        slug = re.sub(r"-+", "-", slug).strip("-")
        return slug

    def _truncate_slug(self, slug: str, max_len: int = 40) -> str:
        if len(slug) <= max_len:
            return slug
        return slug[:max_len].rstrip("-")


__all__ = ["ProductDocAgent", "ProductDocGenerateResult", "ProductDocUpdateResult"]
