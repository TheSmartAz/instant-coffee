from __future__ import annotations

from typing import Dict, List, Optional

import re


_VIEWPORT_RE = re.compile(r"<meta[^>]+name=[\"']viewport[\"'][^>]*>", re.IGNORECASE)
_TITLE_RE = re.compile(r"<title[^>]*>.*?</title>", re.IGNORECASE | re.DOTALL)
_IMG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
_ALT_RE = re.compile(r"\balt\s*=\s*([\"'])(.*?)\1", re.IGNORECASE | re.DOTALL)
_HREF_RE = re.compile(r"href\s*=\s*([\"'])(.*?)\1", re.IGNORECASE)
_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")
_BASE64_RE = re.compile(r"data:[^;]+;base64,([A-Za-z0-9+/=]+)")

MAX_INLINE_BASE64_BYTES = 200_000
FALLBACK_EXCERPT_MAX_CHARS = 1200


def _is_internal_link(value: str) -> bool:
    raw = (value or "").strip()
    if not raw:
        return False
    if raw.startswith("#") or raw.startswith("//"):
        return False
    if _SCHEME_RE.match(raw):
        return False
    return True


def _strip_query_fragment(value: str) -> str:
    base = value.split("#", 1)[0]
    base = base.split("?", 1)[0]
    return base


def _normalize_path(value: str) -> str:
    raw = value.strip()
    while raw.startswith("./"):
        raw = raw[2:]
    if raw.startswith("/"):
        raw = raw[1:]
    return raw


def _validate_internal_link(value: str) -> bool:
    base = _normalize_path(_strip_query_fragment(value))
    if not base:
        return True
    if base.startswith("../"):
        return False
    if base == "index.html":
        return True
    if base.startswith("pages/") and base.endswith(".html"):
        return True
    return False


def validate_mobile_html(html: str) -> Dict[str, List[str]]:
    errors: List[str] = []
    warnings: List[str] = []

    if not html or not html.strip():
        return {"errors": ["empty_html"], "warnings": warnings}

    if not _VIEWPORT_RE.search(html):
        errors.append("missing_viewport_meta")

    if not _TITLE_RE.search(html):
        errors.append("missing_title")

    for img_tag in _IMG_RE.findall(html):
        alt_match = _ALT_RE.search(img_tag)
        if not alt_match or not alt_match.group(2).strip():
            errors.append("image_missing_alt")
            break

    for match in _BASE64_RE.finditer(html):
        data = match.group(1) or ""
        approx_bytes = int(len(data) * 3 / 4)
        if approx_bytes > MAX_INLINE_BASE64_BYTES:
            errors.append("inline_base64_too_large")
            break

    for match in _HREF_RE.finditer(html):
        href = match.group(2) or ""
        if not _is_internal_link(href):
            continue
        base = _strip_query_fragment(href)
        if not base:
            continue
        if "." in base and not base.endswith(".html"):
            continue
        if not _validate_internal_link(href):
            errors.append("invalid_internal_link")
            break

    return {"errors": errors, "warnings": warnings}


def build_fallback_excerpt(content: Optional[str], max_chars: int = FALLBACK_EXCERPT_MAX_CHARS) -> Optional[str]:
    if not content:
        return None
    snippet = " ".join(str(content).split())
    if not snippet:
        return None
    if len(snippet) <= max_chars:
        return snippet
    head = max_chars // 2
    tail = max_chars - head
    return f"{snippet[:head]} ... {snippet[-tail:]}"


__all__ = ["validate_mobile_html", "build_fallback_excerpt"]
