# Phase B8: Tool Event Integration

## Metadata

- **Category**: Backend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: Medium
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: B3 (BaseAgent Enhancement), B5-B7 (Agent Implementations)
  - **Blocks**: F1 (Frontend Event Display)

## Goal

Integrate tool calling events into the agent execution flow, ensuring all tool calls and results are properly emitted for frontend display.

## Detailed Tasks

### Task 1: Verify Tool Call Events

**Description**: Ensure tool_call events are emitted when LLM requests tool execution.

**Implementation Details**:
- [x] Verify ToolCallEvent is defined in events/models.py
- [x] Verify BaseAgent._wrap_tool_handler() emits tool_call
- [x] Ensure event includes: agent_id, agent_type, task_id, tool_name, tool_input
- [x] Test event emission in all three agents

**Acceptance Criteria**:
- [x] Tool calls emit events before execution
- [x] Event includes all required fields
- [x] Event is serializable to JSON

### Task 2: Verify Tool Result Events

**Description**: Ensure tool_result events are emitted after tool execution.

**Implementation Details**:
- [x] Verify ToolResultEvent is defined in events/models.py
- [x] Verify BaseAgent._wrap_tool_handler() emits tool_result
- [x] Ensure event includes: agent_id, agent_type, task_id, tool_name, success, tool_output/error
- [x] Test both success and failure cases

**Acceptance Criteria**:
- [x] Tool results emit events after execution
- [x] Success events include tool_output
- [x] Failure events include error message
- [x] Event is serializable to JSON

### Task 3: Update Orchestrator for Tool Events

**Description**: Ensure orchestrator properly passes tool events to SSE stream.

**Implementation Details**:
- [x] Verify orchestrator subscribes to all event types
- [x] Ensure tool events flow through to frontend
- [x] Test tool event propagation in chat flow

**Acceptance Criteria**:
- [x] Tool events appear in SSE stream
- [x] Events are in correct order (tool_call before tool_result)
- [x] Multiple tool calls in one request are handled

### Task 4: Add Tool Execution Logging

**Description**: Add logging for tool execution for debugging.

**Implementation Details**:
- [x] Log tool name and input before execution
- [x] Log tool result after execution
- [x] Log errors if tool fails
- [x] Use appropriate log levels

**Acceptance Criteria**:
- [x] Tool calls are logged at INFO level
- [x] Tool errors are logged at WARNING level
- [x] Logs include relevant context

## Technical Specifications

### ToolCallEvent Structure

```python
class ToolCallEvent(Event):
    type: Literal["tool_call"] = "tool_call"
    agent_id: str
    agent_type: str
    task_id: Optional[str]
    tool_name: str
    tool_input: Dict[str, Any]
    timestamp: datetime
```

### ToolResultEvent Structure

```python
class ToolResultEvent(Event):
    type: Literal["tool_result"] = "tool_result"
    agent_id: str
    agent_type: str
    task_id: Optional[str]
    tool_name: str
    success: bool
    tool_output: Optional[Any] = None
    error: Optional[str] = None
    timestamp: datetime
```

### Event Flow

```
LLM returns tool_calls
    │
    ▼
For each tool_call:
    │
    ├─> Emit ToolCallEvent
    │       └─> agent_id, agent_type, tool_name, tool_input
    │
    ├─> Execute tool handler
    │       ├─> Success?
    │       │       ├─> Yes: Emit ToolResultEvent(success=True, tool_output=...)
    │       │       └─> No:  Emit ToolResultEvent(success=False, error=...)
    │       │
    │       └─> Return result to LLM
    │
    └─> Add tool message to conversation history
```

## Testing Requirements

- [x] Unit test for tool_call event emission
- [x] Unit test for tool_result event emission (success)
- [x] Unit test for tool_result event emission (failure)
- [x] Integration test for event propagation to SSE
- [x] Integration test for multiple tool calls in one request
### Implementation Notes

- Implemented agent_type on tool events and JSON-safe payload normalization in BaseAgent.
- Added tool execution logging with redaction.
- SSE stream for chat message flow now drains and emits tool events.

## Notes & Warnings

1. **Event Ordering**: tool_call must always come before corresponding tool_result
2. **Error Handling**: Tool errors should still emit tool_result event
3. **Serialization**: Ensure tool_input and tool_output are JSON-serializable
4. **PII Prevention**: Be careful not to log sensitive data in tool events
5. **Performance**: Too many tool events could flood frontend; consider batching if needed
