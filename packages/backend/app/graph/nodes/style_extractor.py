from __future__ import annotations

from typing import Any

from ...config import get_settings
from ...schemas.asset import AssetRef, AssetRegistry
from ...services.style_extractor import StyleExtractorService


def _extract_style_refs(assets: Any) -> list[Any]:
    if assets is None:
        return []
    if isinstance(assets, AssetRegistry):
        return list(assets.style_refs)
    if isinstance(assets, dict):
        return assets.get("style_refs") or assets.get("styleRefs") or []
    return getattr(assets, "style_refs", []) or []


def _extract_url(ref: Any) -> str | None:
    if isinstance(ref, AssetRef):
        return ref.url
    if isinstance(ref, dict):
        return ref.get("url")
    return getattr(ref, "url", None)


def _with_style_tokens(state: Any, tokens: Any) -> dict:
    if isinstance(state, dict):
        updated = dict(state)
    else:
        updated = {}
    updated["style_tokens"] = tokens
    return updated


async def style_extractor_node(state: Any) -> dict:
    settings = get_settings()
    if not settings.style_extractor_enabled:
        return _with_style_tokens(state, None)
    assets = None
    if isinstance(state, dict):
        assets = state.get("assets")
    else:
        assets = getattr(state, "assets", None)

    style_refs = _extract_style_refs(assets)
    if not style_refs:
        return _with_style_tokens(state, None)

    extractor = StyleExtractorService()
    extracted = None
    for ref in style_refs:
        url = _extract_url(ref)
        if not url:
            continue
        extracted = await extractor.extract_style_tokens(url)
        if extracted:
            break

    if extracted:
        return _with_style_tokens(state, extracted.model_dump())
    return _with_style_tokens(state, None)


__all__ = ["style_extractor_node"]
