from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ...renderer.builder import BuildError, ReactSSGBuilder
from ...schemas.session_metadata import BuildInfo, BuildStatus


def _as_dict(state: Any) -> dict:
    if isinstance(state, dict):
        return dict(state)
    if hasattr(state, "__dict__"):
        return dict(state.__dict__)
    return {}


def _normalize_error(exc: Exception) -> str:
    if isinstance(exc, BuildError):
        return exc.summary()
    return str(exc)


async def render_node(state: Any, *, event_emitter: Any | None = None) -> dict:
    updated = _as_dict(state)
    session_id = updated.get("session_id")
    page_schemas = updated.get("page_schemas") or []
    component_registry = updated.get("component_registry") or {}
    style_tokens = updated.get("style_tokens") or {}
    assets = updated.get("assets")

    if not session_id:
        error = "Missing session_id for build"
        updated["build_status"] = BuildStatus.FAILED.value
        updated["build_artifacts"] = BuildInfo(
            status=BuildStatus.FAILED,
            error=error,
            pages=[],
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        ).model_dump(mode="json", exclude_none=True)
        updated["error"] = error
        return updated

    if not isinstance(page_schemas, list) or not page_schemas:
        started_at = datetime.now(timezone.utc)
        updated["build_status"] = BuildStatus.SUCCESS.value
        updated["build_artifacts"] = BuildInfo(
            status=BuildStatus.SUCCESS,
            pages=[],
            started_at=started_at,
            completed_at=started_at,
        ).model_dump(mode="json", exclude_none=True)
        updated["error"] = None
        return updated

    updated["build_status"] = BuildStatus.BUILDING.value
    started_at = datetime.now(timezone.utc)

    emitter = event_emitter if hasattr(event_emitter, "emit") else None
    builder = ReactSSGBuilder(session_id, event_emitter=emitter)

    try:
        result = await builder.build(
            page_schemas=page_schemas,
            component_registry=component_registry,
            style_tokens=style_tokens,
            assets=assets,
        )
    except Exception as exc:
        completed_at = datetime.now(timezone.utc)
        error = _normalize_error(exc)
        updated["build_status"] = BuildStatus.FAILED.value
        updated["build_artifacts"] = BuildInfo(
            status=BuildStatus.FAILED,
            error=error,
            pages=[],
            started_at=started_at,
            completed_at=completed_at,
        ).model_dump(mode="json", exclude_none=True)
        updated["error"] = error
        return updated

    completed_at = datetime.now(timezone.utc)
    pages = result.get("pages") if isinstance(result, dict) else []
    dist_path = result.get("dist_path") if isinstance(result, dict) else None

    updated["build_status"] = BuildStatus.SUCCESS.value
    updated["build_artifacts"] = BuildInfo(
        status=BuildStatus.SUCCESS,
        pages=pages or [],
        dist_path=dist_path,
        started_at=started_at,
        completed_at=completed_at,
    ).model_dump(mode="json", exclude_none=True)
    updated["error"] = None

    return updated


__all__ = ["render_node"]
