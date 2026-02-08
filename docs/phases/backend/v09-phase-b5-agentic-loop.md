# Phase B5: Agentic Loop Core

## Metadata

- **Category**: Backend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: High
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: v09-B1, v09-B2, v09-B3, v09-B4
  - **Blocks**: v09-B6 (API Integration)

## Goal

Implement the core agentic loop (`run_agentic_loop()`) and `SoulOrchestrator` that replaces the LangGraph graph execution with a simple while-loop that lets the LLM decide which tools to call.

## Detailed Tasks

### Task 1: Agentic Loop

**Description**: The `run_agentic_loop()` async generator that drives tool-calling.

**Implementation Details**:
- [ ] Build messages from `context.build_messages()`
- [ ] Call `llm_client.chat_completion()` with `tools=registry.get_openai_tools()`
- [ ] If no `tool_calls` → yield final text, break
- [ ] For each tool call: if `ask_user` → yield `waiting_input` and return (loop suspends)
- [ ] Otherwise execute via `registry.execute()`, emit events, append to context
- [ ] Call `context.maybe_compact()` after each step
- [ ] Check cancellation via `RunService.is_cancelled(run_id)`
- [ ] Safety: max 30 steps, 3 consecutive errors, cancellation check

**Files to modify/create**:
- `packages/backend/app/soul/loop.py`

**Acceptance Criteria**:
- [ ] Loop terminates on: no tool calls, max steps, max errors, cancellation
- [ ] `ask_user` pauses loop and yields `waiting_input`
- [ ] Resume with answers continues loop from where it left off

---

### Task 2: SoulOrchestrator

**Description**: Drop-in replacement for `AgentOrchestrator` using the agentic loop.

**Implementation Details**:
- [ ] Implement `stream_responses()` matching existing interface signature
- [ ] Build `ToolContext` from session state
- [ ] Load `ConversationContext` from DB
- [ ] Register all 9 tools into `ToolRegistry`
- [ ] Translate `LoopEvent`s into `OrchestratorResponse` yields
- [ ] Manage run lifecycle via `RunService`

**Files to modify/create**:
- `packages/backend/app/soul/orchestrator.py`

**Acceptance Criteria**:
- [ ] `stream_responses()` yields `OrchestratorResponse` objects
- [ ] Events stream correctly to frontend via existing SSE
- [ ] Run lifecycle managed correctly
- [ ] Retry with exponential backoff for transient LLM errors

---

### Task 3: LoopEvent Types

**Description**: Define the event types yielded by the agentic loop.

**Implementation Details**:
- [ ] `step_start`, `tool_call`, `tool_result`, `waiting_input`, `text`, `step_end`, `complete`, `error`

**Files to modify/create**:
- `packages/backend/app/soul/loop.py` (LoopEvent dataclass)

---

### Task 4: Unit Tests

**Files to modify/create**:
- `packages/backend/tests/test_soul_loop.py`
- `packages/backend/tests/test_soul_orchestrator.py`

**Acceptance Criteria**:
- [ ] Mock LLM text-only → loop exits after 1 step
- [ ] Mock LLM tool call → execute → text → exits after 2 steps
- [ ] Mock LLM 30+ calls → exits at max_steps
- [ ] Mock LLM errors → exits at max_consecutive_errors
- [ ] Mock `ask_user` → yields `waiting_input`, resume works
- [ ] Orchestrator yields correct `OrchestratorResponse` contract

## Technical Specifications

### Loop Signature

```python
async def run_agentic_loop(
    context: ConversationContext,
    registry: ToolRegistry,
    llm_client: OpenAIClient,
    tool_ctx: ToolContext,
    event_emitter: EventEmitter,
    max_steps: int = 30,
    max_consecutive_errors: int = 3,
) -> AsyncGenerator[LoopEvent, None]:
```

### LoopEvent Types

| Type | Fields | Description |
|------|--------|-------------|
| `step_start` | `step: int` | New loop iteration |
| `tool_call` | `name, arguments` | LLM requested tool |
| `tool_result` | `name, result` | Tool execution result |
| `waiting_input` | `questions` | Loop suspended for user |
| `text` | `content` | Assistant text output |
| `step_end` | `step: int` | Iteration complete |
| `complete` | — | Loop finished |
| `error` | `error: str` | Loop failed |

### OrchestratorResponse Contract

Must match existing 12-field dataclass (see B1 contract freeze).

## Notes & Warnings

- The `ask_user` blocking behavior requires the loop to **return** (not just yield) — the orchestrator must persist context and re-invoke the loop on resume
- `SOUL_MAX_STEPS` env var controls the safety limit (default 30)
- The orchestrator must handle the case where the LLM never calls any tools (pure text response)
