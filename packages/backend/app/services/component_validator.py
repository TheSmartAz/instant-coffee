from __future__ import annotations

import difflib
import json
from typing import Any, Dict, List

from .component_registry import slugify_component_id


def validate_page_schema(schema: dict, registry: dict) -> List[str]:
    """Validate that page schema components exist in the registry."""
    errors: List[str] = []
    registered_ids = _registered_component_ids(registry)
    if not registered_ids:
        return ["registry: no components registered"]

    components = schema.get("components")
    if not isinstance(components, list):
        return ["schema.components: expected list"]

    def check_component(comp: Any, path: str) -> None:
        if not isinstance(comp, dict):
            errors.append(f"{path}: invalid component")
            return
        comp_id = comp.get("id")
        if not comp_id:
            errors.append(f"{path}: missing component id")
        elif comp_id not in registered_ids:
            errors.append(f"{path}: unregistered component '{comp_id}'")
        children = comp.get("children")
        if isinstance(children, list):
            for idx, child in enumerate(children):
                check_component(child, f"{path}.children[{idx}]")

    for idx, comp in enumerate(components):
        check_component(comp, f"components[{idx}]")

    return errors


def auto_fix_unknown_components(schema: dict, registry: dict) -> dict:
    """Replace unknown components with closest registry match."""
    if not isinstance(schema, dict):
        return schema
    registered_ids = _registered_component_ids(registry)
    if not registered_ids:
        return schema

    try:
        working = json.loads(json.dumps(schema))
    except (TypeError, ValueError):
        working = dict(schema)

    normalized_map = _normalized_id_map(registered_ids)
    normalized_ids = list(normalized_map.keys())

    def resolve_id(value: Any) -> str | None:
        if not value:
            return None
        raw = str(value)
        if raw in registered_ids:
            return raw
        normalized = slugify_component_id(raw)
        if normalized in normalized_map:
            return normalized_map[normalized]
        if normalized_ids:
            matches = difflib.get_close_matches(normalized, normalized_ids, n=1, cutoff=0.6)
            if matches:
                return normalized_map[matches[0]]
        return raw

    def rewrite_component(comp: Any) -> None:
        if not isinstance(comp, dict):
            return
        comp_id = comp.get("id")
        resolved = resolve_id(comp_id)
        if resolved is not None:
            comp["id"] = resolved
        children = comp.get("children")
        if isinstance(children, list):
            for child in children:
                rewrite_component(child)

    components = working.get("components")
    if isinstance(components, list):
        for comp in components:
            rewrite_component(comp)

    return working


def _registered_component_ids(registry: dict) -> set[str]:
    components = registry.get("components") if isinstance(registry, dict) else None
    if not isinstance(components, list):
        return set()
    ids = {
        str(item.get("id"))
        for item in components
        if isinstance(item, dict) and item.get("id")
    }
    return ids


def _normalized_id_map(ids: set[str]) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for comp_id in ids:
        normalized = slugify_component_id(comp_id)
        if normalized and normalized not in mapping:
            mapping[normalized] = comp_id
    return mapping


__all__ = ["validate_page_schema", "auto_fix_unknown_components"]
