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
    progress: Optional[int] = None  # 0-100


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


class TokenUsageEvent(BaseEvent):
    type: EventType = EventType.TOKEN_USAGE
    task_id: Optional[str] = None
    agent_type: Optional[str] = None
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float


# Plan events
class PlanCreatedEvent(BaseEvent):
    type: EventType = EventType.PLAN_CREATED
    plan: Dict[str, Any]


class PlanUpdatedEvent(BaseEvent):
    type: EventType = EventType.PLAN_UPDATED
    plan_id: str
    changes: List[Dict[str, Any]]


# Task events
class TaskStartedEvent(BaseEvent):
    type: EventType = EventType.TASK_STARTED
    task_id: str
    task_title: str


class TaskProgressEvent(BaseEvent):
    type: EventType = EventType.TASK_PROGRESS
    task_id: str
    progress: int
    message: Optional[str] = None


class TaskDoneEvent(BaseEvent):
    type: EventType = EventType.TASK_DONE
    task_id: str
    result: Optional[Dict[str, Any]] = None


class TaskFailedEvent(BaseEvent):
    type: EventType = EventType.TASK_FAILED
    task_id: str
    error_type: str  # temporary, logic, dependency
    error_message: str
    retry_count: int
    max_retries: int
    available_actions: List[str]
    blocked_tasks: List[str]


class TaskRetryingEvent(BaseEvent):
    type: EventType = EventType.TASK_RETRYING
    task_id: str
    attempt: int
    max_attempts: int
    next_retry_in: int


class TaskSkippedEvent(BaseEvent):
    type: EventType = EventType.TASK_SKIPPED
    task_id: str
    reason: Optional[str] = None


class TaskBlockedEvent(BaseEvent):
    type: EventType = EventType.TASK_BLOCKED
    task_id: str
    blocked_by: List[str] = Field(default_factory=list)
    reason: Optional[str] = None


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


class AestheticScoreEvent(BaseEvent):
    type: EventType = EventType.AESTHETIC_SCORE
    page_id: str
    slug: Optional[str] = None
    score: Dict[str, Any]
    attempts: Optional[List[Dict[str, Any]]] = None


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
