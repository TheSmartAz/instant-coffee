from __future__ import annotations

import re
from typing import Optional, Tuple

DEFAULT_PRIMARY = "#2563EB"
DEFAULT_SECONDARY = "#F97316"
DEFAULT_FONT = "system-ui, -apple-system, 'Segoe UI', sans-serif"

_COLOR_KEYWORDS = {
    "blue": "#2563EB",
    "navy": "#1E3A8A",
    "sky": "#38BDF8",
    "cyan": "#06B6D4",
    "teal": "#14B8A6",
    "green": "#16A34A",
    "emerald": "#10B981",
    "lime": "#84CC16",
    "yellow": "#EAB308",
    "amber": "#F59E0B",
    "orange": "#F97316",
    "red": "#EF4444",
    "rose": "#F43F5E",
    "pink": "#EC4899",
    "purple": "#8B5CF6",
    "violet": "#7C3AED",
    "indigo": "#4F46E5",
    "slate": "#475569",
    "gray": "#6B7280",
    "grey": "#6B7280",
    "black": "#111827",
    "white": "#FFFFFF",
    "beige": "#E7E5E4",
    "cream": "#FEF3C7",
    "brown": "#92400E",
}

_FONT_BY_STYLE = {
    "modern": "Manrope, sans-serif",
    "minimal": "DM Sans, sans-serif",
    "clean": "DM Sans, sans-serif",
    "playful": "Poppins, sans-serif",
    "friendly": "Poppins, sans-serif",
    "elegant": "Cormorant Garamond, serif",
    "classic": "Merriweather, serif",
    "luxury": "Playfair Display, serif",
    "editorial": "Source Serif 4, serif",
    "tech": "Space Grotesk, sans-serif",
    "futuristic": "Space Grotesk, sans-serif",
    "retro": "Fira Sans, sans-serif",
}

_FONT_BY_TONE = {
    "professional": "IBM Plex Sans, sans-serif",
    "serious": "IBM Plex Sans, sans-serif",
    "bold": "Montserrat, sans-serif",
    "warm": "Nunito, sans-serif",
    "soft": "Nunito, sans-serif",
    "youthful": "Poppins, sans-serif",
}

_HEX_PATTERN = re.compile(r"#([0-9A-Fa-f]{6})")


def normalize_hex_color(value: Optional[str], fallback: Optional[str]) -> Optional[str]:
    if not value:
        return fallback
    match = _HEX_PATTERN.search(value)
    if not match:
        return fallback
    return f"#{match.group(1).upper()}"


def parse_color_preferences(color_preference: Optional[str]) -> Tuple[str, Optional[str]]:
    if not color_preference:
        return DEFAULT_PRIMARY, None
    raw = color_preference.strip()
    if not raw:
        return DEFAULT_PRIMARY, None

    hex_matches = _HEX_PATTERN.findall(raw)
    if hex_matches:
        primary = f"#{hex_matches[0].upper()}"
        secondary = f"#{hex_matches[1].upper()}" if len(hex_matches) > 1 else None
        return primary, secondary

    lower = raw.lower()
    found = []
    for keyword, color in _COLOR_KEYWORDS.items():
        if keyword in lower:
            found.append(color)
    if found:
        primary = found[0]
        secondary = found[1] if len(found) > 1 else None
        return primary, secondary

    return DEFAULT_PRIMARY, None


def _pick_font_family(style: Optional[str], tone: Optional[str]) -> str:
    combined = " ".join(filter(None, [style, tone])).lower()
    for keyword, font in _FONT_BY_TONE.items():
        if keyword in combined:
            return font
    for keyword, font in _FONT_BY_STYLE.items():
        if keyword in combined:
            return font
    return DEFAULT_FONT


