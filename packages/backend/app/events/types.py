from enum import Enum


class EventType(str, Enum):
    # Phase 1: Agent and Tool events
    AGENT_START = "agent_start"
    AGENT_PROGRESS = "agent_progress"
    AGENT_END = "agent_end"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    TOKEN_USAGE = "token_usage"
    ERROR = "error"
    DONE = "done"

    # Phase 2: Plan and Task events
    PLAN_CREATED = "plan_created"
    PLAN_UPDATED = "plan_updated"
    TASK_STARTED = "task_started"
    TASK_PROGRESS = "task_progress"
    TASK_DONE = "task_done"
    TASK_FAILED = "task_failed"
    TASK_RETRYING = "task_retrying"
    TASK_SKIPPED = "task_skipped"
    TASK_BLOCKED = "task_blocked"
