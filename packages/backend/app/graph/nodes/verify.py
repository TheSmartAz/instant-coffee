from __future__ import annotations

import re
from typing import Any

from pathlib import Path

from ...config import get_settings

_TEMPLATE_INDEX_HTML = (
    Path(__file__).resolve().parents[2] / "renderer" / "templates" / "react-ssg" / "index.html"
)
_TEMPLATE_APP_TSX = (
    Path(__file__).resolve().parents[2] / "renderer" / "templates" / "react-ssg" / "src" / "App.tsx"
)


def _template_checks() -> tuple[bool, bool]:
    viewport_ok = True
    app_entry_ok = True
    try:
        content = _TEMPLATE_INDEX_HTML.read_text(encoding="utf-8")
        viewport_ok = "name=\"viewport\"" in content or "name='viewport'" in content
    except Exception:
        viewport_ok = False
    try:
        app_content = _TEMPLATE_APP_TSX.read_text(encoding="utf-8")
        app_entry_ok = "id=\"app\"" in app_content or "id='app'" in app_content
    except Exception:
        app_entry_ok = False
    return viewport_ok, app_entry_ok

_SENSITIVE_PATTERNS = (
    re.compile(r"(?i)\b(api[_-]?key|secret|token|password)\b\s*[:=]\s*['\"]?[A-Za-z0-9_\-\.]{8,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9_\-\.]{16,}"),
)


def _as_dict(state: Any) -> dict:
    if isinstance(state, dict):
        return dict(state)
    if hasattr(state, "__dict__"):
        return dict(state.__dict__)
    return {}


def _check_build(state: dict[str, Any]) -> dict[str, Any]:
    build_status = str(state.get("build_status") or "pending").lower()
    error = state.get("error")
    if build_status == "failed" or error:
        return {
            "name": "build",
            "passed": False,
            "details": f"Build status={build_status}; error={error or 'unknown'}",
            "severity": "error",
        }
    return {
        "name": "build",
        "passed": True,
        "details": "No fatal build error in state before render",
        "severity": "info",
    }


def _check_structure(state: dict[str, Any]) -> dict[str, Any]:
    schemas = state.get("page_schemas") or []
    if not isinstance(schemas, list) or not schemas:
        return {
            "name": "structure",
            "passed": False,
            "details": "No page_schemas generated",
            "severity": "error",
        }

    has_index = any(
        isinstance(schema, dict) and str(schema.get("slug") or "").strip().lower() == "index"
        for schema in schemas
    )
    if not has_index:
        return {
            "name": "structure",
            "passed": False,
            "details": "Missing required index page",
            "severity": "error",
        }

    _, app_entry_ok = _template_checks()
    if not app_entry_ok:
        return {
            "name": "structure",
            "passed": False,
            "details": "Missing #app entry node in renderer template",
            "severity": "error",
        }

    return {
        "name": "structure",
        "passed": True,
        "details": "index page exists and #app entry contract is satisfied",
        "severity": "info",
    }


def _check_mobile(state: dict[str, Any]) -> dict[str, Any]:
    viewport_ok, _ = _template_checks()
    schemas = state.get("page_schemas") or []
    mobile_ok = True
    details: list[str] = []

    if not isinstance(schemas, list) or not schemas:
        mobile_ok = False
        details.append("No page schemas for mobile validation")
    else:
        for schema in schemas:
            if not isinstance(schema, dict):
                continue
            layout = str(schema.get("layout") or "default").lower()
            if layout not in {"default", "fullscreen", "sidebar"}:
                mobile_ok = False
                details.append(f"Unsupported layout '{layout}' for mobile shell")

            components = schema.get("components")
            if not isinstance(components, list):
                mobile_ok = False
                details.append(f"Page '{schema.get('slug')}' has invalid components")

    if mobile_ok and not viewport_ok:
        mobile_ok = False
        details.append("Missing viewport meta tag in renderer template")

    if mobile_ok:
        return {
            "name": "mobile",
            "passed": True,
            "details": "Viewport and mobile shell constraints satisfied",
            "severity": "info",
        }

    return {
        "name": "mobile",
        "passed": False,
        "details": "; ".join(details) or "Mobile validation failed",
        "severity": "error",
    }


def _check_security(state: dict[str, Any]) -> dict[str, Any]:
    candidates = []
    for key in (
        "product_doc",
        "data_model",
        "style_tokens",
        "component_registry",
        "page_schemas",
        "build_artifacts",
    ):
        value = state.get(key)
        if value is None:
            continue
        candidates.append(str(value))

    haystack = "\n".join(candidates)
    for pattern in _SENSITIVE_PATTERNS:
        match = pattern.search(haystack)
        if match:
            snippet = match.group(0)
            return {
                "name": "security",
                "passed": False,
                "details": f"Sensitive pattern detected: {snippet[:80]}",
                "severity": "error",
            }

    return {
        "name": "security",
        "passed": True,
        "details": "No sensitive pattern detected",
        "severity": "info",
    }


def _build_report(state: dict[str, Any], *, retry_count: int) -> dict[str, Any]:
    checks = [
        _check_build(state),
        _check_structure(state),
        _check_mobile(state),
        _check_security(state),
    ]
    overall_passed = all(bool(item.get("passed")) for item in checks)
    return {
        "checks": checks,
        "overall_passed": overall_passed,
        "retry_count": retry_count,
    }


async def verify_node(state: Any) -> dict[str, Any]:
    updated = _as_dict(state)
    settings = get_settings()

    if not bool(getattr(settings, "verify_gate_enabled", True)):
        updated["verify_blocked"] = False
        updated["verify_report"] = {
            "checks": [],
            "overall_passed": True,
            "retry_count": 0,
            "skipped": True,
        }
        updated["verify_action"] = "pass"
        return updated

    existing_report = updated.get("verify_report")
    previous_retry = 0
    if isinstance(existing_report, dict):
        try:
            previous_retry = int(existing_report.get("retry_count") or 0)
        except Exception:
            previous_retry = 0

    report = _build_report(updated, retry_count=previous_retry)
    updated["verify_report"] = report

    if report["overall_passed"]:
        updated["verify_blocked"] = False
        updated["verify_action"] = "pass"
        return updated

    max_retry = max(int(getattr(settings, "verify_gate_max_retry", 1) or 0), 0)
    auto_fix = bool(getattr(settings, "verify_gate_auto_fix_enabled", True))

    if auto_fix and previous_retry < max_retry:
        next_retry = previous_retry + 1
        retry_report = _build_report(updated, retry_count=next_retry)
        updated["verify_report"] = retry_report
        if retry_report["overall_passed"]:
            updated["verify_blocked"] = False
            updated["verify_action"] = "pass"
            return updated

    updated["verify_blocked"] = True
    updated["verify_action"] = "wait"
    return updated


__all__ = [
    "verify_node",
]
