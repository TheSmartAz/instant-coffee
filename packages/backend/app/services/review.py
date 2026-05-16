from __future__ import annotations

import re
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session as DbSession

from ..db.models import Page, ProductDoc, Session as SessionModel
from ..utils.product_doc import extract_pages_from_markdown


IssueSeverity = Literal["error", "warning"]
ReviewVerdictValue = Literal["pass", "fail"]


class ReviewIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    severity: IssueSeverity
    message: str
    subject: Optional[str] = None
    details: dict[str, Any] = Field(default_factory=dict)


class ReviewPageInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str
    title: str = ""
    html: Optional[str] = None
    current_version_id: Optional[int] = None


class ReviewBuildInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Optional[str] = None
    pages: list[str] = Field(default_factory=list)
    error: Optional[str] = None
    log_summary: Optional[str] = None


class ReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_doc_content: Optional[str] = None
    product_doc_structured: dict[str, Any] = Field(default_factory=dict)
    product_doc_status: Optional[str] = None
    pages: list[ReviewPageInput] = Field(default_factory=list)
    build: ReviewBuildInput = Field(default_factory=ReviewBuildInput)


class ReviewVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verdict: ReviewVerdictValue
    issues: list[ReviewIssue] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.verdict == "pass"


_ERROR_LOG_RE = re.compile(r"\b(error|failed|exception|traceback)\b", re.IGNORECASE)
_PLACEHOLDER_RE = re.compile(r"(\{\{[^}]+\}\}|<%[^>]+%>|TODO|FIXME)", re.IGNORECASE)
_HTML_SHELL_RE = re.compile(r"<(?:!doctype\s+html|html|body|main|section|div)\b", re.IGNORECASE)


