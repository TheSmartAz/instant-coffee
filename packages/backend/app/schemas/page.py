from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class PageCreate(BaseModel):
    title: str
    slug: str
    description: str = ""
    order_index: int = 0


class PageResponse(BaseModel):
    id: str
    session_id: str
    title: str
    slug: str
    description: str
    order_index: int
    current_version_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class PageVersionResponse(BaseModel):
    id: int
    page_id: str
    version: int
    description: Optional[str] = None
    source: Optional[str] = None
    is_pinned: bool = False
    is_released: bool = False
    created_at: datetime
    available: bool = True
    fallback_used: bool = False
    previewable: bool = True


class PagePreviewResponse(BaseModel):
    page_id: str
    slug: str
    html: str
    version: int


class RollbackRequest(BaseModel):
    version_id: int


class RollbackResponse(BaseModel):
    page_id: str
    rolled_back_to_version: int
    new_current_version_id: int


__all__ = [
    "PageCreate",
    "PageResponse",
    "PageVersionResponse",
    "PagePreviewResponse",
    "RollbackRequest",
    "RollbackResponse",
]
