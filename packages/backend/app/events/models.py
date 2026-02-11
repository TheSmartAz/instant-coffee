from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .types import EventType


class BaseEvent(BaseModel):
    model_config = ConfigDict(extra="allow")
    type: EventType
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    session_id: Optional[str] = None
    seq: Optional[int] = None
    source: Optional[str] = None
    run_id: Optional[str] = None
    event_id: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_event_envelope(self) -> "BaseEvent":
        if self.payload is None:
            self.payload = {}
        if not isinstance(self.payload, dict):
            raise ValueError("payload must be an object")

        return self

    def to_sse(self) -> str:
        """Convert event to SSE format."""
        import json

        data = self.model_dump()
        timestamp = data.get("timestamp")
        if isinstance(timestamp, datetime):
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            data["timestamp"] = (
                timestamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
            )
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


class WorkflowEvent(BaseEvent):
    payload: Dict[str, Any] = Field(default_factory=dict)


# Agent events
class AgentStartEvent(BaseEvent):
    type: EventType = EventType.AGENT_START
    task_id: Optional[str] = None
    agent_id: str
    agent_type: str  # Interview, Generation, Refinement, etc.
    agent_instance: Optional[int] = None


class AgentProgressEvent(BaseEvent):
    type: EventType = EventType.AGENT_PROGRESS
    task_id: Optional[str] = None
    agent_id: str
    message: str


class AgentEndEvent(BaseEvent):
    type: EventType = EventType.AGENT_END
    task_id: Optional[str] = None
    agent_id: str
    status: str  # success, failed
    summary: Optional[str] = None


# Tool events
class ToolCallEvent(BaseEvent):
    type: EventType = EventType.TOOL_CALL
    task_id: Optional[str] = None
    agent_id: str
    agent_type: str = "agent"
    tool_name: str
    tool_input: Optional[Dict[str, Any]] = None


class ToolResultEvent(BaseEvent):
    type: EventType = EventType.TOOL_RESULT
    task_id: Optional[str] = None
    agent_id: str
    agent_type: str = "agent"
    tool_name: str
    success: bool
    tool_output: Optional[Any] = None
    error: Optional[str] = None


class ToolProgressEvent(BaseEvent):
    """Progress update during tool execution."""
    type: EventType = EventType.TOOL_PROGRESS
    task_id: Optional[str] = None
    agent_id: str
    agent_type: str = "agent"
    tool_name: str
    progress_message: str
    progress_percent: Optional[int] = None  # 0-100, or None for indeterminate


class TokenUsageEvent(BaseEvent):
    type: EventType = EventType.TOKEN_USAGE
    task_id: Optional[str] = None
    agent_type: Optional[str] = None
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float


class CostUpdateEvent(BaseEvent):
    """Real-time cost tracking update from the engine."""
    type: EventType = EventType.COST_UPDATE
    prompt_tokens: int
    completion_tokens: int
    total_cost_usd: float


class ShellApprovalEvent(BaseEvent):
    """Emitted when a shell command needs user approval before execution."""
    type: EventType = EventType.SHELL_APPROVAL
    command: str
    reason: str  # Why the command was flagged
    approval_id: str  # Unique ID for the approval request


class PageCreatedEvent(BaseEvent):
    type: EventType = EventType.PAGE_CREATED
    page_id: str
    slug: str
    title: str


class PageVersionCreatedEvent(BaseEvent):
    type: EventType = EventType.PAGE_VERSION_CREATED
    page_id: str
    slug: str
    version: int


class PagePreviewReadyEvent(BaseEvent):
    type: EventType = EventType.PAGE_PREVIEW_READY
    page_id: str
    slug: str
    preview_url: Optional[str] = None


# Interview events
class InterviewQuestionEvent(BaseEvent):
    type: EventType = EventType.INTERVIEW_QUESTION
    batch_id: Optional[str] = None
    message: Optional[str] = None
    questions: Optional[List[Dict[str, Any]]] = None


