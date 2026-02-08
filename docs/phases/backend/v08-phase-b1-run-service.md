# Phase B1: Run Service + State Machine + CRUD API

## Metadata

- **Category**: Backend
- **Priority**: P0
- **Estimated Complexity**: High
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: v08-D1 (Run Data Layer)
  - **Blocks**: v08-B3 (Orchestration Run Integration), v08-B4 (Chat Compat Adapter)

## Goal

Implement `RunService` with full state machine logic and the Run CRUD API endpoints (`POST /api/runs`, `GET /api/runs/{run_id}`, `POST /api/runs/{run_id}/resume`, `POST /api/runs/{run_id}/cancel`).

## Detailed Tasks

### Task 1: Implement RunService Core

**Description**: Create the RunService with state machine management.

**Implementation Details**:
- [ ] Create `packages/backend/app/services/run.py`
- [ ] Implement `create_run(session_id, message, generate_now, style_reference, target_pages)` → creates DB record with status `queued`
- [ ] Implement `start_run(run_id)` → transitions `queued → running`, sets `started_at`
- [ ] Implement `resume_run(run_id, resume_payload)` → validates `waiting_input` state, transitions to `running`, stores resume_payload
- [ ] Implement `cancel_run(run_id)` → idempotent cancel with rules per spec 8.4
- [ ] Implement `persist_run_state(run_id, status, **kwargs)` → generic state update
- [ ] Implement `get_run(run_id)` → fetch run with all fields
- [ ] Implement `list_runs(session_id)` → list runs for a session ordered by created_at
- [ ] State machine validation: reject invalid transitions (e.g., `completed → running`)

**Files to modify/create**:
- `packages/backend/app/services/run.py`

**Acceptance Criteria**:
- [ ] All 6 states supported: queued, running, waiting_input, completed, failed, cancelled
- [ ] Invalid state transitions raise appropriate errors
- [ ] Cancel is idempotent per spec (200 for terminal states, 202 for active states)
- [ ] Resume only works from `waiting_input` state (409 otherwise)

---

### Task 2: Implement Run API Endpoints

**Description**: Create the REST API endpoints for Run management.

**Implementation Details**:
- [ ] Create `packages/backend/app/api/runs.py`
- [ ] `POST /api/runs` — create run, return run_id + status
- [ ] `GET /api/runs/{run_id}` — return full run details
- [ ] `POST /api/runs/{run_id}/resume` — resume with payload
- [ ] `POST /api/runs/{run_id}/cancel` — cancel run
- [ ] `GET /api/runs/{run_id}/events` — run event stream (SSE or JSON based on Accept header)
- [ ] Error codes: 400 (bad params), 404 (not found), 409 (state conflict), 422 (semantic error), 500 (internal)
- [ ] Support `Idempotency-Key` header for create and resume endpoints

**Files to modify/create**:
- `packages/backend/app/api/runs.py`
- `packages/backend/app/main.py` (register router)

**Acceptance Criteria**:
- [ ] All 5 endpoints functional
- [ ] Correct HTTP status codes per spec section 8
- [ ] SSE vs JSON content negotiation works via Accept header
- [ ] Idempotency-Key prevents duplicate creates within 24h window

---

### Task 3: Run Event Stream Endpoint

**Description**: Implement the run-scoped event stream with SSE and JSON polling support.

**Implementation Details**:
- [ ] `GET /api/runs/{run_id}/events?since_seq=&limit=1000`
- [ ] If `Accept: text/event-stream` → SSE stream
- [ ] If `Accept: application/json` (or no Accept) → JSON array response
- [ ] Filter events by `run_id` from `session_events` table
- [ ] Support `since_seq` for incremental polling
- [ ] Default `limit=1000`, validate bounds

**Files to modify/create**:
- `packages/backend/app/api/runs.py`
- `packages/backend/app/services/event_store.py` (add run-scoped query)

**Acceptance Criteria**:
- [ ] SSE stream delivers events in real-time for active runs
- [ ] JSON polling returns correct event slice
- [ ] `since_seq` filtering works correctly
- [ ] Events ordered by `seq ASC`

---

### Task 4: Feature Flags

**Description**: Add feature flags for gradual rollout.

**Implementation Details**:
- [ ] Add `run_api_enabled: bool = True` to config
- [ ] Add `chat_use_run_adapter: bool = False` to config (for phase B4)
- [ ] Run API endpoints return 404 when `run_api_enabled=False`

**Files to modify/create**:
- `packages/backend/app/config.py`

**Acceptance Criteria**:
- [ ] Feature flags configurable via environment variables
- [ ] Run API disabled when flag is off

## Technical Specifications

### State Machine Transitions

```
queued → running (start_run)
running → waiting_input (interrupt)
running → completed (verify pass + render done)
running → failed (unrecoverable error)
running → cancelled (user cancel)
waiting_input → running (resume_run)
waiting_input → cancelled (user cancel)
queued → cancelled (user cancel)
```

### API Endpoints

| Method | Path | Request | Response | Status Codes |
|--------|------|---------|----------|-------------|
| POST | /api/runs | RunCreate | RunResponse | 201, 400, 422 |
| GET | /api/runs/{run_id} | - | RunResponse | 200, 404 |
| POST | /api/runs/{run_id}/resume | RunResumeRequest | RunResponse | 200, 404, 409 |
| POST | /api/runs/{run_id}/cancel | - | RunResponse | 200, 202, 404 |
| GET | /api/runs/{run_id}/events | query params | Event[] / SSE | 200, 404 |

### Concurrency Rule

Each run can only have one active execution instance. Concurrent resume requests to the same run return 409.

## Testing Requirements

- [ ] Unit test: state machine transitions (all valid paths)
- [ ] Unit test: invalid state transitions rejected
- [ ] Unit test: create_run returns correct initial state
- [ ] Unit test: cancel idempotency (terminal states return 200)
- [ ] Unit test: resume from non-waiting_input returns 409
- [ ] Integration test: full run lifecycle (create → start → complete)
- [ ] Integration test: interrupt → resume flow
- [ ] Integration test: cancel during running state
- [ ] Integration test: event stream filtering by run_id

## Notes & Warnings

- `resumed` is an event, not a persistent state — after resume, status goes to `running`
- Concurrent resume requests must be handled (reject or merge per idempotency)
- `checkpoint_thread` defaults to `session_id:run_id` to isolate concurrent runs
