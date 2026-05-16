from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


def _normalize_execution_mode(value: Any = None) -> str:
    mode = str(value or "agent")
    if mode == "yolo":
        return "auto"
    return mode if mode in {"plan", "agent", "auto"} else "agent"


class StyleReferenceInput(BaseModel):
    mode: Literal["full_mimic", "style_only"] = "full_mimic"
    images: List[str] = Field(default_factory=list)
    scope_pages: List[str] = Field(default_factory=list)
    tokens: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(extra="forbid")


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    thread_id: Optional[str] = None
    message: str = Field(min_length=1)
    interview: Optional[bool] = None
    generate_now: bool = False
    images: List[str] = Field(default_factory=list)
    image_intent: Optional[Literal["asset", "style_reference", "layout_reference", "screenshot"]] = None
    target_pages: List[str] = Field(default_factory=list)
    style_reference: Optional[StyleReferenceInput] = None
    style_reference_mode: Optional[Literal["full_mimic", "style_only"]] = None
    execution_mode: str = Field(default="agent", pattern="^(plan|agent|auto)$")
    approval_mode: str = Field(default="agent", pattern="^(plan|agent|auto)$")
    resume: Optional[dict] = None
    mentioned_files: List[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def accept_legacy_approval_mode(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        payload = dict(data)
        raw_mode = payload.get("execution_mode", payload.get("approval_mode", "agent"))
        mode = _normalize_execution_mode(raw_mode)
        payload["execution_mode"] = mode
        payload["approval_mode"] = mode
        return payload

    @model_validator(mode="after")
    def validate_image_count(self) -> "ChatRequest":
        combined = list(self.images)
        if self.style_reference and self.style_reference.images:
            combined.extend(self.style_reference.images)
        if len(combined) > 3:
            raise ValueError("images must contain at most 3 items")
        self.execution_mode = _normalize_execution_mode(self.execution_mode)
        self.approval_mode = self.execution_mode
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
                "active_page_slug": None,
                "product_doc_updated": True,
                "affected_pages": [],
                "action": "product_doc_generated",
                "tokens_used": 1234,
            }
        }
    )


__all__ = ["ChatRequest", "ChatResponse", "StyleReferenceInput"]