class InterviewAnswerEvent(BaseEvent):
    type: EventType = EventType.INTERVIEW_ANSWER
    batch_id: Optional[str] = None
    action: Optional[str] = None
    answers: Optional[List[Dict[str, Any]]] = None


# Versioning events
class VersionCreatedEvent(BaseEvent):
    type: EventType = EventType.VERSION_CREATED
    version_id: Optional[str] = None
    version: Optional[int] = None
    description: Optional[str] = None


class SnapshotCreatedEvent(BaseEvent):
    type: EventType = EventType.SNAPSHOT_CREATED
    snapshot_id: str
    snapshot_number: int
    source: Optional[str] = None
    label: Optional[str] = None


class HistoryCreatedEvent(BaseEvent):
    type: EventType = EventType.HISTORY_CREATED
    history_id: int
    version: int
    source: Optional[str] = None
    change_summary: Optional[str] = None


# ProductDoc events
class ProductDocGeneratedEvent(BaseEvent):
    type: EventType = EventType.PRODUCT_DOC_GENERATED
    doc_id: str
    status: str


class ProductDocUpdatedEvent(BaseEvent):
    type: EventType = EventType.PRODUCT_DOC_UPDATED
    doc_id: str
    change_summary: Optional[str] = None


class ProductDocConfirmedEvent(BaseEvent):
    type: EventType = EventType.PRODUCT_DOC_CONFIRMED
    doc_id: str


class ProductDocOutdatedEvent(BaseEvent):
    type: EventType = EventType.PRODUCT_DOC_OUTDATED
    doc_id: str


class MultiPageDecisionEvent(BaseEvent):
    type: EventType = EventType.MULTIPAGE_DECISION_MADE
    decision: str
    confidence: float
    reasons: List[str] = Field(default_factory=list)
    suggested_pages: Optional[List[Dict[str, Any]]] = None
    risk: Optional[str] = None


class SitemapProposedEvent(BaseEvent):
    type: EventType = EventType.SITEMAP_PROPOSED
    pages_count: int
    sitemap: Optional[Dict[str, Any]] = None


class ErrorEvent(BaseEvent):
    type: EventType = EventType.ERROR
    message: str
    details: Optional[str] = None


class DoneEvent(BaseEvent):
    type: EventType = EventType.DONE
    summary: Optional[str] = None
    token_usage: Optional[Dict[str, Any]] = None


class TextDeltaEvent(BaseEvent):
    """Lightweight streaming text delta — serialises without ``type`` so the
    frontend treats it as a raw delta chunk rather than a structured event."""

    type: EventType = EventType.DELTA
    delta: str

    def to_sse(self) -> str:
        import json

        return f"data: {json.dumps({'delta': self.delta}, ensure_ascii=False)}\n\n"


# ── Phase 9: Agent improvement events ──────────────────────────


class FilesChangedEvent(BaseEvent):
    """Emitted after a turn when files were created/modified/deleted."""

    type: EventType = EventType.FILES_CHANGED
    files: List[Dict[str, Any]] = Field(default_factory=list)


class ContextCompactedEvent(BaseEvent):
    """Emitted when context is compacted to save tokens."""

    type: EventType = EventType.CONTEXT_COMPACTED
    tokens_saved: int = 0
    turns_removed: int = 0
    warning: Optional[str] = None


class PlanUpdateEvent(BaseEvent):
    """Emitted when the agent creates or updates a plan."""

    type: EventType = EventType.PLAN_UPDATE
    explanation: str = ""
    steps: List[Dict[str, Any]] = Field(default_factory=list)


class AgentSpawnedEvent(BaseEvent):
    """Emitted when a sub-agent is spawned for a task."""

    type: EventType = EventType.AGENT_SPAWNED
    agent_id: str
    task_description: str = ""


