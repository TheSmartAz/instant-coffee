from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class RoutingMetadata(BaseModel):
    product_type: Optional[str] = None
    complexity: Optional[str] = None
    skill_id: Optional[str] = None
    doc_tier: Optional[str] = None
    style_reference_mode: Optional[str] = None


class ModelUsage(BaseModel):
    classifier: Optional[str] = None
    writer: Optional[str] = None
    expander: Optional[str] = None
    validator: Optional[str] = None
    style_refiner: Optional[str] = None


class BuildStatus(str, enum.Enum):
    PENDING = "pending"
    BUILDING = "building"
    SUCCESS = "success"
    FAILED = "failed"


class BuildInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: BuildStatus = BuildStatus.PENDING
    pages: List[str] = Field(default_factory=list)
    dist_path: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class SessionMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    graph_state: Optional[Dict[str, Any]] = None
    build_status: BuildStatus = BuildStatus.PENDING
    build_artifacts: Optional[Dict[str, Any]] = None
    aesthetic_scores: Optional[Dict[str, Any]] = None
    updated_at: Optional[datetime] = None


class SessionMetadataUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    graph_state: Optional[Dict[str, Any]] = None
    build_status: Optional[BuildStatus] = None
    build_artifacts: Optional[Dict[str, Any]] = None
    aesthetic_scores: Optional[Dict[str, Any]] = None


__all__ = [
    "RoutingMetadata",
    "ModelUsage",
    "BuildStatus",
    "BuildInfo",
    "SessionMetadata",
    "SessionMetadataUpdate",
]
