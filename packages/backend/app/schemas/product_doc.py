from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

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


class PageInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str
    role: str = "general"  # catalog, checkout, profile, landing, etc.
    title: Optional[str] = None
    # Legacy fields for compatibility with existing ProductDoc usage.
    purpose: Optional[str] = None
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


class ProductDocPage(PageInfo):
    pass


class DataFlow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_page: str
    event: str
    to_page: str


class StateContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shared_state_key: str = "instant-coffee:state"
    records_key: str = "instant-coffee:records"
    events_key: str = "instant-coffee:events"
    schema: Dict[str, Any] = Field(default_factory=dict)
    events: List[str] = Field(default_factory=list)


class StyleReferenceInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: str = "full_mimic"  # full_mimic, style_only
    scope: Dict[str, Any] = Field(default_factory=dict)
    images: List[str] = Field(default_factory=list)


class ProductDocStructured(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_type: str = "unknown"  # ecommerce, booking, dashboard, landing, card, invitation
    complexity: str = "unknown"  # simple, medium, complex
    doc_tier: str = "standard"  # checklist, standard, extended
    goal: str = ""
    pages: List[PageInfo] = Field(default_factory=list)
    data_flow: List[DataFlow] = Field(default_factory=list)
    state_contract: Optional[StateContract] = None
    style_reference: Optional[StyleReferenceInfo] = None
    component_inventory: List[str] = Field(default_factory=list)

    core_points: List[str] = Field(default_factory=list)
    users: List[str] = Field(default_factory=list)
    user_stories: List[str] = Field(default_factory=list)
    components: List[str] = Field(default_factory=list)
    data_flow_explanation: Optional[str] = None
    detailed_specs: List[str] = Field(default_factory=list)
    appendices: List[str] = Field(default_factory=list)
    mermaid_page_flow: Optional[str] = None
    mermaid_data_flow: Optional[str] = None

    project_name: Optional[str] = None
    description: Optional[str] = None
    target_audience: Optional[str] = None
    goals: List[str] = Field(default_factory=list)
    features: List[ProductDocFeature] = Field(default_factory=list)
    design_direction: Optional[DesignDirection] = None
    constraints: List[str] = Field(default_factory=list)


class ProductDocChecklist(ProductDocStructured):
    """Minimal output for simple products."""

    core_points: List[str] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)


class ProductDocStandard(ProductDocStructured):
    """Standard output for medium complexity."""

    users: List[str] = Field(default_factory=list)
    user_stories: List[str] = Field(default_factory=list)
    components: List[str] = Field(default_factory=list)
    data_flow_explanation: Optional[str] = None


class ProductDocExtended(ProductDocStandard):
    """Extended output for complex products."""

    mermaid_page_flow: Optional[str] = None
    mermaid_data_flow: Optional[str] = None
    detailed_specs: List[str] = Field(default_factory=list)
    appendices: List[str] = Field(default_factory=list)


class ProductDocResponse(BaseModel):
    id: str
    session_id: str
    content: str
    structured: dict
    version: int
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
    "DataFlow",
    "DesignDirection",
    "PageInfo",
    "ProductDocFeature",
    "ProductDocPage",
    "ProductDocResponse",
    "ProductDocHistoryListItem",
    "ProductDocHistoryListResponse",
    "ProductDocHistoryResponse",
    "ProductDocHistoryPinResponse",
    "ProductDocChecklist",
    "ProductDocStandard",
    "ProductDocExtended",
    "ProductDocStructured",
    "StateContract",
    "StyleReferenceInfo",
]
