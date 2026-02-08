from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StyleScope(BaseModel):
    type: Literal["model_decide", "specific_pages"] = "model_decide"
    pages: List[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _normalize_pages(self) -> "StyleScope":
        cleaned = [str(page).strip() for page in self.pages if str(page).strip()]
        if self.type == "model_decide":
            cleaned = []
        self.pages = cleaned
        return self


class StyleImage(BaseModel):
    id: Optional[str] = None
    source: Literal["upload", "url"]
    page_hint: Optional[str] = None
    url: Optional[str] = None
    base64_data: Optional[str] = None
    content_type: Optional[str] = None

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _validate_payload(self) -> "StyleImage":
        if self.source == "url" and not self.url:
            raise ValueError("url is required when source=url")
        if self.source == "upload" and not (self.base64_data or self.id or self.url):
            raise ValueError("upload images require base64_data, id, or url")
        return self


class StyleTokens(BaseModel):
    colors: Dict[str, Any]
    typography: Dict[str, Any]
    radius: Literal["sharp", "small", "medium", "large", "pill"]
    shadow: Literal["none", "soft", "medium", "strong"]
    spacing: Literal["tight", "medium", "airy"]
    layout_patterns: List[dict | str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class StyleReference(BaseModel):
    mode: Literal["full_mimic", "style_only"] = "full_mimic"
    scope: StyleScope = Field(default_factory=StyleScope)
    images: List[StyleImage] = Field(default_factory=list)
    tokens: Optional[StyleTokens] = None

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _validate_images(self) -> "StyleReference":
        if len(self.images) > 3:
            raise ValueError("images must contain at most 3 items")
        return self


__all__ = ["StyleReference", "StyleImage", "StyleScope", "StyleTokens"]
