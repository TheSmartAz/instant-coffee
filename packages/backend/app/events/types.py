from enum import Enum


class EventType(str, Enum):
    # Phase 1: Agent and Tool events
    AGENT_START = "agent_start"
    AGENT_PROGRESS = "agent_progress"
    AGENT_END = "agent_end"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    TOOL_PROGRESS = "tool_progress"  # Added for tool execution progress
    TOKEN_USAGE = "token_usage"
    COST_UPDATE = "cost_update"
    SHELL_APPROVAL = "shell_approval"
    DELTA = "delta"
    ERROR = "error"
    DONE = "done"

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

    # Phase 7: Workflow events (LangGraph + build)
    BRIEF_START = "brief_start"
    BRIEF_COMPLETE = "brief_complete"
    STYLE_EXTRACTED = "style_extracted"
    REGISTRY_START = "registry_start"
    REGISTRY_COMPLETE = "registry_complete"
    GENERATE_START = "generate_start"
    GENERATE_PROGRESS = "generate_progress"
    GENERATE_COMPLETE = "generate_complete"
    REFINE_START = "refine_start"
    REFINE_COMPLETE = "refine_complete"
    REFINE_WAITING = "refine_waiting"
    BUILD_START = "build_start"
    BUILD_PROGRESS = "build_progress"
    BUILD_COMPLETE = "build_complete"
    BUILD_FAILED = "build_failed"
    INTERRUPT = "interrupt"

    # Phase 8: Run lifecycle events
    RUN_CREATED = "run_created"
    RUN_STARTED = "run_started"
    RUN_WAITING_INPUT = "run_waiting_input"
    RUN_RESUMED = "run_resumed"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"
    RUN_CANCELLED = "run_cancelled"

    # Phase 8: Verify events
    VERIFY_START = "verify_start"
    VERIFY_PASS = "verify_pass"
    VERIFY_FAIL = "verify_fail"

    # Phase 8: Tool policy events
    TOOL_POLICY_BLOCKED = "tool_policy_blocked"
    TOOL_POLICY_WARN = "tool_policy_warn"

    # Phase 9: Agent improvements
    FILES_CHANGED = "files_changed"
    CONTEXT_COMPACTED = "context_compacted"
    PLAN_UPDATE = "plan_update"
    PLAN_CREATED = "plan_created"
    AGENT_SPAWNED = "agent_spawned"
    BG_TASK_STARTED = "bg_task_started"
    BG_TASK_COMPLETED = "bg_task_completed"
    BG_TASK_FAILED = "bg_task_failed"


STRUCTURED_EVENT_TYPES = {event_type.value for event_type in EventType}
STRUCTURED_EVENT_TYPES.update(
    {
        # Spec naming variants
        "agent_complete",
        "agent_error",
    }
)

# Not persisted (streaming-only or internal)
EXCLUDED_EVENT_TYPES = {"delta", "thinking", "ping"}


RUN_SCOPED_EVENT_TYPES = {
    EventType.RUN_CREATED.value,
    EventType.RUN_STARTED.value,
    EventType.RUN_WAITING_INPUT.value,
    EventType.RUN_RESUMED.value,
    EventType.RUN_COMPLETED.value,
    EventType.RUN_FAILED.value,
    EventType.RUN_CANCELLED.value,
    EventType.VERIFY_START.value,
    EventType.VERIFY_PASS.value,
    EventType.VERIFY_FAIL.value,
    EventType.TOOL_POLICY_BLOCKED.value,
    EventType.TOOL_POLICY_WARN.value,
}
