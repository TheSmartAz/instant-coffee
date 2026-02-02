from __future__ import annotations

import re
from typing import Iterable, List, Optional, Sequence, Tuple


_HEAD_CLOSE_RE = re.compile(r"</head>", re.IGNORECASE)
_HEAD_OPEN_RE = re.compile(r"<head[^>]*>", re.IGNORECASE)
_HTML_OPEN_RE = re.compile(r"<html[^>]*>", re.IGNORECASE)
_BODY_OPEN_RE = re.compile(r"<body[^>]*>", re.IGNORECASE)
_NAV_RE = re.compile(r"class=[\"']site-nav[\"']", re.IGNORECASE)
_NAV_BLOCK_RE = re.compile(r"<nav\b[^>]*class=[\"']site-nav[\"'][^>]*>.*?</nav>", re.IGNORECASE | re.DOTALL)
_HREF_RE = re.compile(r"href=(?P<quote>[\"'])(?P<value>[^\"']*)(?P=quote)", re.IGNORECASE)
_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")
_PROMPT_BLOCK_RE = re.compile(
    r"(?m)^===\s*[^=]+?===[ \t]*(?:\n(?!\s*<|\s*===).*)*"
)

_HIDE_SCROLLBAR_STYLE = (
    "<style id=\"ic-hide-scrollbar\">\n"
    "html, body {\n"
    "  height: 100%;\n"
    "  overflow: auto;\n"
    "  -ms-overflow-style: none;\n"
    "  scrollbar-width: none;\n"
    "}\n"
    "html::-webkit-scrollbar,\n"
    "body::-webkit-scrollbar {\n"
    "  width: 0;\n"
    "  height: 0;\n"
    "  display: none;\n"
    "}\n"
    "</style>"
)


def inline_css(html: str, css: Optional[str]) -> str:
    """Inline CSS into HTML by injecting a <style> tag."""
    if css is None or not str(css).strip():
        return html

    style_block = f"<style>\n{css.strip()}\n</style>"
    if not html:
        return style_block

    head_close_match = _HEAD_CLOSE_RE.search(html)
    if head_close_match:
        insert_at = head_close_match.start()
        return f"{html[:insert_at]}{style_block}{html[insert_at:]}"

    head_open_match = _HEAD_OPEN_RE.search(html)
    if head_open_match:
        insert_at = head_open_match.end()
        return f"{html[:insert_at]}{style_block}{html[insert_at:]}"

    html_open_match = _HTML_OPEN_RE.search(html)
    if html_open_match:
        insert_at = html_open_match.end()
        head_block = f"<head>{style_block}</head>"
        return f"{html[:insert_at]}{head_block}{html[insert_at:]}"

    return f"{style_block}{html}"


def inject_hide_scrollbar_style(html: str) -> str:
    if not html:
        return html
    if "id=\"ic-hide-scrollbar\"" in html:
        return html

    head_close_match = _HEAD_CLOSE_RE.search(html)
    if head_close_match:
        insert_at = head_close_match.start()
        return f"{html[:insert_at]}{_HIDE_SCROLLBAR_STYLE}{html[insert_at:]}"

    head_open_match = _HEAD_OPEN_RE.search(html)
    if head_open_match:
        insert_at = head_open_match.end()
        return f"{html[:insert_at]}{_HIDE_SCROLLBAR_STYLE}{html[insert_at:]}"

    html_open_match = _HTML_OPEN_RE.search(html)
    if html_open_match:
        insert_at = html_open_match.end()
        head_block = f"<head>{_HIDE_SCROLLBAR_STYLE}</head>"
        return f"{html[:insert_at]}{head_block}{html[insert_at:]}"

    return f"{_HIDE_SCROLLBAR_STYLE}{html}"


def build_nav_html(
    nav_items: Sequence[object],
    *,
    current_slug: str,
    all_pages: Optional[Sequence[str]] = None,
) -> str:
    resolved_items = _coerce_nav_items(nav_items)
    resolved_items = _ensure_all_pages(resolved_items, all_pages)

    links: List[str] = []
    for item in resolved_items:
        slug = item["slug"]
        label = item["label"]
        href = _resolve_page_href(slug)
        classes = "nav-link"
        if slug == current_slug:
            classes = f"{classes} active"
        links.append(f"<a class=\"{classes}\" href=\"{href}\">{label}</a>")

    if not links:
        return ""

    return (
        "<nav class=\"site-nav\">"
        "<div class=\"nav-container\">"
        + "".join(links)
        + "</div></nav>"
    )


