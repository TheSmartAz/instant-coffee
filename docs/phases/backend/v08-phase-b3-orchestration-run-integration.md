# Phase B3: Orchestration Run Integration

## Metadata

- **Category**: Backend
- **Priority**: P0
- **Estimated Complexity**: High
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: v08-B1 (Run Service)
  - **Blocks**: v08-B5-tool-policy (Tool Policy Hooks), v08-B6-verify-gate (Verify Gate)

## Goal

Integrate the Run lifecycle into the LangGraph orchestration pipeline so that every graph execution is wrapped in a Run, with state transitions, checkpoint alignment, and interrupt/resume handled through RunService.

## Detailed Tasks

### Task 1: Extend GraphState for Run

**Description**: Add run-related fields to the LangGraph state.

**Implementation Details**:
- [ ] Add `run_status: str` to GraphState
- [ ] Add `verify_report: Optional[dict]` to GraphState
- [ ] Add `verify_blocked: Optional[bool]` to GraphState
- [ ] Add `current_node: Optional[str]` to GraphState

**Files to modify/create**:
- `packages/backend/app/graph/state.py`

**Acceptance Criteria**:
- [ ] All 4 new fields added to GraphState
- [ ] Existing graph state fields unchanged
- [ ] Fields serializable for checkpointing

---

### Task 2: Wrap Graph Execution in Run Lifecycle

**Description**: Modify the graph orchestrator to create and manage runs.

**Implementation Details**:
- [ ] Before graph execution: call `RunService.create_run()` and `RunService.start_run()`
- [ ] Emit `run_created` and `run_started` events
- [ ] On graph completion: call `RunService.persist_run_state(run_id, 'completed')`, emit `run_completed`
- [ ] On graph error: call `RunService.persist_run_state(run_id, 'failed')`, emit `run_failed`
- [ ] On interrupt: call `RunService.persist_run_state(run_id, 'waiting_input')`, emit `run_waiting_input`
- [ ] Set `checkpoint_thread = session_id:run_id` to isolate concurrent runs

**Files to modify/create**:
- `packages/backend/app/graph/orchestrator.py`
- `packages/backend/app/graph/graph.py`

**Acceptance Criteria**:
- [ ] Every graph execution creates a run record
- [ ] Run status accurately reflects graph execution state
- [ ] Run events emitted at each state transition
- [ ] Checkpoint thread isolated per run

---

### Task 3: Implement Run Resume via Graph

**Description**: Wire RunService resume to LangGraph `Command(resume=...)`.

**Implementation Details**:
- [ ] `RunService.resume_run()` validates state, then invokes graph with `Command(resume=payload)`
- [ ] Resume uses same `checkpoint_thread` as original run
- [ ] After resume, run transitions back to `running`
- [ ] Emit `run_resumed` event

**Files to modify/create**:
- `packages/backend/app/services/run.py`
- `packages/backend/app/graph/orchestrator.py`

**Acceptance Criteria**:
- [ ] Resume from `waiting_input` works end-to-end
- [ ] Same run_id maintained across interrupt/resume
- [ ] Graph continues from checkpoint
- [ ] `run_resumed` event emitted

---

### Task 4: Implement Run Cancel

**Description**: Wire cancel to send cooperative cancellation signal to graph execution.

**Implementation Details**:
- [ ] On cancel: set a cancellation flag that graph nodes check
- [ ] Graph nodes should check cancellation at safe points (between LLM calls)
- [ ] After cancellation confirmed: emit `run_cancelled` event
- [ ] Idempotent: cancelling already-terminal run returns success

**Files to modify/create**:
- `packages/backend/app/services/run.py`
- `packages/backend/app/graph/orchestrator.py`

**Acceptance Criteria**:
- [ ] Cancel stops graph execution cooperatively
- [ ] Run status transitions to `cancelled`
- [ ] No new events emitted after cancellation
- [ ] Idempotent cancel behavior per spec

## Technical Specifications

### GraphState Extensions

```python
class GraphState(TypedDict):
    # ... existing fields ...
    run_status: str                    # mirrors RunService status
    verify_report: Optional[dict]      # verify gate results
    verify_blocked: Optional[bool]     # whether verify blocked render
    current_node: Optional[str]        # current executing node name
```

### Run-Graph Lifecycle Flow

```
POST /api/runs → RunService.create_run() → status=queued
                → RunService.start_run()  → status=running
                → graph.invoke()
                    → nodes execute...
                    → interrupt() → status=waiting_input
                    → resume()   → status=running
                    → complete   → status=completed
                    → error      → status=failed
```

### Checkpoint Thread Isolation

```
checkpoint_thread = f"{session_id}:{run_id}"
```

This prevents concurrent runs from sharing checkpoint state.

## Testing Requirements

- [ ] Unit test: GraphState extensions serialize correctly
- [ ] Unit test: run created before graph execution
- [ ] Unit test: run status transitions during graph lifecycle
- [ ] Integration test: full run lifecycle through graph
- [ ] Integration test: interrupt → resume preserves state
- [ ] Integration test: cancel stops execution
- [ ] Integration test: concurrent runs use separate checkpoints

## Notes & Warnings

- `run_status` in GraphState should mirror RunService state but is not the source of truth — RunService DB record is authoritative
- Cancel is cooperative — long-running LLM calls may not stop immediately
- Checkpoint thread must be unique per run to prevent state corruption
