from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, List, Optional, Sequence

from pydantic import ValidationError

from .base import BaseAgent
from .prompts import (
    PRODUCT_DOC_GENERATE_USER,
    PRODUCT_DOC_UPDATE_USER,
    get_product_doc_generate_prompt,
    get_product_doc_update_prompt,
)
from ..schemas.product_doc import ProductDocStructured
from ..services.product_doc import ProductDocService

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
        )
        self.generate_prompt = get_product_doc_generate_prompt()
        self.update_prompt = get_product_doc_update_prompt()

    async def generate(
        self,
        session_id: Optional[str],
        user_message: str,
        interview_context: dict | None = None,
        history: Sequence[dict] | None = None,
    ) -> ProductDocGenerateResult:
        resolved_session_id = session_id or self.session_id
        history = history or []

        messages = self._build_generate_messages(
            user_message=user_message,
            interview_context=interview_context,
            history=history,
        )
        response = await self._call_llm(
            messages=messages,
            agent_type=self.agent_type,
            model=self.settings.model,
            temperature=self.settings.temperature,
            max_tokens=self.settings.max_tokens,
            context="product-doc-generate",
        )
        tokens_used = response.token_usage.total_tokens if response.token_usage else 0

        parsed = self._parse_generate_response(
            response.content or "",
            user_message=user_message,
            interview_context=interview_context,
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
    ) -> ProductDocUpdateResult:
        resolved_session_id = session_id or self.session_id
        history = history or []

        current_content = getattr(current_doc, "content", "") or ""
        current_structured = getattr(current_doc, "structured", None)
        if not isinstance(current_structured, dict):
            current_structured = {}

        messages = self._build_update_messages(
            current_content=current_content,
            current_structured=current_structured,
            user_message=user_message,
            history=history,
        )
        response = await self._call_llm(
            messages=messages,
            agent_type=self.agent_type,
            model=self.settings.model,
            temperature=self.settings.temperature,
            max_tokens=self.settings.max_tokens,
            context="product-doc-update",
        )
        tokens_used = response.token_usage.total_tokens if response.token_usage else 0

        parsed = self._parse_update_response(
            response.content or "",
            current_structured=current_structured,
            user_message=user_message,
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
    ) -> List[dict]:
        messages: List[dict] = [{"role": "system", "content": self.generate_prompt}]
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
        ).strip()

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
    ) -> List[dict]:
        messages: List[dict] = [{"role": "system", "content": self.update_prompt}]
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
        ).strip()
        language_note = self._language_note(user_message, None)
        if language_note:
            prompt = f"{prompt}\n\n{language_note}"
        messages.append({"role": "user", "content": prompt})
        return messages

    def _parse_generate_response(
        self,
        content: str,
        *,
        user_message: str,
        interview_context: dict | None,
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
            validated, errors = self._validate_structured(structured)
            parsed.structured = validated
            parsed.errors.extend(errors)
        else:
            parsed.structured = {}

        if not parsed.content:
            parsed.content = self._build_markdown(parsed.structured, user_message)

        if not parsed.message:
            parsed.message = self._default_message("generate", user_message)

        return parsed

    def _parse_update_response(
        self,
        content: str,
        *,
        current_structured: dict,
        user_message: str,
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
            validated, errors = self._validate_structured(structured)
            parsed.structured = validated
            parsed.errors.extend(errors)
        else:
            parsed.structured = {}

        if not parsed.content:
            parsed.content = self._build_markdown(parsed.structured or current_structured, user_message)

        if not parsed.change_summary:
            parsed.change_summary = self._default_change_summary(user_message)

        if not parsed.affected_pages:
            parsed.affected_pages = self._compute_affected_pages(current_structured, parsed.structured)

        if not parsed.message:
            parsed.message = self._default_message("update", user_message)

        return parsed

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
            "projectName": "project_name",
            "targetAudience": "target_audience",
            "designDirection": "design_direction",
        }
        for src, dest in key_map.items():
            if src in normalized and dest not in normalized:
                normalized[dest] = normalized.pop(src)

        if "goals" not in normalized and "goal" in normalized:
            normalized["goals"] = normalized.pop("goal")
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

        normalized["goals"] = self._coerce_string_list(normalized.get("goals"))
        normalized["constraints"] = self._coerce_string_list(normalized.get("constraints"))

        features = normalized.get("features")
        normalized["features"] = self._normalize_features(features)

        pages = normalized.get("pages")
        normalized["pages"] = self._normalize_pages(pages)

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
                purpose = str(item.get("purpose") or item.get("description") or "").strip()
                sections = item.get("sections")
                if isinstance(sections, str):
                    sections = [part.strip() for part in sections.split(",") if part.strip()]
                elif not isinstance(sections, list):
                    sections = []
                required = bool(item.get("required"))
                if not slug and title:
                    slug = self._slugify(title)
                if slug:
                    slug = self._truncate_slug(slug)
                if not slug:
                    continue
                page_payload = {
                    "title": title or slug or "Page",
                    "slug": slug,
                    "purpose": purpose,
                    "sections": [str(section).strip() for section in sections if str(section).strip()],
                    "required": required,
                }
                normalized.append(page_payload)
        return normalized

    def _validate_structured(self, structured: dict) -> tuple[dict, List[str]]:
        errors: List[str] = []
        try:
            model = ProductDocStructured.model_validate(structured)
        except ValidationError as exc:
            errors.append(str(exc))
            cleaned = self._sanitize_structured(structured)
            try:
                model = ProductDocStructured.model_validate(cleaned)
            except ValidationError as exc2:
                errors.append(str(exc2))
                return {}, errors
        return model.model_dump(exclude_none=True, exclude_unset=True), errors

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
                    "purpose": item.get("purpose"),
                    "sections": item.get("sections"),
                    "required": item.get("required"),
                }
                for item in pages
                if isinstance(item, dict)
            ]
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
                "purpose": "Primary landing page",
                "sections": ["hero", "features", "cta"],
                "required": True,
            }
            pages = [index_page] + pages
        else:
            for page in pages:
                if isinstance(page, dict) and str(page.get("slug") or "").strip().lower() == "index":
                    page["required"] = True

        structured["pages"] = pages
        return structured

    def _build_markdown(self, structured: dict, user_message: str) -> str:
        name = (structured.get("project_name") or "Untitled project") if isinstance(structured, dict) else "Untitled"
        description = structured.get("description") if isinstance(structured, dict) else None
        audience = structured.get("target_audience") if isinstance(structured, dict) else None
        goals = structured.get("goals") if isinstance(structured, dict) else []
        features = structured.get("features") if isinstance(structured, dict) else []
        design = structured.get("design_direction") if isinstance(structured, dict) else {}
        pages = structured.get("pages") if isinstance(structured, dict) else []
        constraints = structured.get("constraints") if isinstance(structured, dict) else []

        lines = ["# Product Document", "", f"## Project", f"- Name: {name}"]
        if description:
            lines.append(f"- Description: {description}")
        if audience:
            lines.append(f"- Target audience: {audience}")

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
                purpose = page.get("purpose") or ""
                lines.append(f"- {title} ({slug}) - {purpose}")
                sections = page.get("sections") or []
                if sections:
                    lines.append("  - Sections: " + ", ".join(str(item) for item in sections))

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
