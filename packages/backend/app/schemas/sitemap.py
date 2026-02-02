from __future__ import annotations

import re
from typing import List, Optional

from pydantic import BaseModel, Field

try:  # Pydantic v2
    from pydantic import ConfigDict, field_validator, model_validator

    _PYDANTIC_V2 = True
except Exception:  # pragma: no cover - pydantic v1 compatibility
    from pydantic import root_validator, validator

    _PYDANTIC_V2 = False


_SLUG_PATTERN = re.compile(r"^[a-z0-9-]+$")
_HEX_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")


class SitemapPage(BaseModel):
    title: str
    slug: str = Field(..., max_length=40)
    purpose: str
    sections: List[str]
    required: bool = False

    if _PYDANTIC_V2:

        @field_validator("slug")
        @classmethod
        def _validate_slug(cls, value: str) -> str:
            if not _SLUG_PATTERN.fullmatch(value or ""):
                raise ValueError("slug must match pattern [a-z0-9-]+")
            return value

    else:  # pragma: no cover - pydantic v1 compatibility

        @validator("slug")
        def _validate_slug(cls, value: str) -> str:
            if not _SLUG_PATTERN.fullmatch(value or ""):
                raise ValueError("slug must match pattern [a-z0-9-]+")
            return value


class NavItem(BaseModel):
    slug: str
    label: str
    order: int


class GlobalStyle(BaseModel):
    primary_color: str
    secondary_color: Optional[str] = None
    font_family: str
    font_size_base: str = "16px"
    font_size_heading: str = "24px"
    button_height: str = "44px"
    spacing_unit: str = "8px"
    border_radius: str = "8px"

    if _PYDANTIC_V2:

        @field_validator("primary_color")
        @classmethod
        def _validate_primary_color(cls, value: str) -> str:
            if not _HEX_PATTERN.fullmatch(value or ""):
                raise ValueError("primary_color must be a 6-digit hex color")
            return value

        @field_validator("secondary_color")
        @classmethod
        def _validate_secondary_color(cls, value: Optional[str]) -> Optional[str]:
            if value is None:
                return value
            if not _HEX_PATTERN.fullmatch(value):
                raise ValueError("secondary_color must be a 6-digit hex color")
            return value

    else:  # pragma: no cover - pydantic v1 compatibility

        @validator("primary_color")
        def _validate_primary_color(cls, value: str) -> str:
            if not _HEX_PATTERN.fullmatch(value or ""):
                raise ValueError("primary_color must be a 6-digit hex color")
            return value

        @validator("secondary_color")
        def _validate_secondary_color(cls, value: Optional[str]) -> Optional[str]:
            if value is None:
                return value
            if not _HEX_PATTERN.fullmatch(value):
                raise ValueError("secondary_color must be a 6-digit hex color")
            return value


class SitemapResult(BaseModel):
    pages: List[SitemapPage]
    nav: List[NavItem]
    global_style: GlobalStyle

    if _PYDANTIC_V2:
        model_config = ConfigDict(extra="forbid")

        @model_validator(mode="after")
        def _validate_pages(self) -> "SitemapResult":
            if not (1 <= len(self.pages) <= 8):
                raise ValueError("pages must contain between 1 and 8 items")
            return self

    else:  # pragma: no cover - pydantic v1 compatibility

        class Config:
            extra = "forbid"

        @root_validator
        def _validate_pages(cls, values: dict) -> dict:
            pages = values.get("pages") or []
            if not (1 <= len(pages) <= 8):
                raise ValueError("pages must contain between 1 and 8 items")
            return values


__all__ = ["SitemapPage", "NavItem", "GlobalStyle", "SitemapResult"]
