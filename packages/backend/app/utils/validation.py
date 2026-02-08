from __future__ import annotations

import re
from typing import Iterable, Optional, Tuple

from ..schemas.validation import AutoChecks

_STYLE_BLOCK_RE = re.compile(r"<style[^>]*>(.*?)</style>", re.DOTALL | re.IGNORECASE)
_STYLE_ATTR_RE = re.compile(r"style=[\"'](.*?)[\"']", re.DOTALL | re.IGNORECASE)
_HEX_COLOR_RE = re.compile(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})")
_RGB_COLOR_RE = re.compile(r"rgba?\(([^)]+)\)", re.IGNORECASE)
_VAR_RE = re.compile(r"var\(\s*--([a-zA-Z0-9_-]+)(?:\s*,\s*([^)]+))?\)")

_DEFAULT_TEXT = (0.0667, 0.0667, 0.0667)  # #111111
_DEFAULT_BG = (1.0, 1.0, 1.0)  # #FFFFFF

_TITLE_SELECTORS = ("h1", "h2", "h3", ".title", ".headline", ".hero-title", ".display")
_BODY_SELECTORS = ("body", "p", ".body", ".text", ".copy")
_CTA_SELECTORS = ("button", ".btn", ".cta", ".primary", ".call-to-action", "a.btn", "a.button")


def run_auto_checks(html: str) -> AutoChecks:
    contrast_pass, contrast_ratio = check_wcag_contrast(html)
    line_pass, line_value = check_line_height(html)
    scale_pass, scale_desc = check_type_scale(html)
    return AutoChecks(
        wcag_contrast="pass" if contrast_pass else "fail",
        contrast_ratio=contrast_ratio,
        line_height="pass" if line_pass else "fail",
        line_height_value=line_value,
        type_scale="pass" if scale_pass else "fail",
        scale_difference=scale_desc,
    )


def check_wcag_contrast(html: str) -> Tuple[bool, Optional[float]]:
    css = _extract_style_blocks(html)
    rules = _parse_css_rules(css)
    variables = _extract_css_variables(rules)

    body_color = _resolve_color(_find_style_value(rules, ("body", "html"), "color"), variables)
    body_bg = _resolve_color(
        _find_style_value(rules, ("body", "html"), "background-color")
        or _find_style_value(rules, ("body", "html"), "background"),
        variables,
    )

    text_color = body_color or _DEFAULT_TEXT
    bg_color = body_bg or _DEFAULT_BG

    pairs: list[Tuple[Tuple[float, float, float], Tuple[float, float, float]]] = [(text_color, bg_color)]

    for selector, props in rules:
        color = _resolve_color(props.get("color"), variables) or text_color
        background = _resolve_color(
            props.get("background-color") or props.get("background"),
            variables,
        ) or bg_color
        if color and background:
            pairs.append((color, background))

    for style_text in _extract_inline_styles(html):
        props = _parse_declarations(style_text)
        color = _resolve_color(props.get("color"), variables) or text_color
        background = _resolve_color(
            props.get("background-color") or props.get("background"),
            variables,
        ) or bg_color
        if color and background:
            pairs.append((color, background))

    ratios = [
        _contrast_ratio(color, background)
        for color, background in pairs
        if color is not None and background is not None
    ]
    if not ratios:
        return False, None

    min_ratio = min(ratios)
    return min_ratio >= 4.5, round(min_ratio, 2)


def check_line_height(html: str) -> Tuple[bool, Optional[float]]:
    css = _extract_style_blocks(html)
    rules = _parse_css_rules(css)
    variables = _extract_css_variables(rules)

    font_size = _parse_length(
        _find_style_value(rules, ("body", "html"), "font-size"),
        variables=variables,
    )
    if font_size is None:
        font_size = 16.0

    line_height_value = _parse_line_height(
        _find_style_value(rules, ("body",), "line-height")
        or _find_inline_body_line_height(html),
        base_font_size=font_size,
        variables=variables,
    )
    if line_height_value is None:
        return False, None

    passes = 1.4 <= line_height_value <= 1.8
    return passes, round(line_height_value, 2)