def build_global_style(design_direction: Optional[dict]) -> dict:
    design_direction = design_direction or {}
    style = design_direction.get("style") or ""
    tone = design_direction.get("tone") or ""
    color_pref = design_direction.get("color_preference") or design_direction.get("colorPreference")

    primary_color, secondary_color = parse_color_preferences(color_pref)
    font_family = _pick_font_family(style, tone)

    return {
        "primary_color": primary_color,
        "secondary_color": secondary_color,
        "font_family": font_family,
        "font_size_base": "16px",
        "font_size_heading": "24px",
        "button_height": "44px",
        "spacing_unit": "8px",
        "border_radius": "8px",
    }

def normalize_global_style(
    raw_style: Optional[dict],
    design_direction: Optional[dict] = None,
) -> dict:
    default_style = build_global_style(design_direction or {})
    resolved = raw_style if isinstance(raw_style, dict) else {}

    primary_color = normalize_hex_color(
        resolved.get("primary_color") or resolved.get("primaryColor"),
        default_style.get("primary_color"),
    )
    secondary_color = normalize_hex_color(
        resolved.get("secondary_color") or resolved.get("secondaryColor"),
        default_style.get("secondary_color"),
    )
    font_family = resolved.get("font_family") or resolved.get("fontFamily") or default_style.get("font_family")

    return {
        "primary_color": primary_color,
        "secondary_color": secondary_color,
        "font_family": str(font_family),
        "font_size_base": str(
            resolved.get("font_size_base") or resolved.get("fontSizeBase") or default_style.get("font_size_base")
        ),
        "font_size_heading": str(
            resolved.get("font_size_heading")
            or resolved.get("fontSizeHeading")
            or default_style.get("font_size_heading")
        ),
        "button_height": str(
            resolved.get("button_height") or resolved.get("buttonHeight") or default_style.get("button_height")
        ),
        "spacing_unit": str(
            resolved.get("spacing_unit") or resolved.get("spacingUnit") or default_style.get("spacing_unit")
        ),
        "border_radius": str(
            resolved.get("border_radius") or resolved.get("borderRadius") or default_style.get("border_radius")
        ),
    }


def build_global_style_css(global_style: Optional[dict], design_direction: Optional[dict] = None) -> str:
    resolved = normalize_global_style(global_style, design_direction)
    primary = resolved.get("primary_color") or DEFAULT_PRIMARY
    secondary = resolved.get("secondary_color") or primary
    font_family = resolved.get("font_family") or DEFAULT_FONT

    return (
        ":root {\n"
        f"  --primary-color: {primary};\n"
        f"  --secondary-color: {secondary};\n"
        f"  --font-family: {font_family};\n"
        f"  --font-size-base: {resolved.get('font_size_base')};\n"
        f"  --font-size-heading: {resolved.get('font_size_heading')};\n"
        f"  --button-height: {resolved.get('button_height')};\n"
        f"  --spacing-unit: {resolved.get('spacing_unit')};\n"
        f"  --border-radius: {resolved.get('border_radius')};\n"
        "}\n\n"
        "* {\n"
        "  box-sizing: border-box;\n"
        "  margin: 0;\n"
        "  padding: 0;\n"
        "}\n\n"
        "body {\n"
        "  font-family: var(--font-family);\n"
        "  font-size: var(--font-size-base);\n"
        "  line-height: 1.5;\n"
        "  max-width: 430px;\n"
        "  margin: 0 auto;\n"
        "}\n\n"
        ".hide-scrollbar::-webkit-scrollbar {\n"
        "  display: none;\n"
        "}\n\n"
        ".hide-scrollbar {\n"
        "  -ms-overflow-style: none;\n"
        "  scrollbar-width: none;\n"
        "}\n"
    )


