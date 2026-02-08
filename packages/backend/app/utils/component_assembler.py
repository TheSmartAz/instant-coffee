from __future__ import annotations

import html as html_lib
import json
import re
from pathlib import Path
from typing import Any, Dict, Optional

_COMPONENT_TAG_RE = re.compile(r"<component\b([^>]*)>(.*?)</component>", re.IGNORECASE | re.DOTALL)
_COMPONENT_SELF_CLOSING_RE = re.compile(r"<component\b([^>]*)/>", re.IGNORECASE)
_ATTR_RE = re.compile(r'([a-zA-Z0-9_-]+)\s*=\s*("([^"]*)"|\'([^\']*)\'|([^\s"\'=<>`]+))')
_SLOT_RE = re.compile(r"{{\s*([\w-]+)\s*}}")
_IF_EQ_RE = re.compile(
    r"{{#if_eq\s+([\w-]+)\s+(['\"])(.*?)\2\s*}}(.*?){{/if_eq}}",
    re.DOTALL | re.IGNORECASE,
)
_HANDLEBARS_RE = re.compile(r"{{[^}]+}}")


def assemble_components(html: str, registry: Dict[str, Any], base_dir: Path, page_slug: Optional[str] = None) -> str:
    if not html or not registry:
        return html
    components = registry.get("components")
    if not isinstance(components, list):
        return html
    component_map = {
        str(item.get("id")): item for item in components if isinstance(item, dict) and item.get("id")
    }
    if not component_map:
        return html

    def replace(match: re.Match) -> str:
        attrs = _parse_attrs(match.group(1))
        comp_id = attrs.get("id") or attrs.get("name")
        if not comp_id:
            return match.group(0)
        component = component_map.get(comp_id)
        if not component:
            return match.group(0)
        file_path = component.get("file") or component.get("path")
        if not file_path:
            return match.group(0)
        fragment_path = base_dir / str(file_path).lstrip("/").replace("\\", "/")
        if not fragment_path.exists():
            return match.group(0)
        try:
            fragment = fragment_path.read_text(encoding="utf-8")
        except Exception:
            return match.group(0)
        data_payload = _parse_json_attr(attrs.get("data") or attrs.get("data-props"))
        default_payload = _default_component_data(comp_id, page_slug)
        slot_defaults = component.get("slots") if isinstance(component.get("slots"), dict) else {}
        merged_payload = _merge_slot_defaults(slot_defaults, {**default_payload, **data_payload})
        if merged_payload:
            fragment = _apply_if_eq_blocks(fragment, merged_payload)
            fragment = _apply_slots(fragment, merged_payload)
        fragment = _strip_handlebars(fragment)
        return fragment

    html = _COMPONENT_TAG_RE.sub(replace, html)
    html = _COMPONENT_SELF_CLOSING_RE.sub(replace, html)
    return html


def _parse_attrs(raw: str) -> Dict[str, str]:
    attrs: Dict[str, str] = {}
    for match in _ATTR_RE.finditer(raw or ""):
        key = match.group(1)
        value = match.group(3) or match.group(4) or match.group(5) or ""
        attrs[key.lower()] = html_lib.unescape(value)
    return attrs


def _parse_json_attr(value: Optional[str]) -> Dict[str, Any]:
    if not value:
        return {}
    raw = html_lib.unescape(value)
    try:
        payload = json.loads(raw)
        return payload if isinstance(payload, dict) else {}
    except json.JSONDecodeError:
        return {}


def _apply_slots(fragment: str, data: Dict[str, Any]) -> str:
    updated = fragment
    for key, value in data.items():
        updated = updated.replace("{{" + str(key) + "}}", str(value))
    return updated


def _merge_slot_defaults(defaults: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    if not defaults and not payload:
        return {}
    merged: Dict[str, Any] = {}
    if isinstance(defaults, dict):
        for key, value in defaults.items():
            if key not in payload and value is not None:
                merged[str(key)] = value
    if isinstance(payload, dict):
        for key, value in payload.items():
            merged[str(key)] = value
    return merged


def _apply_if_eq_blocks(fragment: str, data: Dict[str, Any]) -> str:
    if not fragment:
        return fragment

    def replace(match: re.Match) -> str:
        key = match.group(1)
        expected = match.group(3)
        inner = match.group(4) or ""
        actual = data.get(key)
        return inner if actual is not None and str(actual) == expected else ""

    updated = fragment
    while True:
        next_value = _IF_EQ_RE.sub(replace, updated)
        if next_value == updated:
            return updated
        updated = next_value


def _strip_handlebars(fragment: str) -> str:
    if not fragment:
        return fragment
    cleaned = _HANDLEBARS_RE.sub("", fragment)
    cleaned = _SLOT_RE.sub("", cleaned)
    return cleaned.replace("{}", "")


def _default_component_data(component_id: str, page_slug: Optional[str]) -> Dict[str, Any]:
    if component_id == "bottom-nav":
        slug = (page_slug or "").strip().lower()
        active_tab = "home" if slug in {"", "index"} else slug
        return {"active_tab": active_tab}
    return {}


__all__ = ["assemble_components"]