def check_type_scale(html: str) -> Tuple[bool, Optional[str]]:
    css = _extract_style_blocks(html)
    rules = _parse_css_rules(css)
    variables = _extract_css_variables(rules)

    base_font = _parse_length(
        _find_style_value(rules, ("body", "html"), "font-size"),
        variables=variables,
    ) or 16.0

    title_sizes = _collect_font_sizes(rules, variables, base_font, _TITLE_SELECTORS)
    body_sizes = _collect_font_sizes(rules, variables, base_font, _BODY_SELECTORS)
    cta_sizes = _collect_font_sizes(rules, variables, base_font, _CTA_SELECTORS)

    title_sizes.extend(_collect_inline_font_sizes(html, ("h1", "h2", "h3"), base_font, variables))
    body_sizes.extend(_collect_inline_font_sizes(html, ("p",), base_font, variables))
    cta_sizes.extend(_collect_inline_font_sizes(html, ("button", "a"), base_font, variables))

    title = max(title_sizes) if title_sizes else None
    body = min(body_sizes) if body_sizes else None
    cta = max(cta_sizes) if cta_sizes else None

    if title is None or body is None or cta is None:
        missing = []
        if title is None:
            missing.append("title")
        if body is None:
            missing.append("body")
        if cta is None:
            missing.append("cta")
        return False, f"Missing sizes: {', '.join(missing)}"

    title_ok = title >= body * 1.2
    cta_ok = cta >= body and abs(cta - body) >= 2

    description = f"title {title:.1f}px, body {body:.1f}px, cta {cta:.1f}px"
    return title_ok and cta_ok, description


def _extract_style_blocks(html: str) -> str:
    if not html:
        return ""
    blocks = [match.group(1) for match in _STYLE_BLOCK_RE.finditer(html)]
    return "\n".join(blocks)


def _extract_inline_styles(html: str) -> Iterable[str]:
    if not html:
        return []
    return [match.group(1) for match in _STYLE_ATTR_RE.finditer(html)]


def _parse_css_rules(css: str) -> list[tuple[str, dict[str, str]]]:
    cleaned = _strip_css_comments(css)
    rules: list[tuple[str, dict[str, str]]] = []
    i = 0
    length = len(cleaned)
    while i < length:
        start = cleaned.find("{", i)
        if start == -1:
            break
        selector = cleaned[i:start].strip()
        depth = 1
        j = start + 1
        while j < length and depth:
            if cleaned[j] == "{":
                depth += 1
            elif cleaned[j] == "}":
                depth -= 1
            j += 1
        block = cleaned[start + 1 : j - 1].strip()
        if selector.lower().startswith("@media"):
            rules.extend(_parse_css_rules(block))
        elif selector:
            props = _parse_declarations(block)
            if props:
                rules.append((selector, props))
        i = j
    return rules


def _strip_css_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css or "", flags=re.DOTALL)


def _parse_declarations(block: str) -> dict[str, str]:
    props: dict[str, str] = {}
    for part in (block or "").split(";"):
        if ":" not in part:
            continue
        key, value = part.split(":", 1)
        key = key.strip().lower()
        value = value.strip()
        if key:
            props[key] = value
    return props


def _extract_css_variables(rules: Iterable[tuple[str, dict[str, str]]]) -> dict[str, str]:
    variables: dict[str, str] = {}
    for selector, props in rules:
        if ":root" in selector or "html" in selector or "body" in selector:
            for key, value in props.items():
                if key.startswith("--"):
                    variables[key] = value
    return variables


def _find_style_value(rules: Iterable[tuple[str, dict[str, str]]], selectors: Iterable[str], prop: str) -> Optional[str]:
    prop = prop.lower()
    for selector, props in rules:
        lowered = selector.lower()
        if any(sel in lowered for sel in selectors):
            value = props.get(prop)
            if value:
                return value
    return None