class BgTaskStartedEvent(BaseEvent):
    """Emitted when a background shell task starts."""

    type: EventType = EventType.BG_TASK_STARTED
    task_id: Optional[str] = None
    command: str = ""


class BgTaskCompletedEvent(BaseEvent):
    """Emitted when a background shell task completes."""

    type: EventType = EventType.BG_TASK_COMPLETED
    task_id: Optional[str] = None
    output: Optional[str] = None
    exit_code: Optional[int] = None


class BgTaskFailedEvent(BaseEvent):
    """Emitted when a background shell task fails."""

    type: EventType = EventType.BG_TASK_FAILED
    task_id: Optional[str] = None
    error: str = ""


def _clean_payload(payload: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not payload:
        return {}
    return {key: value for key, value in payload.items() if value is not None}


def workflow_event(event_type: EventType, payload: Optional[Dict[str, Any]] = None) -> WorkflowEvent:
    return WorkflowEvent(type=event_type, payload=_clean_payload(payload))


def brief_start_event() -> WorkflowEvent:
    return workflow_event(EventType.BRIEF_START)


def brief_complete_event() -> WorkflowEvent:
    return workflow_event(EventType.BRIEF_COMPLETE)


def style_extracted_event(payload: Optional[Dict[str, Any]] = None) -> WorkflowEvent:
    return workflow_event(EventType.STYLE_EXTRACTED, payload)


def registry_start_event() -> WorkflowEvent:
    return workflow_event(EventType.REGISTRY_START)


def registry_complete_event(payload: Optional[Dict[str, Any]] = None) -> WorkflowEvent:
    return workflow_event(EventType.REGISTRY_COMPLETE, payload)


def generate_start_event(payload: Optional[Dict[str, Any]] = None) -> WorkflowEvent:
    return workflow_event(EventType.GENERATE_START, payload)


def generate_progress_event(
    *,
    step: Optional[str] = None,
    percent: Optional[int] = None,
    message: Optional[str] = None,
    page: Optional[str] = None,
) -> WorkflowEvent:
    return workflow_event(
        EventType.GENERATE_PROGRESS,
        {"step": step, "percent": percent, "message": message, "page": page},
    )


def generate_complete_event(payload: Optional[Dict[str, Any]] = None) -> WorkflowEvent:
    return workflow_event(EventType.GENERATE_COMPLETE, payload)


def refine_start_event(payload: Optional[Dict[str, Any]] = None) -> WorkflowEvent:
    return workflow_event(EventType.REFINE_START, payload)


def refine_complete_event(payload: Optional[Dict[str, Any]] = None) -> WorkflowEvent:
    return workflow_event(EventType.REFINE_COMPLETE, payload)


def refine_waiting_event(payload: Optional[Dict[str, Any]] = None) -> WorkflowEvent:
    return workflow_event(EventType.REFINE_WAITING, payload)


def build_start_event(payload: Optional[Dict[str, Any]] = None) -> WorkflowEvent:
    return workflow_event(EventType.BUILD_START, payload)


def build_progress_event(
    *,
    step: Optional[str] = None,
    percent: Optional[int] = None,
    message: Optional[str] = None,
    page: Optional[str] = None,
) -> WorkflowEvent:
    return workflow_event(
        EventType.BUILD_PROGRESS,
        {"step": step, "percent": percent, "message": message, "page": page},
    )


def build_complete_event(payload: Optional[Dict[str, Any]] = None) -> WorkflowEvent:
    return workflow_event(EventType.BUILD_COMPLETE, payload)


def build_failed_event(
    *,
    error: str,
    retry_count: Optional[int] = None,
) -> WorkflowEvent:
    return workflow_event(
        EventType.BUILD_FAILED,
        {"error": error, "retry_count": retry_count},
    )


def interrupt_event(payload: Optional[Dict[str, Any]] = None) -> WorkflowEvent:
    return workflow_event(EventType.INTERRUPT, payload)
