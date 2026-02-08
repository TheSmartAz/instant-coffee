# Phase D1: Run Data Layer

## Metadata

- **Category**: Database
- **Priority**: P0
- **Estimated Complexity**: Medium
- **Parallel Development**: ✅ Can develop in parallel
- **Dependencies**:
  - **Blocked by**: None
  - **Blocks**: v08-B1 (Run Service), v08-B2 (Event Layer Upgrade)

## Goal

Create the `session_runs` table and extend `session_events` with `run_id`/`event_id` columns, plus migration functions, to support Run as a first-class object.

## Detailed Tasks

### Task 1: Create `session_runs` Table Model

**Description**: Define the SQLAlchemy model for the `session_runs` table.

**Implementation Details**:
- [ ] Add `SessionRun` model to `packages/backend/app/db/models.py`
- [ ] Fields: `id` (VARCHAR PK, uuid hex), `session_id` (VARCHAR NOT NULL, FK), `parent_run_id` (VARCHAR NULL), `trigger_source` (VARCHAR(20) NOT NULL), `status` (VARCHAR(20) NOT NULL), `input_message` (TEXT NULL), `resume_payload` (JSON NULL), `checkpoint_thread` (VARCHAR NULL), `checkpoint_ns` (VARCHAR NULL), `latest_error` (JSON NULL), `metrics` (JSON NULL), `started_at` (DATETIME NULL), `finished_at` (DATETIME NULL), `created_at` (DATETIME NOT NULL), `updated_at` (DATETIME NOT NULL)
- [ ] Add relationship to `Session` model

**Files to modify/create**:
- `packages/backend/app/db/models.py`

**Acceptance Criteria**:
- [ ] `SessionRun` model defined with all fields from spec section 6.1
- [ ] Foreign key relationship to `sessions` table established
- [ ] Default values set (`status='queued'`, timestamps auto-populated)

---

### Task 2: Extend `session_events` Table

**Description**: Add `run_id` and `event_id` columns to the existing `session_events` table.

**Implementation Details**:
- [ ] Add `run_id VARCHAR NULL` column to `SessionEvent` model
- [ ] Add `event_id VARCHAR NULL` column to `SessionEvent` model
- [ ] Historical data keeps `run_id = NULL`

**Files to modify/create**:
- `packages/backend/app/db/models.py`

**Acceptance Criteria**:
- [ ] `run_id` column added, nullable for backward compatibility
- [ ] `event_id` column added, nullable

---

### Task 3: Create Migration Functions

**Description**: Add v0.8 migration functions to create the new table and alter the existing one.

**Implementation Details**:
- [ ] Add `migrate_v08_run_model()` function — creates `session_runs` table with all indexes
- [ ] Add `migrate_v08_event_run_columns()` function — adds `run_id`, `event_id` columns to `session_events`
- [ ] Add indexes: `idx_session_runs_session_created(session_id, created_at)`, `idx_session_runs_status(status)`, `idx_session_runs_parent(parent_run_id)`, `idx_session_event_run_seq(session_id, run_id, seq)`
- [ ] Register migrations in the migration runner

**Files to modify/create**:
- `packages/backend/app/db/migrations.py`

**Acceptance Criteria**:
- [ ] Migration creates `session_runs` table with correct schema
- [ ] Migration adds columns to `session_events` without data loss
- [ ] All 4 indexes created
- [ ] Migration is idempotent (safe to run multiple times)

---

### Task 4: Create Run Pydantic Schemas

**Description**: Define request/response schemas for the Run API.

**Implementation Details**:
- [ ] Create `packages/backend/app/schemas/run.py`
- [ ] Define `RunCreate` schema (session_id, message, generate_now, style_reference, target_pages)
- [ ] Define `RunResponse` schema (run_id, session_id, status, started_at, finished_at, latest_error, metrics, checkpoint_thread, checkpoint_ns, waiting_reason)
- [ ] Define `RunResumeRequest` schema (resume payload)
- [ ] Define `RunStatus` enum (queued, running, waiting_input, completed, failed, cancelled)

**Files to modify/create**:
- `packages/backend/app/schemas/run.py`
- `packages/backend/app/schemas/__init__.py`

**Acceptance Criteria**:
- [ ] All schemas validate correctly with Pydantic
- [ ] `RunStatus` enum covers all 6 states from spec section 5.2
- [ ] Schemas match API contracts in spec section 8

## Technical Specifications

### Table Schema: `session_runs`

```sql
session_runs (
  id                VARCHAR PRIMARY KEY,
  session_id        VARCHAR NOT NULL,
  parent_run_id     VARCHAR NULL,
  trigger_source    VARCHAR(20) NOT NULL,  -- chat | resume | retry | system
  status            VARCHAR(20) NOT NULL,  -- queued/running/waiting_input/completed/failed/cancelled
  input_message     TEXT NULL,
  resume_payload    JSON NULL,
  checkpoint_thread VARCHAR NULL,
  checkpoint_ns     VARCHAR NULL,
  latest_error      JSON NULL,
  metrics           JSON NULL,
  started_at        DATETIME NULL,
  finished_at       DATETIME NULL,
  created_at        DATETIME NOT NULL,
  updated_at        DATETIME NOT NULL
)
```

### Indexes

- `idx_session_runs_session_created(session_id, created_at)`
- `idx_session_runs_status(status)`
- `idx_session_runs_parent(parent_run_id)`
- `idx_session_event_run_seq(session_id, run_id, seq)` (on `session_events`)

### Extended `session_events` Columns

- `run_id VARCHAR NULL`
- `event_id VARCHAR NULL`

## Testing Requirements

- [ ] Unit test: migration creates table with correct columns
- [ ] Unit test: migration adds columns to session_events
- [ ] Unit test: migration is idempotent
- [ ] Unit test: SessionRun model CRUD operations
- [ ] Unit test: RunStatus enum validation
- [ ] Unit test: Pydantic schemas serialize/deserialize correctly

## Notes & Warnings

- Historical events will have `run_id = NULL` — all queries must handle this
- `checkpoint_thread` defaults to `session_id:run_id` to avoid concurrent run conflicts
- `trigger_source` must be one of: `chat`, `resume`, `retry`, `system`
