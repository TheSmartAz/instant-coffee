from __future__ import annotations

from typing import TypedDict


_DEFAULT_MAX_TOKENS = 1_000_000
_DEFAULT_CAPABILITIES = ["text"]
_VISION_MARKERS = ("vision",)


class ModelOption(TypedDict, total=False):
    id: str
    label: str
    capabilities: list[str]
    max_tokens: int


class ModelGroup(TypedDict):
    category: str
    base_url: str
    models: list[ModelOption]


# DeepSeek is the only configured provider for this project.
MODEL_GROUPS: list[ModelGroup] = [
    {
        "category": "deepseek",
        "base_url": "https://api.deepseek.com",
        "models": [
            {
                "id": "deepseek-v4-pro",
                "label": "DeepSeek V4 Pro",
                "capabilities": ["text"],
                "max_tokens": 1_000_000,
            },
        ],
    },
]


def get_model_catalog() -> list[dict[str, str]]:
    catalog: list[dict[str, str]] = []
    for group in MODEL_GROUPS:
        category = group["category"]
        base_url = group["base_url"]
        for model in group["models"]:
            model_id = model.get("id")
            if not model_id:
                continue
            capabilities = _normalize_capabilities(model.get("capabilities"), model_id)
            max_tokens = _normalize_max_tokens(model.get("max_tokens"))
            catalog.append(
                {
                    "id": model_id,
                    "label": model.get("label") or model_id,
                    "category": category,
                    "base_url": base_url,
                    "capabilities": capabilities,
                    "max_tokens": max_tokens,
                }
            )
    return catalog


def get_model_entry(model_id: str | None) -> dict[str, str] | None:
    if not model_id:
        return None
    for entry in get_model_catalog():
        if entry["id"] == model_id:
            return entry
    inferred = _normalize_capabilities(None, model_id)
    return {
        "id": model_id,
        "label": model_id,
        "category": "custom",
        "base_url": "",
        "capabilities": inferred,
        "max_tokens": _DEFAULT_MAX_TOKENS,
    }


def get_default_model_id() -> str:
    for entry in get_model_catalog():
        return entry["id"]
    return "deepseek-v4-pro"


def get_default_base_url() -> str:
    for entry in get_model_catalog():
        return entry["base_url"]
    return "https://api.deepseek.com"


def get_model_capabilities(model_id: str | None) -> list[str]:
    entry = get_model_entry(model_id)
    capabilities = entry.get("capabilities") if entry else None
    if isinstance(capabilities, list):
        return [str(item) for item in capabilities if str(item).strip()]
    return _normalize_capabilities(None, model_id or "")


def get_model_max_tokens(model_id: str | None) -> int:
    entry = get_model_entry(model_id)
    max_tokens = entry.get("max_tokens") if entry else None
    normalized = _normalize_max_tokens(max_tokens)
    if normalized:
        return normalized
    return _DEFAULT_MAX_TOKENS


def model_supports_capability(model_id: str | None, capability: str) -> bool:
    if not capability:
        return False
    capability = capability.strip().lower()
    capabilities = {cap.lower() for cap in get_model_capabilities(model_id)}
    return capability in capabilities


def _normalize_capabilities(value: list[str] | None, model_id: str) -> list[str]:
    if isinstance(value, list) and value:
        normalized = [str(item).strip() for item in value if str(item).strip()]
        return normalized or list(_DEFAULT_CAPABILITIES)
    inferred = list(_DEFAULT_CAPABILITIES)
    lowered = (model_id or "").lower()
    if lowered and any(marker in lowered for marker in _VISION_MARKERS):
        inferred.append("vision")
    return inferred


def _normalize_max_tokens(value: int | None) -> int:
    if isinstance(value, int) and value > 0:
        return value
    try:
        as_int = int(value) if value is not None else 0
    except (TypeError, ValueError):
        return _DEFAULT_MAX_TOKENS
    return as_int if as_int > 0 else _DEFAULT_MAX_TOKENS


__all__ = [
    "MODEL_GROUPS",
    "get_model_catalog",
    "get_model_entry",
    "get_default_model_id",
    "get_default_base_url",
    "get_model_capabilities",
    "get_model_max_tokens",
    "model_supports_capability",
]
