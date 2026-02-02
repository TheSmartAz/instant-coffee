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

    # Phase 4: Sitemap events
    MULTIPAGE_DECISION_MADE = "multipage_decision_made"
    SITEMAP_PROPOSED = "sitemap_proposed"

    # Phase 4: Page events
    PAGE_CREATED = "page_created"
    PAGE_VERSION_CREATED = "page_version_created"
    PAGE_PREVIEW_READY = "page_preview_ready"

    # Phase 4: ProductDoc events
    PRODUCT_DOC_GENERATED = "product_doc_generated"
    PRODUCT_DOC_UPDATED = "product_doc_updated"
    PRODUCT_DOC_CONFIRMED = "product_doc_confirmed"
    PRODUCT_DOC_OUTDATED = "product_doc_outdated"

    # Phase 5: Interview events
    INTERVIEW_QUESTION = "interview_question"
    INTERVIEW_ANSWER = "interview_answer"

    # Phase 5: Versioning events
    VERSION_CREATED = "version_created"
    SNAPSHOT_CREATED = "snapshot_created"
    HISTORY_CREATED = "history_created"


STRUCTURED_EVENT_TYPES = {event_type.value for event_type in EventType}
STRUCTURED_EVENT_TYPES.update(
    {
        # Spec naming variants
        "agent_complete",
        "agent_error",
        "task_completed",
        "task_aborted",
    }
)

# Not persisted (streaming-only or internal)
EXCLUDED_EVENT_TYPES = {"delta", "thinking", "ping"}
