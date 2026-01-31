from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from .types import EventType


class BaseEvent(BaseModel):
    model_config = ConfigDict(extra="allow")
    type: EventType
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    session_id: Optional[str] = None

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


class ErrorEvent(BaseEvent):
    type: EventType = EventType.ERROR
    message: str
    details: Optional[str] = None


class DoneEvent(BaseEvent):
    type: EventType = EventType.DONE
    summary: Optional[str] = None
    token_usage: Optional[Dict[str, Any]] = None