def build_site_css(
    global_style: Optional[dict],
    design_direction: Optional[dict] = None,
    *,
    include_nav: bool = True,
) -> str:
    resolved = normalize_global_style(global_style, design_direction)
    primary = resolved.get("primary_color") or DEFAULT_PRIMARY
    secondary = resolved.get("secondary_color") or primary
    font_family = resolved.get("font_family") or DEFAULT_FONT

    return (
        "/* Site-wide Design System */\n"
        "/* Generated from global_style */\n\n"
        ":root {\n"
        f"  --primary-color: {primary};\n"
        f"  --secondary-color: {secondary};\n"
        f"  --font-family: {font_family};\n"
        f"  --font-size-base: {resolved.get('font_size_base')};\n"
        f"  --font-size-heading: {resolved.get('font_size_heading')};\n"
        f"  --button-height: {resolved.get('button_height')};\n"
        f"  --spacing-unit: {resolved.get('spacing_unit')};\n"
        f"  --border-radius: {resolved.get('border_radius')};\n"
        "}\n\n"
        "/* Reset & Base */\n"
        "* {\n"
        "  box-sizing: border-box;\n"
        "  margin: 0;\n"
        "  padding: 0;\n"
        "}\n\n"
        "html, body {\n"
        "  font-family: var(--font-family), -apple-system, BlinkMacSystemFont, sans-serif;\n"
        "  font-size: var(--font-size-base);\n"
        "  line-height: 1.5;\n"
        "  color: #333;\n"
        "  background: #fff;\n"
        "}\n\n"
        "body {\n"
        "  max-width: 430px;\n"
        "  margin: 0 auto;\n"
        "  min-height: 100vh;\n"
        "}\n\n"
        "/* Scrollbar Hide Utility */\n"
        ".hide-scrollbar::-webkit-scrollbar {\n"
        "  display: none;\n"
        "}\n"
        ".hide-scrollbar {\n"
        "  -ms-overflow-style: none;\n"
        "  scrollbar-width: none;\n"
        "}\n\n"
        "/* Navigation */\n"
        + (
            ".site-nav {\n"
            "  position: sticky;\n"
            "  bottom: 0;\n"
            "  background: var(--primary-color);\n"
            "  padding: 12px 16px;\n"
            "  z-index: 100;\n"
            "}\n\n"
            ".nav-container {\n"
            "  display: flex;\n"
            "  gap: 16px;\n"
            "  overflow-x: auto;\n"
            "  -webkit-overflow-scrolling: touch;\n"
            "}\n\n"
            ".nav-link {\n"
            "  color: white;\n"
            "  text-decoration: none;\n"
            "  white-space: nowrap;\n"
            "  padding: 8px 16px;\n"
            "  border-radius: var(--border-radius);\n"
            "  transition: background 0.2s;\n"
            "}\n\n"
            ".nav-link:hover {\n"
            "  background: rgba(255, 255, 255, 0.1);\n"
            "}\n\n"
            ".nav-link.active {\n"
            "  background: rgba(255, 255, 255, 0.2);\n"
            "}\n\n"
            if include_nav
            else ""
        )
        + "/* Buttons */\n"
        "button, .btn {\n"
        "  min-height: var(--button-height);\n"
        "  padding: 0 24px;\n"
        "  border-radius: var(--border-radius);\n"
        "  font-size: var(--font-size-base);\n"
        "  cursor: pointer;\n"
        "  border: none;\n"
        "  background: var(--primary-color);\n"
        "  color: white;\n"
        "}\n\n"
        "button:hover, .btn:hover {\n"
        "  opacity: 0.9;\n"
        "}\n\n"
        "/* Typography */\n"
        "h1, h2, h3 {\n"
        "  font-size: var(--font-size-heading);\n"
        "  line-height: 1.2;\n"
        "  margin-bottom: calc(var(--spacing-unit) * 2);\n"
        "}\n\n"
        "p {\n"
        "  margin-bottom: var(--spacing-unit);\n"
        "}\n"
    )


__all__ = [
    "build_global_style",
    "build_global_style_css",
    "build_site_css",
    "normalize_global_style",
    "normalize_hex_color",
    "parse_color_preferences",
]