def ensure_nav_html(html: str, nav_html: str) -> str:
    if not nav_html:
        return html
    if _NAV_RE.search(html or ""):
        return html
    match = _BODY_OPEN_RE.search(html or "")
    if match:
        insert_at = match.end()
        return f"{html[:insert_at]}{nav_html}{html[insert_at:]}"
    return f"{nav_html}{html}"


def extract_nav_html(html: str) -> str:
    if not html:
        return ""
    match = _NAV_BLOCK_RE.search(html)
    return match.group(0) if match else ""


def replace_nav_html(html: str, nav_html: str) -> str:
    if not nav_html:
        return html
    if not html:
        return nav_html
    if _NAV_BLOCK_RE.search(html):
        return _NAV_BLOCK_RE.sub(nav_html, html, count=1)
    return ensure_nav_html(html, nav_html)


def ensure_css_link(html: str, href: str) -> str:
    if not href:
        return html
    if href in (html or ""):
        return html
    link_tag = f"<link rel=\"stylesheet\" href=\"{href}\">"
    if not html:
        return link_tag

    head_close_match = _HEAD_CLOSE_RE.search(html)
    if head_close_match:
        insert_at = head_close_match.start()
        return f"{html[:insert_at]}{link_tag}{html[insert_at:]}"

    head_open_match = _HEAD_OPEN_RE.search(html)
    if head_open_match:
        insert_at = head_open_match.end()
        return f"{html[:insert_at]}{link_tag}{html[insert_at:]}"

    html_open_match = _HTML_OPEN_RE.search(html)
    if html_open_match:
        insert_at = html_open_match.end()
        head_block = f"<head>{link_tag}</head>"
        return f"{html[:insert_at]}{head_block}{html[insert_at:]}"

    return f"{link_tag}{html}"


def normalize_internal_links(
    html: str,
    *,
    all_pages: Sequence[str],
) -> Tuple[str, List[str]]:
    if not html:
        return html, []
    resolved_pages = {slug for slug in all_pages if slug}
    if not resolved_pages:
        return html, []

    warnings: List[str] = []

    def _replace(match: re.Match[str]) -> str:
        quote = match.group("quote")
        value = match.group("value")
        updated, warning_slug = _normalize_href(value, resolved_pages)
        if warning_slug:
            warnings.append(warning_slug)
        return f"href={quote}{updated}{quote}"

    updated_html = _HREF_RE.sub(_replace, html)
    return updated_html, sorted(set(warnings))


