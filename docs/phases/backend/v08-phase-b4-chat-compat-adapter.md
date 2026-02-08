# Phase B4: Chat Compatibility Adapter

## Metadata

- **Category**: Backend
- **Priority**: P0
- **Estimated Complexity**: Medium
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: v08-B1 (Run Service), v08-B2 (Event Layer Upgrade)
  - **Blocks**: None

## Goal

Adapt the existing `/api/chat` and `/api/chat/stream` endpoints to internally use RunService, while maintaining full backward compatibility with the current frontend. This is the bridge that allows gradual migration.

## Detailed Tasks

### Task 1: Implement Chat-to-Run Adapter

**Description**: Create an adapter layer that translates chat requests into run operations.

**Implementation Details**:
- [ ] Create adapter logic in `packages/backend/app/api/chat.py`
- [ ] When `chat_use_run_adapter` flag is enabled:
  - Chat request → `RunService.create_run()` + `RunService.start_run()`
  - Resume request → `RunService.resume_run()`
  - Subscribe to run events → translate to chat response format
- [ ] When flag is disabled: use existing chat flow (no change)
- [ ] Aggregate run events into compatible response fields: `message`, `action`, `preview`

**Files to modify/create**:
- `packages/backend/app/api/chat.py`

**Acceptance Criteria**:
- [ ] With flag OFF: existing behavior unchanged
- [ ] With flag ON: chat internally creates runs
- [ ] Response format identical to current chat API
- [ ] Frontend sees no difference

---

### Task 2: Adapt Stream Endpoint

**Description**: Ensure `/api/chat/stream` works with run-based event flow.

**Implementation Details**:
- [ ] When adapter enabled: stream run events translated to existing SSE format
- [ ] Map run events to existing event types where possible
- [ ] New event types (run_*, verify_*, tool_policy_*) passed through for forward-compatible clients
- [ ] Maintain existing `seq` ordering

**Files to modify/create**:
- `packages/backend/app/api/chat.py`

**Acceptance Criteria**:
- [ ] SSE stream works identically for existing frontend
- [ ] New event types included but don't break old clients
- [ ] Stream terminates correctly on run completion/failure/cancel

---

### Task 3: Feature Flag Integration

**Description**: Wire the `chat_use_run_adapter` feature flag.

**Implementation Details**:
- [ ] Read `chat_use_run_adapter` from config
- [ ] Default to `False` (safe rollout)
- [ ] Log when adapter is active vs legacy path
- [ ] Support runtime toggle via config reload (optional)

**Files to modify/create**:
- `packages/backend/app/config.py`
- `packages/backend/app/api/chat.py`

**Acceptance Criteria**:
- [ ] Flag defaults to False
- [ ] Toggling flag switches between legacy and adapter paths
- [ ] Clear logging of which path is active

## Technical Specifications

### Compatibility Mapping

| Chat API Field | Run API Source |
|---------------|---------------|
| `message` | Run input_message / events |
| `action` | Derived from run status |
| `preview` | From render events |
| `session_id` | Passed through |
| `resume` | Mapped to RunService.resume_run() |

### Gradual Migration Phases

1. **Phase 1** (this phase): Chat internally creates runs when flag ON, external API unchanged
2. **Phase 2** (future): Frontend optionally calls Run API directly
3. **Phase 3** (future): Chat API deprecated in favor of Run API

## Testing Requirements

- [ ] Unit test: adapter OFF → legacy path used
- [ ] Unit test: adapter ON → run created for chat request
- [ ] Unit test: response format matches existing chat API contract
- [ ] Integration test: full chat flow through adapter
- [ ] Integration test: stream endpoint through adapter
- [ ] Regression test: existing frontend E2E tests pass with adapter ON

## Notes & Warnings

- This phase should be the LAST backend phase merged to minimize regression risk
- Keep the adapter thin — translate, don't add new logic
- If adapter causes issues, disable flag to instantly revert
- Old sessions (no runs) must still work via session-level event queries
