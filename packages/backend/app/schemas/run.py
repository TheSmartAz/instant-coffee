from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from .chat import StyleReferenceInput


class RunStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_INPUT = "waiting_input"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RunPhase(str, enum.Enum):
    PLAN = "plan"
    IMPLEMENT = "implement"
    BUILD = "build"
    REVIEW = "review"
    FIX = "fix"
    VERIFY = "verify"
    DONE = "done"


class RunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    message: str = Field(min_length=1)
    generate_now: bool = False
    style_reference: Optional[StyleReferenceInput] = None
    target_pages: list[str] = Field(default_factory=list)


class RunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    session_id: str
    status: RunStatus
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    latest_error: Optional[dict[str, Any]] = None
    metrics: Optional[dict[str, Any]] = None
    checkpoint_thread: Optional[str] = None
    checkpoint_ns: Optional[str] = None
    waiting_reason: Optional[str] = None
    current_phase: Optional[str] = None
    phase_status: Optional[str] = None
    phase_metadata: dict[str, Any] = Field(default_factory=dict)
    phase_history: list[dict[str, Any]] = Field(default_factory=list)
    artifacts: dict[str, Any] = Field(default_factory=dict)
    fix_attempts: int = 0
    last_review: Optional[dict[str, Any]] = None
    review_summary: Optional[dict[str, Any]] = None
    review_issues: list[dict[str, Any]] = Field(default_factory=list)
    heartbeat_at: Optional[str] = None


class RunListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runs: list[RunResponse]
    total: int


class RunResumeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resume_payload: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias=AliasChoices("resume_payload", "resume"),
        serialization_alias="resume_payload",
    )


__all__ = [
    "RunCreate",
    "RunListResponse",
    "RunPhase",
    "RunResponse",
    "RunResumeRequest",
    "RunStatus",
]