def strip_prompt_artifacts(html: str) -> str:
    if not html:
        return html
    cleaned = re.sub(
        r"<INTERVIEW_ANSWERS>.*?</INTERVIEW_ANSWERS>",
        "",
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    cleaned = re.sub(r"(?mi)^\s*Answer summary:.*$", "", cleaned)
    cleaned = re.sub(r"(?mi)^\s*Collected info:.*$", "", cleaned)
    cleaned = re.sub(r"(?mi)^\s*ProductDoc excerpt:.*$", "", cleaned)
    cleaned = _PROMPT_BLOCK_RE.sub("", cleaned)
    if cleaned != html:
        cleaned = re.sub(
            r"(?mi)^\s*(multi[- ]?page(s)?)\s*$",
            "",
            cleaned,
        )
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned


def rewrite_internal_links_for_export(
    html: str,
    *,
    current_slug: str,
    all_pages: Sequence[str],
) -> Tuple[str, List[str]]:
    if not html:
        return html, []
    resolved_pages = {slug for slug in all_pages if slug}
    if not resolved_pages:
        return html, []

    warnings: List[str] = []

    def _replace(match: re.Match[str]) -> str:
        quote = match.group("quote")
        value = match.group("value")
        updated, warning_slug = _rewrite_href_for_export(value, current_slug, resolved_pages)
        if warning_slug:
            warnings.append(warning_slug)
        return f"href={quote}{updated}{quote}"

    updated_html = _HREF_RE.sub(_replace, html)
    return updated_html, sorted(set(warnings))


def extract_nav_slugs(nav_html: str) -> List[str]:
    if not nav_html:
        return []
    slugs: List[str] = []
    for match in _HREF_RE.finditer(nav_html):
        value = match.group("value")
        slug = _slug_from_href(value)
        if slug:
            slugs.append(slug)
    return slugs


def _coerce_nav_items(nav_items: Sequence[object]) -> List[dict]:
    resolved: List[dict] = []
    for idx, item in enumerate(nav_items or []):
        payload: dict
        if hasattr(item, "model_dump"):
            payload = item.model_dump()
        elif hasattr(item, "dict"):
            payload = item.dict()
        elif isinstance(item, dict):
            payload = item
        else:
            continue
        slug = str(payload.get("slug") or "").strip()
        if not slug:
            continue
        label = str(payload.get("label") or "").strip() or _label_from_slug(slug)
        order_value = payload.get("order", idx)
        try:
            order = int(order_value)
        except (TypeError, ValueError):
            order = idx
        resolved.append({"slug": slug, "label": label, "order": order})
    resolved.sort(key=lambda item: item["order"])
    return resolved


def _ensure_all_pages(items: List[dict], all_pages: Optional[Sequence[str]]) -> List[dict]:
    if not all_pages:
        return items
    seen = {item["slug"] for item in items}
    extra: List[dict] = []
    base_order = items[-1]["order"] if items else 0
    for offset, slug in enumerate(all_pages):
        if not slug or slug in seen:
            continue
        extra.append(
            {
                "slug": slug,
                "label": _label_from_slug(slug),
                "order": base_order + offset + 1,
            }
        )
    return items + extra


def _label_from_slug(slug: str) -> str:
    return slug.replace("-", " ").title()


def _resolve_page_href(slug: str) -> str:
    if slug == "index":
        return "index.html"
    return f"pages/{slug}.html"


def _rewrite_href_for_export(
    value: str,
    current_slug: str,
    allowed_pages: Iterable[str],
) -> Tuple[str, Optional[str]]:
    raw = (value or "").strip()
    if not raw:
        return raw, None
    if raw.startswith("#") or raw.startswith("//") or _SCHEME_RE.match(raw):
        return raw, None

    base, query, fragment = _split_href(raw)
    base = base.lstrip("/")
    slug = _slug_from_href(base)
    if not slug:
        return raw, None

    if slug not in allowed_pages:
        return raw, slug

    if slug == "index":
        resolved = "index.html" if current_slug == "index" else "../index.html"
    else:
        if current_slug == "index":
            resolved = f"pages/{slug}.html"
        else:
            resolved = f"{slug}.html"

    suffix = ""
    if query:
        suffix += f"?{query}"
    if fragment:
        suffix += f"#{fragment}"
    return f"{resolved}{suffix}", None


def _split_href(value: str) -> Tuple[str, str, str]:
    base = value
    fragment = ""
    query = ""
    if "#" in base:
        base, fragment = base.split("#", 1)
    if "?" in base:
        base, query = base.split("?", 1)
    return base, query, fragment


def _slug_from_href(value: str) -> Optional[str]:
    raw = (value or "").strip()
    if not raw:
        return None
    raw = raw.split("#", 1)[0].split("?", 1)[0]
    if not raw:
        return None
    if raw.startswith("./"):
        raw = raw[2:]
    while raw.startswith("../"):
        raw = raw[3:]
    if raw == "index.html":
        return "index"
    if raw.startswith("pages/"):
        raw = raw[len("pages/") :]
    if raw.endswith(".html"):
        raw = raw[: -len(".html")]
    if raw == "index":
        return "index"
    if not raw:
        return None
    if "/" in raw:
        return None
    return raw


def _normalize_href(value: str, allowed_pages: Iterable[str]) -> Tuple[str, Optional[str]]:
    raw = (value or "").strip()
    if not raw:
        return raw, None
    if raw.startswith("#"):
        return raw, None
    if raw.startswith("//"):
        return raw, None
    if _SCHEME_RE.match(raw):
        return raw, None
    if raw.startswith("../"):
        return raw, None

    fragment = ""
    query = ""
    base = raw
    if "#" in base:
        base, fragment = base.split("#", 1)
    if "?" in base:
        base, query = base.split("?", 1)
    if not base:
        return raw, None

    if base.startswith("./"):
        base = base[2:]
    if base.startswith("/"):
        base = base[1:]
    if not base:
        return raw, None

    if re.search(r"\.[a-zA-Z0-9]+$", base) and not base.endswith(".html"):
        return raw, None

    if base.startswith("pages/"):
        base = base[len("pages/") :]
    if base.endswith(".html"):
        base = base[: -len(".html")]
    if "/" in base:
        return raw, None

    if base in allowed_pages:
        normalized = _resolve_page_href(base)
        suffix = ""
        if query:
            suffix += f"?{query}"
        if fragment:
            suffix += f"#{fragment}"
        return f"{normalized}{suffix}", None

    return raw, base


__all__ = [
    "inline_css",
    "inject_hide_scrollbar_style",
    "build_nav_html",
    "ensure_nav_html",
    "ensure_css_link",
    "normalize_internal_links",
    "extract_nav_html",
    "replace_nav_html",
    "extract_nav_slugs",
    "rewrite_internal_links_for_export",
]
