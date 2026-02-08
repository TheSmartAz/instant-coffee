# Phase B7: App Data API

## Metadata

- **Category**: Backend
- **Priority**: P0
- **Estimated Complexity**: Medium
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: v08-D2 (App Data PG Schema)
  - **Blocks**: v08-F1 (Data Tab Frontend), v08-B8 (Generation Integration)

## Goal

Expose CRUD API endpoints for app data at `/api/sessions/{id}/data/*`, enabling the frontend Data Tab and iframe JS runtime to read/write structured app data stored in PostgreSQL.

## Detailed Tasks

### Task 1: Create Data API Router

**Description**: Implement the REST API endpoints for app data CRUD.

**Implementation Details**:
- [ ] Create `packages/backend/app/api/data.py`
- [ ] `GET /api/sessions/{id}/data/tables` — list all tables + column definitions
- [ ] `GET /api/sessions/{id}/data/{table}` — query table records (paginated)
- [ ] `POST /api/sessions/{id}/data/{table}` — insert record
- [ ] `DELETE /api/sessions/{id}/data/{table}/{row_id}` — delete record
- [ ] `GET /api/sessions/{id}/data/{table}/stats` — aggregation statistics
- [ ] Register router in `main.py`

**Files to modify/create**:
- `packages/backend/app/api/data.py`
- `packages/backend/app/main.py`

**Acceptance Criteria**:
- [ ] All 5 endpoints functional
- [ ] Correct HTTP status codes (400/404/409/422/500)
- [ ] Pagination works with limit (max 200) and offset

---

### Task 2: Input Validation and Security

**Description**: Enforce strict validation on all data API inputs.

**Implementation Details**:
- [ ] `table` parameter must match a table in the session's data_model (whitelist)
- [ ] `order_by` must match a known column name (whitelist)
- [ ] `limit` capped at 200, `offset >= 0`
- [ ] Write requests require object body (reject top-level arrays)
- [ ] Reject identifiers containing `.` (prevent cross-schema access)
- [ ] All values parameterized (no SQL interpolation)

**Files to modify/create**:
- `packages/backend/app/api/data.py`

**Acceptance Criteria**:
- [ ] Invalid table names return 404
- [ ] Invalid order_by returns 400
- [ ] Limit > 200 capped or returns 400
- [ ] SQL injection attempts blocked

---

### Task 3: Session Cleanup Integration

**Description**: Wire schema cleanup into session deletion flow.

**Implementation Details**:
- [ ] On `DELETE /api/sessions/{id}`: call `AppDataStore.drop_schema(session_id)`
- [ ] Handle case where schema doesn't exist (no-op)
- [ ] Log cleanup action

**Files to modify/create**:
- `packages/backend/app/api/sessions.py`

**Acceptance Criteria**:
- [ ] Session deletion cleans up PG schema
- [ ] Missing schema doesn't cause error
- [ ] Cleanup logged

## Technical Specifications

### API Endpoints

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| GET | /api/sessions/{id}/data/tables | List tables + columns | `{tables: [{name, columns: [{name, type}]}]}` |
| GET | /api/sessions/{id}/data/{table}?limit=50&offset=0&order_by=created_at | Query records | `{records: [...], total: N, limit, offset}` |
| POST | /api/sessions/{id}/data/{table} | Insert record | `{record: {...}}` |
| DELETE | /api/sessions/{id}/data/{table}/{row_id} | Delete record | `{deleted: true}` |
| GET | /api/sessions/{id}/data/{table}/stats | Aggregation | `{count: N, ...}` |

### Error Codes

- `400`: Invalid parameters (bad limit, invalid order_by)
- `404`: Session/table/record not found
- `409`: Conflict (duplicate key)
- `422`: Semantic validation failure
- `500`: Internal error

## Testing Requirements

- [ ] Unit test: list tables endpoint
- [ ] Unit test: query with pagination
- [ ] Unit test: insert record
- [ ] Unit test: delete record
- [ ] Unit test: stats endpoint
- [ ] Unit test: invalid table name rejected
- [ ] Unit test: SQL injection prevention
- [ ] Unit test: session cleanup drops schema
- [ ] Integration test: full CRUD lifecycle

## Notes & Warnings

- Table/column names come from data_model — always validate against whitelist
- Never interpolate user input into SQL identifiers
- Stats endpoint may need optimization for large tables (consider caching)
