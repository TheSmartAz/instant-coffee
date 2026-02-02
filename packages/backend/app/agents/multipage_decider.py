from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional

from ..events.models import MultiPageDecisionEvent


@dataclass
class MultiPageDecision:
    decision: str  # "single_page" | "multi_page" | "suggest_multi_page"
    confidence: float
    reasons: List[str] = field(default_factory=list)
    suggested_pages: Optional[List[dict]] = None
    risk: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "decision": self.decision,
            "confidence": self.confidence,
            "reasons": list(self.reasons),
            "suggested_pages": self.suggested_pages,
            "risk": self.risk,
        }


class AutoMultiPageDecider:
    def __init__(self, *, event_emitter: Any | None = None) -> None:
        self.event_emitter = event_emitter

    def decide(self, product_doc: Any) -> MultiPageDecision:
        structured = getattr(product_doc, "structured", None) or {}
        if not isinstance(structured, dict):
            structured = {}

        score, reasons = calculate_confidence(structured)
        decision = "single_page"
        risk = None
        suggested_pages = None

        if score >= 0.75:
            decision = "multi_page"
        elif score >= 0.45:
            decision = "suggest_multi_page"
            suggested_pages = _extract_suggested_pages(structured)
            if not suggested_pages:
                suggested_pages = _default_suggested_pages()
                risk = "No pages defined in ProductDoc; using default suggestions."

        if score < 0.45:
            reasons.append("Scope appears focused; single page likely sufficient.")

        result = MultiPageDecision(
            decision=decision,
            confidence=score,
            reasons=reasons,
            suggested_pages=suggested_pages,
            risk=risk,
        )

        if self.event_emitter:
            self.event_emitter.emit(
                MultiPageDecisionEvent(
                    decision=result.decision,
                    confidence=result.confidence,
                    reasons=result.reasons,
                    suggested_pages=result.suggested_pages,
                    risk=result.risk,
                )
            )

        return result


def calculate_confidence(structured: dict) -> tuple[float, List[str]]:
    score = 0.0
    reasons: List[str] = []

    pages = structured.get("pages") or []
    if isinstance(pages, list):
        page_count = len(pages)
    else:
        page_count = 0

    if page_count >= 3:
        score += 0.4
        reasons.append(f"ProductDoc includes {page_count} pages.")
    elif page_count >= 2:
        score += 0.25
        reasons.append("ProductDoc includes multiple pages.")

    features = structured.get("features") or []
    must_features = [f for f in features if isinstance(f, dict) and f.get("priority") == "must"]
    if len(must_features) >= 4:
        score += 0.3
        reasons.append("Several must-have features suggest broader scope.")
    elif len(must_features) >= 2:
        score += 0.15
        reasons.append("Multiple must-have features suggest more than one page.")

    description = structured.get("description") or ""
    if not isinstance(description, str):
        description = ""
    description = description.lower()
    multi_page_keywords = [
        "pages",
        "services",
        "products",
        "about",
        "contact",
        "blog",
    ]
    if any(keyword in description for keyword in multi_page_keywords):
        score += 0.2
        reasons.append("Description references multi-page sections.")

    total_sections = 0
    if isinstance(pages, list):
        for page in pages:
            if isinstance(page, dict):
                sections = page.get("sections") or []
                if isinstance(sections, list):
                    total_sections += len(sections)

    if total_sections >= 10:
        score += 0.1
        reasons.append("Total section count suggests a larger structure.")

    score = min(score, 1.0)
    return score, reasons


def _extract_suggested_pages(structured: dict) -> List[dict]:
    pages = structured.get("pages") or []
    if not isinstance(pages, list):
        return []
    suggested = []
    for page in pages:
        if not isinstance(page, dict):
            continue
        title = page.get("title") or ""
        slug = page.get("slug") or ""
        purpose = page.get("purpose") or ""
        if not title or not slug:
            continue
        suggested.append(
            {
                "title": title,
                "slug": slug,
                "purpose": purpose,
                "sections": page.get("sections") or [],
                "required": bool(page.get("required", False)),
            }
        )
    return suggested


def _default_suggested_pages() -> List[dict]:
    return [
        {
            "title": "Home",
            "slug": "index",
            "purpose": "Overview and primary call to action",
            "sections": ["hero", "features", "cta"],
            "required": True,
        },
        {
            "title": "Features",
            "slug": "features",
            "purpose": "Highlight key capabilities",
            "sections": ["feature-list", "benefits"],
            "required": False,
        },
        {
            "title": "Contact",
            "slug": "contact",
            "purpose": "Help visitors get in touch",
            "sections": ["contact-form", "details"],
            "required": False,
        },
    ]


__all__ = ["AutoMultiPageDecider", "MultiPageDecision", "calculate_confidence"]
