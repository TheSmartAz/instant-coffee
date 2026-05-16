from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator

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


def normalize_execution_mode(value: Any = None) -> str:
    mode = str(value or "agent")
    if mode == "yolo":
        return "auto"
    return mode if mode in {"plan", "agent", "auto"} else "agent"


class RunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    message: str = Field(min_length=1)
    generate_now: bool = False
    execution_mode: str = Field(default="agent", pattern="^(plan|agent|auto)$")
    approval_mode: str = Field(default="agent", pattern="^(plan|agent|auto)$")
    style_reference: Optional[StyleReferenceInput] = None
    target_pages: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def accept_legacy_approval_mode(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        payload = dict(data)
        raw_mode = payload.get("execution_mode", payload.get("approval_mode", "agent"))
        mode = normalize_execution_mode(raw_mode)
        payload["execution_mode"] = mode
        payload["approval_mode"] = mode
        return payload

    @model_validator(mode="after")
    def mirror_legacy_approval_mode(self) -> "RunCreate":
        self.execution_mode = normalize_execution_mode(self.execution_mode)
        self.approval_mode = self.execution_mode
        return self


class VerificationCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    status: str
    passed: Optional[bool] = None
    details: dict[str, Any] = Field(default_factory=dict)


class VerificationCommandResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    command: str
    scope: str = "repo"
    status: str
    exit_code: Optional[int] = None
    duration_ms: int = 0
    output_summary: str = ""
    failures: list[dict[str, Any]] = Field(default_factory=list)


class VerificationRunResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    passed: bool
    commands: list[VerificationCommandResult] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class VerificationChangeSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = "captured"
    changed_files: list[str] = Field(default_factory=list)
    file_count: int = 0
    risk_level: str = "low"
    risk_flags: list[str] = Field(default_factory=list)
    verification_status: Optional[str] = None
    captured_at: Optional[str] = None


class VerificationFixAttempt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attempt: int
    status: str
    prompt: str
    failures: list[dict[str, Any]] = Field(default_factory=list)
    engine: Optional[dict[str, Any]] = None
    verification: Optional[VerificationRunResult] = None
    change_summary: Optional[VerificationChangeSummary] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class VerificationAuditEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    status: str
    message: str = ""
    attempt: Optional[int] = None
    command_count: Optional[int] = None
    failure_count: Optional[int] = None
    risk_flags: list[str] = Field(default_factory=list)
    at: Optional[str] = None


class RunActionAuditEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    category: str
    status: str
    summary: str = ""
    attempt: Optional[int] = None
    command: Optional[str] = None
    scope: Optional[str] = None
    exit_code: Optional[int] = None
    duration_ms: Optional[int] = None
    file_count: Optional[int] = None
    risk_level: Optional[str] = None
    risk_flags: list[str] = Field(default_factory=list)
    at: Optional[str] = None


class RunVerification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = "unknown"
    passed: Optional[bool] = None
    checks: list[VerificationCheck] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
    profile: dict[str, Any] = Field(default_factory=dict)
    last_run: Optional[VerificationRunResult] = None
    fix_attempts: list[VerificationFixAttempt] = Field(default_factory=list)
    audit_trail: list[VerificationAuditEvent] = Field(default_factory=list)
    action_audit_trail: list[RunActionAuditEvent] = Field(default_factory=list)


class RunContextEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    memory_keys: list[str] = Field(default_factory=list)
    memory: dict[str, str] = Field(default_factory=dict)


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
    execution_mode: str = "agent"
    approval_mode: str = "agent"
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
    verification: RunVerification = Field(default_factory=RunVerification)
    context: RunContextEvidence = Field(default_factory=RunContextEvidence)
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


class RunApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approved: bool


__all__ = [
    "RunApprovalRequest",
    "RunCreate",
    "RunListResponse",
    "RunPhase",
    "RunResponse",
    "RunResumeRequest",
    "RunStatus",
    "normalize_execution_mode",
    "RunContextEvidence",
    "RunVerification",
    "RunActionAuditEvent",
    "VerificationFixAttempt",
    "VerificationChangeSummary",
    "VerificationAuditEvent",
    "VerificationCommandResult",
    "VerificationRunResult",
    "VerificationCheck",
]
