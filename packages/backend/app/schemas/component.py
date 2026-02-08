from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from .style_tokens import StyleTokens


ComponentPropType = Literal["string", "number", "boolean", "asset", "binding"]
DesignRadius = Literal["none", "small", "medium", "large"]
DesignSpacing = Literal["compact", "normal", "airy"]
DesignShadow = Literal["none", "subtle", "medium", "strong"]


class PropDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    type: ComponentPropType
    required: bool = False
    default: Optional[Any] = None


class ComponentDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: str
    slots: list[str] = Field(default_factory=list)
    props: list[PropDefinition] = Field(default_factory=list)
    variants: Optional[list[str]] = None


class DesignTokens(BaseModel):
    model_config = ConfigDict(extra="forbid")

    radius: DesignRadius
    spacing: DesignSpacing
    shadow: DesignShadow


class ComponentRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    components: list[ComponentDefinition] = Field(default_factory=list)
    tokens: DesignTokens


def normalize_design_tokens(style_tokens: Any) -> DesignTokens:
    if isinstance(style_tokens, StyleTokens):
        payload = style_tokens.model_dump()
    elif isinstance(style_tokens, dict):
        payload = style_tokens
    else:
        payload = {}

    def pick(value: Any, *, allowed: set[str], fallback: str, alias: dict[str, str] | None = None) -> str:
        if value is None:
            return fallback
        normalized = str(value).strip().lower()
        if alias and normalized in alias:
            normalized = alias[normalized]
        return normalized if normalized in allowed else fallback

    radius = pick(
        payload.get("radius"),
        allowed={"none", "small", "medium", "large"},
        fallback="medium",
        alias={"full": "large"},
    )
    spacing = pick(
        payload.get("spacing"),
        allowed={"compact", "normal", "airy"},
        fallback="normal",
    )
    shadow = pick(
        payload.get("shadow"),
        allowed={"none", "subtle", "medium", "strong"},
        fallback="subtle",
    )
    return DesignTokens(radius=radius, spacing=spacing, shadow=shadow)


__all__ = [
    "ComponentRegistry",
    "ComponentDefinition",
    "PropDefinition",
    "DesignTokens",
    "ComponentPropType",
    "DesignRadius",
    "DesignSpacing",
    "DesignShadow",
    "normalize_design_tokens",
]
