from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .style_reference import StyleTokens

class StyleReferenceInput(BaseModel):
    mode: Literal["full_mimic", "style_only"] = "full_mimic"
    images: List[str] = Field(default_factory=list)
    scope_pages: List[str] = Field(default_factory=list)
    tokens: Optional[StyleTokens] = None

    model_config = ConfigDict(extra="forbid")


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str = Field(min_length=1)
    interview: Optional[bool] = None
    generate_now: bool = False
    images: List[str] = Field(default_factory=list)
    target_pages: List[str] = Field(default_factory=list)
    style_reference: Optional[StyleReferenceInput] = None
    style_reference_mode: Optional[Literal["full_mimic", "style_only"]] = None
    resume: Optional[dict] = None

    @model_validator(mode="after")
    def validate_image_count(self) -> "ChatRequest":
        combined = list(self.images)
        if self.style_reference and self.style_reference.images:
            combined.extend(self.style_reference.images)
        if len(combined) > 3:
            raise ValueError("images must contain at most 3 items")
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": "123e4567-e89b-12d3-a456-426614174000",
                "message": "Create a mobile-friendly website for a coffee shop",
                "generate_now": False,
            }
        }
    )


class ChatResponse(BaseModel):
    session_id: str
    message: str

    preview_url: Optional[str] = None
    preview_html: Optional[str] = None
    active_page_slug: Optional[str] = None

    product_doc_updated: bool = False
    affected_pages: List[str] = Field(default_factory=list)

    action: str = "direct_reply"
    tokens_used: int = 0

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": "123e4567-e89b-12d3-a456-426614174000",
                "message": "Your product doc is ready. Please check the Product Doc tab.",
                "preview_url": None,
                "preview_html": None,
                "active_page_slug": None,
                "product_doc_updated": True,
                "affected_pages": [],
                "action": "product_doc_generated",
                "tokens_used": 1234,
            }
        }
    )


__all__ = ["ChatRequest", "ChatResponse", "StyleReferenceInput"]