class ReviewService:
    """Deterministic review gate for generated backend artifacts.

    This service intentionally avoids orchestrator and LangGraph dependencies. It only reads
    persisted product-doc, page, and build metadata state, then applies local rules.
    """

    FAILING_BUILD_STATUSES = {"failed", "error", "cancelled"}
    INCOMPLETE_BUILD_STATUSES = {"building", "queued", "running"}

    def __init__(self, db: DbSession | None = None) -> None:
        self.db = db

    def review_session(
        self,
        session_id: str,
        *,
        build_log_summary: str | None = None,
    ) -> ReviewVerdict:
        if self.db is None:
            raise ValueError("db session is required for review_session")

        session = self.db.get(SessionModel, session_id)
        if session is None:
            raise ValueError("Session not found")

        product_doc = (
            self.db.query(ProductDoc)
            .filter(ProductDoc.session_id == session_id)
            .first()
        )
        pages = (
            self.db.query(Page)
            .filter(Page.session_id == session_id)
            .order_by(Page.order_index.asc(), Page.created_at.asc())
            .all()
        )
        is_react = self._is_react_workspace(session_id)
        return self.review(
            ReviewInput(
                product_doc_content=product_doc.content if product_doc else None,
                product_doc_structured=(
                    product_doc.structured
                    if product_doc is not None and isinstance(product_doc.structured, dict)
                    else {}
                ),
                product_doc_status=(
                    getattr(product_doc.status, "value", product_doc.status)
                    if product_doc is not None
                    else None
                ),
                pages=[self._page_input(page) for page in pages],
                build=self._build_input(session, build_log_summary),
            ),
            is_react=is_react,
        )

    def _is_react_workspace(self, session_id: str) -> bool:
        from pathlib import Path
        from ..config import get_settings

        workspace = Path(get_settings().output_dir).expanduser() / session_id
        return (workspace / "src" / "App.tsx").is_file()

    def review(
        self,
        review_input: ReviewInput | dict[str, Any],
        *,
        is_react: bool = False,
    ) -> ReviewVerdict:
        data = (
            review_input
            if isinstance(review_input, ReviewInput)
            else ReviewInput.model_validate(review_input)
        )
        issues: list[ReviewIssue] = []

        expected_slugs = self._expected_page_slugs(data)
        generated_slugs = {page.slug for page in data.pages}

        self._review_product_doc(data, issues)
        self._review_pages(
            data.pages, expected_slugs, generated_slugs, issues, is_react=is_react
        )
        self._review_build(data.build, generated_slugs, issues)

        error_count = sum(1 for issue in issues if issue.severity == "error")
        warning_count = sum(1 for issue in issues if issue.severity == "warning")
        return ReviewVerdict(
            verdict="fail" if error_count else "pass",
            issues=issues,
            summary={
                "error_count": error_count,
                "warning_count": warning_count,
                "expected_pages": sorted(expected_slugs),
                "generated_pages": sorted(generated_slugs),
                "build_status": data.build.status,
            },
        )

    def _review_product_doc(self, data: ReviewInput, issues: list[ReviewIssue]) -> None:
        has_content = bool((data.product_doc_content or "").strip())
        has_structured = bool(data.product_doc_structured)
        if not has_content and not has_structured:
            issues.append(
                ReviewIssue(
                    code="product_doc_missing",
                    severity="error",
                    message="Product doc is missing or empty.",
                    subject="product_doc",
                )
            )
            return

        status = (data.product_doc_status or "").strip().lower()
        if status and status != "confirmed":
            issues.append(
                ReviewIssue(
                    code="product_doc_not_confirmed",
                    severity="warning",
                    message=f"Product doc status is {status!r}, not 'confirmed'.",
                    subject="product_doc",
                )
            )

    def _review_pages(
        self,
        pages: list[ReviewPageInput],
        expected_slugs: set[str],
        generated_slugs: set[str],
        issues: list[ReviewIssue],
        *,
        is_react: bool = False,
    ) -> None:
        if not pages:
            issues.append(
                ReviewIssue(
                    code="pages_missing",
                    severity="error",
                    message="No generated pages were found.",
                    subject="pages",
                )
            )

        for slug in sorted(expected_slugs - generated_slugs):
            issues.append(
                ReviewIssue(
                    code="expected_page_missing",
                    severity="error",
                    message=f"Expected page {slug!r} was not generated.",
                    subject=slug,
                )
            )

        for page in pages:
            html = (page.html or "").strip()
            if not html:
                # React workspaces use TSX source; empty HTML is OK until built
                if is_react:
                    continue
                issues.append(
                    ReviewIssue(
                        code="page_html_missing",
                        severity="error",
                        message=f"Generated page {page.slug!r} has no current HTML.",
                        subject=page.slug,
                        details={"current_version_id": page.current_version_id},
                    )
                )
                continue
            if _HTML_SHELL_RE.search(html) is None:
                if is_react:
                    continue
                issues.append(
                    ReviewIssue(
                        code="page_html_invalid",
                        severity="error",
                        message=f"Generated page {page.slug!r} does not look like HTML.",
                        subject=page.slug,
                    )
                )
            if _PLACEHOLDER_RE.search(html):
                issues.append(
                    ReviewIssue(
                        code="page_placeholder_leftover",
                        severity="error",
                        message=f"Generated page {page.slug!r} contains unresolved placeholder text.",
                        subject=page.slug,
                    )
                )

    def _review_build(
        self,
        build: ReviewBuildInput,
        generated_slugs: set[str],
        issues: list[ReviewIssue],
    ) -> None:
        status = (build.status or "").strip().lower()
        if status in self.FAILING_BUILD_STATUSES:
            issues.append(
                ReviewIssue(
                    code="build_failed",
                    severity="error",
                    message="Build status is failed.",
                    subject="build",
                    details={"error": build.error},
                )
            )
        elif status in self.INCOMPLETE_BUILD_STATUSES:
            issues.append(
                ReviewIssue(
                    code="build_incomplete",
                    severity="error",
                    message=f"Build status is {status!r}, not complete.",
                    subject="build",
                )
            )
        elif status and status != "success":
            issues.append(
                ReviewIssue(
                    code="build_status_unknown",
                    severity="warning",
                    message=f"Build status {status!r} is not recognized.",
                    subject="build",
                )
            )

        if build.error:
            issues.append(
                ReviewIssue(
                    code="build_error_present",
                    severity="error",
                    message="Build metadata includes an error.",
                    subject="build",
                    details={"error": build.error},
                )
            )

        if build.log_summary and _ERROR_LOG_RE.search(build.log_summary):
            issues.append(
                ReviewIssue(
                    code="build_log_error",
                    severity="error",
                    message="Build log summary contains an error indicator.",
                    subject="build",
                )
            )

        build_pages = {self._page_slug_from_build_path(page) for page in build.pages}
        build_pages.discard("")
        for slug in sorted(generated_slugs - build_pages):
            issues.append(
                ReviewIssue(
                    code="build_artifact_missing",
                    severity="error",
                    message=f"Generated page {slug!r} is missing from build artifacts.",
                    subject=slug,
                )
            )

    def _expected_page_slugs(self, data: ReviewInput) -> set[str]:
        structured_pages = data.product_doc_structured.get("pages")
        if isinstance(structured_pages, list):
            slugs = {
                str(page.get("slug") or "").strip()
                for page in structured_pages
                if isinstance(page, dict)
            }
            slugs.discard("")
            if slugs:
                return slugs

        return {
            str(page.get("slug") or "").strip()
            for page in extract_pages_from_markdown(data.product_doc_content or "")
            if isinstance(page, dict) and page.get("slug")
        }

    def _page_input(self, page: Page) -> ReviewPageInput:
        current = page.current_version
        return ReviewPageInput(
            slug=page.slug,
            title=page.title,
            html=current.html if current is not None else None,
            current_version_id=page.current_version_id,
        )

    def _build_input(
        self,
        session: SessionModel,
        build_log_summary: str | None,
    ) -> ReviewBuildInput:
        artifacts = session.build_artifacts if isinstance(session.build_artifacts, dict) else {}
        return ReviewBuildInput(
            status=getattr(session.build_status, "value", session.build_status),
            pages=[str(page) for page in artifacts.get("pages") or []],
            error=artifacts.get("error"),
            log_summary=build_log_summary,
        )

    def _page_slug_from_build_path(self, value: str) -> str:
        path = str(value).strip().replace("\\", "/")
        if not path:
            return ""
        while path.startswith("./"):
            path = path[2:]
        parts = [part for part in path.split("/") if part and part != "."]
        while parts and parts[0] in {"dist", "pages"}:
            parts.pop(0)
        if not parts:
            return ""

        leaf = parts[-1]
        if leaf.endswith(".html"):
            leaf = leaf[:-5]
        if leaf == "index":
            if len(parts) == 1:
                return "index"
            return "/".join(parts[:-1])
        parts[-1] = leaf
        return "/".join(parts)


__all__ = [
    "ReviewBuildInput",
    "ReviewInput",
    "ReviewIssue",
    "ReviewPageInput",
    "ReviewService",
    "ReviewVerdict",
]
