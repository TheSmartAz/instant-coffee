# Phase B3: BaseAgent Enhancement

## Metadata

- **Category**: Backend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: Medium
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: B1 (LLM Client), B2 (Tools System)
  - **Blocks**: B5-B7 (Agent Implementations)

## Goal

Enhance the BaseAgent class with unified LLM calling methods, event emission, and tool calling support that all concrete agents will inherit.

## Detailed Tasks

### Task 1: Add LLM Client Initialization

**Description**: Initialize OpenAIClient in BaseAgent.__init__.

**Implementation Details**:
- [ ] Modify `packages/backend/app/agents/base.py`
- [ ] Import OpenAIClient and TokenTrackerService
- [ ] Initialize `self._llm_client` in __init__
- [ ] Pass settings and token_tracker to client

**Files to modify**:
- `packages/backend/app/agents/base.py`

**Acceptance Criteria**:
- [ ] LLM client is initialized when Agent is created
- [ ] Settings are properly passed through
- [ ] Token tracker is configured if provided

### Task 2: Implement _call_llm()

**Description**: Create unified LLM calling method with event emission.

**Implementation Details**:
- [ ] Implement `_call_llm()` async method
- [ ] Support model, temperature, max_tokens, tools parameters
- [ ] Support stream mode for real-time output
- [ ] Emit agent_start event before calling
- [ ] Emit agent_progress events during streaming
- [ ] Record token usage with TokenTrackerService
- [ ] Emit agent_end event after completion
- [ ] Handle errors and emit failed events

**Acceptance Criteria**:
- [ ] Agent events are emitted in correct order
- [ ] Token usage is recorded for all calls
- [ ] Streaming emits progress events
- [ ] Errors are properly handled and emitted

### Task 3: Implement _call_llm_with_tools()

**Description**: Create tool-enabled LLM calling with event emission.

**Implementation Details**:
- [ ] Implement `_call_llm_with_tools()` async method
- [ ] Accept tools list and tool_handlers dict
- [ ] Wrap tool handlers with event emission
- [ ] Emit agent_start event before calling
- [ ] Call OpenAIClient.chat_with_tools()
- [ ] Record accumulated token usage
- [ ] Emit agent_end event after completion
- [ ] Handle errors and emit failed events

**Acceptance Criteria**:
- [ ] Tool calls emit tool_call events
- [ ] Tool results emit tool_result events
- [ ] All iterations' token usage is accumulated
- [ ] Max iterations is respected

### Task 4: Implement Event Emission Helpers

**Description**: Create methods for emitting agent lifecycle events.

**Implementation Details**:
- [ ] Implement `_emit_agent_start()` method
- [ ] Implement `_emit_agent_progress()` method
- [ ] Implement `_emit_agent_end()` method
- [ ] Check for event_emitter before emitting

**Acceptance Criteria**:
- [ ] Events are only emitted if event_emitter exists
- [ ] All required event fields are populated
- [ ] Events match the event schema

### Task 5: Implement Tool Handler Wrapper

**Description**: Create wrapper that adds event emission to tool handlers.

**Implementation Details**:
- [ ] Implement `_wrap_tool_handler()` method
- [ ] Emit tool_call event before execution
- [ ] Emit tool_result event on success
- [ ] Emit tool_result event with error on failure
- [ ] Return async wrapped function

**Acceptance Criteria**:
- [ ] Tool call events include tool name and input
- [ ] Tool result events include success status
- [ ] Errors are caught and emitted properly
- [ ] Original handler return value is preserved

## Technical Specifications

### Method Signatures

```python
class BaseAgent:
    def __init__(
        self,
        db,
        session_id: str,
        settings: Settings,
        event_emitter: Optional[EventEmitter] = None,
        agent_id: Optional[str] = None,
        task_id: Optional[str] = None,
        token_tracker: Optional[TokenTrackerService] = None,
    ) -> None:
        # Initialize LLM client
        self._llm_client = OpenAIClient(
            settings=settings,
            token_tracker=token_tracker,
        )

    async def _call_llm(
        self,
        messages: List[dict],
        *,
        agent_type: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        tools: Optional[List] = None,
        stream: bool = False,
        emit_progress: bool = True,
        context: Optional[str] = None,
    ) -> LLMResponse

    async def _call_llm_with_tools(
        self,
        messages: List[dict],
        tools: List,
        tool_handlers: dict,
        *,
        agent_type: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_iterations: int = 10,
        context: Optional[str] = None,
    ) -> LLMResponse
```

### Event Flow

```
_call_llm() / _call_llm_with_tools()
    │
    ├─> _emit_agent_start()
    │       └─> AgentStartEvent(agent_id, agent_type, task_id)
    │
    ├─> LLM Processing
    │       ├─> (streaming) _emit_agent_progress()
    │       │       └─> AgentProgressEvent(message, progress)
    │       │
    │       └─> (tools) _wrap_tool_handler()
    │               ├─> ToolCallEvent(tool_name, tool_input)
    │               └─> ToolResultEvent(success, tool_output/error)
    │
    ├─> TokenTrackerService.record_usage()
    │
    └─> _emit_agent_end()
            └─> AgentEndEvent(status, summary)
```

## Testing Requirements

- [ ] Unit test for _call_llm() with mocked LLM client
- [ ] Unit test for _call_llm() streaming mode
- [ ] Unit test for _call_llm_with_tools() with mocked handlers
- [ ] Unit test for event emission (all three event types)
- [ ] Unit test for tool handler wrapper
- [ ] Integration test with real token tracker

## Notes & Warnings

1. **Event Emission**: Always check event_emitter exists before emitting
2. **Token Tracking**: Only record if token_usage is present in response
3. **Error Handling**: Errors should still emit agent_end with failed status
4. **Tool Wrapping**: Ensure tool handlers remain async after wrapping
5. **Progress Calculation**: Stream progress should be reasonable (10-90% range)