def _find_inline_body_line_height(html: str) -> Optional[str]:
    match = re.search(r"<body[^>]*style=[\"'](.*?)[\"']", html or "", re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    props = _parse_declarations(match.group(1))
    return props.get("line-height")


def _collect_font_sizes(
    rules: Iterable[tuple[str, dict[str, str]]],
    variables: dict[str, str],
    base_font: float,
    selectors: Iterable[str],
) -> list[float]:
    sizes: list[float] = []
    for selector, props in rules:
        lowered = selector.lower()
        if any(sel in lowered for sel in selectors):
            size = _parse_length(props.get("font-size"), base_font_size=base_font, variables=variables)
            if size is not None:
                sizes.append(size)
    return sizes


def _collect_inline_font_sizes(
    html: str,
    tags: Iterable[str],
    base_font: float,
    variables: dict[str, str],
) -> list[float]:
    if not html:
        return []
    tag_pattern = "|".join(tags)
    pattern = re.compile(
        rf"<(?:{tag_pattern})\b[^>]*style=[\"'](.*?)[\"']",
        re.IGNORECASE | re.DOTALL,
    )
    sizes: list[float] = []
    for match in pattern.finditer(html):
        props = _parse_declarations(match.group(1))
        size = _parse_length(props.get("font-size"), base_font_size=base_font, variables=variables)
        if size is not None:
            sizes.append(size)
    return sizes


def _parse_length(
    value: Optional[str],
    *,
    base_font_size: float = 16.0,
    variables: Optional[dict[str, str]] = None,
) -> Optional[float]:
    if not value:
        return None
    resolved = _resolve_var(value, variables or {}) or value
    text = str(resolved).strip().lower()
    if text.endswith("px"):
        return _safe_float(text[:-2])
    if text.endswith("rem"):
        return _safe_float(text[:-3]) * base_font_size
    if text.endswith("em"):
        return _safe_float(text[:-2]) * base_font_size
    if re.fullmatch(r"[0-9]+(\.[0-9]+)?", text):
        return _safe_float(text)
    return None


def _parse_line_height(
    value: Optional[str],
    *,
    base_font_size: float,
    variables: Optional[dict[str, str]] = None,
) -> Optional[float]:
    if not value:
        return None
    resolved = _resolve_var(value, variables or {}) or value
    text = str(resolved).strip().lower()
    if re.fullmatch(r"[0-9]+(\.[0-9]+)?", text):
        return _safe_float(text)
    length = _parse_length(text, base_font_size=base_font_size, variables=variables)
    if length is None or base_font_size <= 0:
        return None
    return length / base_font_size


def _resolve_var(value: str, variables: dict[str, str]) -> Optional[str]:
    if not value:
        return None
    match = _VAR_RE.search(value)
    if not match:
        return None
    key = f"--{match.group(1)}"
    fallback = match.group(2)
    if key in variables:
        return variables[key]
    if fallback:
        return fallback.strip()
    return None


def _resolve_color(value: Optional[str], variables: dict[str, str]) -> Optional[Tuple[float, float, float]]:
    if not value:
        return None
    resolved = _resolve_var(value, variables) or value
    raw = _extract_first_color_token(resolved)
    if not raw:
        return None
    if raw.startswith("#"):
        return _parse_hex_color(raw)
    if raw.lower().startswith("rgb"):
        return _parse_rgb_color(raw)
    return None


def _extract_first_color_token(value: str) -> Optional[str]:
    if not value:
        return None
    hex_match = _HEX_COLOR_RE.search(value)
    if hex_match:
        return f"#{hex_match.group(1)}"
    rgb_match = _RGB_COLOR_RE.search(value)
    if rgb_match:
        return rgb_match.group(0)
    return None


def _parse_hex_color(value: str) -> Optional[Tuple[float, float, float]]:
    match = _HEX_COLOR_RE.search(value)
    if not match:
        return None
    raw = match.group(1)
    if len(raw) == 3:
        raw = "".join([c * 2 for c in raw])
    if len(raw) != 6:
        return None
    try:
        r = int(raw[0:2], 16) / 255.0
        g = int(raw[2:4], 16) / 255.0
        b = int(raw[4:6], 16) / 255.0
        return (r, g, b)
    except ValueError:
        return None


def _parse_rgb_color(value: str) -> Optional[Tuple[float, float, float]]:
    match = _RGB_COLOR_RE.search(value)
    if not match:
        return None
    parts = [part.strip() for part in match.group(1).split(",")]
    if len(parts) < 3:
        return None
    channels = []
    for part in parts[:3]:
        if part.endswith("%"):
            channels.append(_clamp(_safe_float(part[:-1]) / 100.0))
        else:
            channels.append(_clamp(_safe_float(part) / 255.0))
    if len(parts) >= 4:
        alpha = _safe_float(parts[3])
        if alpha < 0.9:
            return None
    return (channels[0], channels[1], channels[2])


def _contrast_ratio(color: Tuple[float, float, float], background: Tuple[float, float, float]) -> float:
    l1 = _relative_luminance(color)
    l2 = _relative_luminance(background)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def _relative_luminance(color: Tuple[float, float, float]) -> float:
    r, g, b = color
    return 0.2126 * _linearize(r) + 0.7152 * _linearize(g) + 0.0722 * _linearize(b)


def _linearize(channel: float) -> float:
    if channel <= 0.03928:
        return channel / 12.92
    return ((channel + 0.055) / 1.055) ** 2.4


def _safe_float(value: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


__all__ = [
    "run_auto_checks",
    "check_wcag_contrast",
    "check_line_height",
    "check_type_scale",
]
