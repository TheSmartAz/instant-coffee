from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str = Field(min_length=1)
    interview: Optional[bool] = None
    generate_now: bool = False

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


__all__ = ["ChatRequest", "ChatResponse"]
