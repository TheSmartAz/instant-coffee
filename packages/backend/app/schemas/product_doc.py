from __future__ import annotations

import re
from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProductDocFeature(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    priority: Literal["must", "should", "nice"]


class DesignDirection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    style: Optional[str] = None
    color_preference: Optional[str] = None
    tone: Optional[str] = None
    reference_sites: List[str] = Field(default_factory=list)


class ProductDocPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    slug: str
    purpose: str
    sections: List[str] = Field(default_factory=list)
    required: bool = False

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, value: str) -> str:
        if value is None:
            raise ValueError("slug is required")
        if len(value) > 40:
            raise ValueError("slug must be 40 characters or fewer")
        if re.fullmatch(r"[a-z0-9-]+", value) is None:
            raise ValueError("slug must match pattern [a-z0-9-]+")
        return value


class ProductDocStructured(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_name: Optional[str] = None
    description: Optional[str] = None
    target_audience: Optional[str] = None
    goals: List[str] = Field(default_factory=list)
    features: List[ProductDocFeature] = Field(default_factory=list)
    design_direction: Optional[DesignDirection] = None
    pages: List[ProductDocPage] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)


class ProductDocResponse(BaseModel):
    id: str
    session_id: str
    content: str
    structured: dict
    status: str
    created_at: datetime
    updated_at: datetime


class ProductDocHistoryListItem(BaseModel):
    id: int
    product_doc_id: str
    version: int
    change_summary: str
    source: str
    is_pinned: bool
    is_released: bool
    created_at: datetime
    available: bool


class ProductDocHistoryListResponse(BaseModel):
    history: List[ProductDocHistoryListItem]
    total: int
    pinned_count: int


class ProductDocHistoryResponse(ProductDocHistoryListItem):
    content: str
    structured: dict


class ProductDocHistoryPinResponse(BaseModel):
    message: Optional[str] = None
    history: Optional[ProductDocHistoryListItem] = None
    current_pinned: Optional[List[int]] = None


__all__ = [
    "DesignDirection",
    "ProductDocFeature",
    "ProductDocPage",
    "ProductDocResponse",
    "ProductDocHistoryListItem",
    "ProductDocHistoryListResponse",
    "ProductDocHistoryResponse",
    "ProductDocHistoryPinResponse",
    "ProductDocStructured",
]
