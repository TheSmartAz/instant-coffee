# Phase B2: Event Layer Upgrade

## Metadata

- **Category**: Backend
- **Priority**: P0
- **Estimated Complexity**: Medium
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: v08-D1 (Run Data Layer)
  - **Blocks**: v08-B4 (Chat Compat Adapter)

## Goal

Add new run/verify/policy event types, enforce the unified event envelope with mandatory `run_id` for run-scoped events, and add run-dimension query support to the event store.

## Detailed Tasks

### Task 1: Add New Event Types

**Description**: Register all new event types for run lifecycle, verify gate, and tool policy.

**Implementation Details**:
- [ ] Add to `packages/backend/app/events/types.py`:
  - `run_created`, `run_started`, `run_waiting_input`, `run_resumed`
  - `run_completed`, `run_failed`, `run_cancelled`
  - `verify_start`, `verify_pass`, `verify_fail`
  - `tool_policy_blocked`, `tool_policy_warn`

**Files to modify/create**:
- `packages/backend/app/events/types.py`

**Acceptance Criteria**:
- [ ] All 12 new event types registered
- [ ] Existing event types unchanged

---

### Task 2: Enforce Unified Event Envelope

**Description**: Update event models to enforce the unified envelope structure.

**Implementation Details**:
- [ ] Update `packages/backend/app/events/models.py` to enforce:
  - Required: `type`, `timestamp`, `session_id`, `seq`, `source`
  - Required for run-scoped events: `run_id`
  - Optional: `event_id`
  - `payload` must be object (not string)
- [ ] Add validation that run lifecycle/verify/policy events always include `run_id`
- [ ] `seq` remains session-level monotonic (not per-run)

**Files to modify/create**:
- `packages/backend/app/events/models.py`

**Acceptance Criteria**:
- [ ] Run-scoped events without `run_id` are rejected
- [ ] Legacy events (no run_id) still valid
- [ ] `payload` enforced as dict, not string

---

### Task 3: Update Event Emitter

**Description**: Update the event emitter to support `run_id` and `event_id` fields.

**Implementation Details**:
- [ ] Update `packages/backend/app/events/emitter.py` to accept optional `run_id` and `event_id`
- [ ] When emitting run-scoped events, auto-populate `run_id` from context
- [ ] Generate `event_id` (UUID) when not provided (for idempotent dedup)

**Files to modify/create**:
- `packages/backend/app/events/emitter.py`

**Acceptance Criteria**:
- [ ] Emitter passes `run_id` through to event store
- [ ] `event_id` auto-generated when missing
- [ ] Backward compatible — existing emit calls still work

---

### Task 4: Add Run-Dimension Event Queries

**Description**: Extend event store to support querying events by run_id.

**Implementation Details**:
- [ ] Add `get_events_by_run(session_id, run_id, since_seq, limit)` to event store
- [ ] Query uses `idx_session_event_run_seq` index
- [ ] Results ordered by `seq ASC`
- [ ] Existing `get_events_by_session()` unchanged (aggregated view)

**Files to modify/create**:
- `packages/backend/app/services/event_store.py`

**Acceptance Criteria**:
- [ ] Run-scoped query returns only events for that run
- [ ] `since_seq` filtering works
- [ ] Session-level query still returns all events (including those with run_id)

---

### Task 5: Update Events API

**Description**: Add run-dimension event endpoint and keep session-level endpoint.

**Implementation Details**:
- [ ] Ensure `GET /api/sessions/{session_id}/events` still works (aggregated)
- [ ] Wire `GET /api/runs/{run_id}/events` to use new run-scoped query (endpoint in B1)

**Files to modify/create**:
- `packages/backend/app/api/events.py`

**Acceptance Criteria**:
- [ ] Session-level events endpoint unchanged
- [ ] Run-level events endpoint returns filtered results

## Technical Specifications

### New Event Types

```
run_created, run_started, run_waiting_input, run_resumed,
run_completed, run_failed, run_cancelled,
verify_start, verify_pass, verify_fail,
tool_policy_blocked, tool_policy_warn
```

### Unified Event Envelope

```json
{
  "type": "run_started",
  "timestamp": "2026-02-06T10:00:00Z",
  "session_id": "...",
  "run_id": "...",
  "seq": 101,
  "source": "session",
  "event_id": "...",
  "payload": {"phase": "langgraph"}
}
```

### `seq` Semantics

- Session-level monotonic (global order)
- Run queries return original `seq` values (no re-numbering)
- Run-internal order via `ORDER BY seq ASC`

## Testing Requirements

- [ ] Unit test: all 12 new event types registered
- [ ] Unit test: run-scoped event without run_id rejected
- [ ] Unit test: legacy event without run_id accepted
- [ ] Unit test: event emitter passes run_id correctly
- [ ] Unit test: run-dimension query returns correct events
- [ ] Unit test: since_seq filtering
- [ ] Integration test: emit run events → query by run_id → verify results

## Notes & Warnings

- `seq` is session-level, NOT per-run — do not re-number within a run
- Historical events with `run_id = NULL` must remain queryable via session endpoint
- `event_id` is for cross-system dedup — optional but recommended
