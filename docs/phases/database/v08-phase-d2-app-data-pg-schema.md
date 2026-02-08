# Phase D2: App Data PG Schema

## Metadata

- **Category**: Database
- **Priority**: P0
- **Estimated Complexity**: High
- **Parallel Development**: ✅ Can develop in parallel (independent of Run system)
- **Dependencies**:
  - **Blocked by**: None
  - **Blocks**: v08-B5 (App Data API), v08-B6 (Generation Integration)

## Goal

Implement PostgreSQL schema-per-session isolation for dynamic app data tables, including the `AppDataStore` service that creates/drops schemas and performs type-mapped table creation from `data_model` definitions.

## Detailed Tasks

### Task 1: Implement `AppDataStore` Core Service

**Description**: Create the core service that manages per-session PG schemas and dynamic table creation.

**Implementation Details**:
- [ ] Create `packages/backend/app/services/app_data_store.py`
- [ ] Implement `create_schema(session_id)` — creates `app_<session_id_slug>` schema
- [ ] Implement `create_tables(session_id, data_model)` — dynamically creates tables from `DataModel.entities`
- [ ] Implement `drop_schema(session_id)` — `DROP SCHEMA CASCADE` for cleanup
- [ ] Implement `list_tables(session_id)` — introspect schema for table/column info
- [ ] Implement schema name sanitization: `lower(session_id)`, replace non-`[a-z0-9_]` with `_`, truncate at 63 chars with short hash if needed
- [ ] Use asyncpg connection pool with `SET search_path` for schema switching

**Files to modify/create**:
- `packages/backend/app/services/app_data_store.py`

**Acceptance Criteria**:
- [ ] Schema created with correct naming convention
- [ ] Tables created with correct column types from TYPE_MAP
- [ ] Schema dropped cleanly with CASCADE
- [ ] Schema name sanitization handles edge cases (long IDs, special chars)

---

### Task 2: Implement Type Mapping

**Description**: Map `data_model` field types to PostgreSQL column types.

**Implementation Details**:
- [ ] Define `TYPE_MAP`: `string→TEXT`, `number→NUMERIC`, `boolean→BOOLEAN`, `array→JSONB`, `object→JSONB`
- [ ] Each table gets auto-generated `id SERIAL PRIMARY KEY`, `created_at TIMESTAMPTZ DEFAULT NOW()`, `updated_at TIMESTAMPTZ DEFAULT NOW()`
- [ ] Handle unknown types gracefully (default to `TEXT` with warning)

**Files to modify/create**:
- `packages/backend/app/services/app_data_store.py`

**Acceptance Criteria**:
- [ ] All 5 type mappings work correctly
- [ ] Auto-generated columns present on every table
- [ ] Unknown types fall back to TEXT

---

### Task 3: Implement CRUD Operations

**Description**: Add record-level CRUD operations to `AppDataStore`.

**Implementation Details**:
- [ ] Implement `insert_record(session_id, table, data)` — parameterized INSERT
- [ ] Implement `query_table(session_id, table, limit, offset, order_by)` — paginated SELECT
- [ ] Implement `delete_record(session_id, table, row_id)` — DELETE by id
- [ ] Implement `get_table_stats(session_id, table)` — COUNT, SUM, GROUP BY aggregations
- [ ] All identifiers (schema/table/column) must pass strict validation + quote_ident
- [ ] All values must use parameterized binding (no string interpolation)
- [ ] `order_by` must be validated against known column whitelist from data_model
- [ ] Reject cross-schema access (no `.` in user-provided identifiers)

**Files to modify/create**:
- `packages/backend/app/services/app_data_store.py`

**Acceptance Criteria**:
- [ ] Insert returns created record with id
- [ ] Query supports pagination with limit (max 200) and offset
- [ ] Delete removes record and returns success
- [ ] Stats return count and numeric aggregations
- [ ] SQL injection attempts are blocked

---

### Task 4: Implement Data Model Evolution

**Description**: Support incremental schema migration when data_model changes across generations.

**Implementation Details**:
- [ ] New entities: `CREATE TABLE IF NOT EXISTS`
- [ ] New fields: `ALTER TABLE ADD COLUMN IF NOT EXISTS`
- [ ] Removed fields: mark as deprecated, do NOT drop
- [ ] Log migration summary (entities added, columns added, columns deprecated)

**Files to modify/create**:
- `packages/backend/app/services/app_data_store.py`

**Acceptance Criteria**:
- [ ] Adding new entity to existing schema works
- [ ] Adding new field to existing table works
- [ ] Existing data preserved during evolution
- [ ] Migration summary returned for logging

---

### Task 5: Connection Pool Configuration

**Description**: Configure asyncpg connection pool for Railway PG deployment.

**Implementation Details**:
- [ ] Read `DATABASE_URL` from environment (Railway provides this)
- [ ] Configure pool with max 15 connections (Railway Starter plan ~20 limit, leave headroom)
- [ ] Add pool initialization to app startup
- [ ] Add pool cleanup to app shutdown

**Files to modify/create**:
- `packages/backend/app/services/app_data_store.py`
- `packages/backend/app/config.py`
- `packages/backend/app/main.py`

**Acceptance Criteria**:
- [ ] Pool connects to Railway PG via DATABASE_URL
- [ ] Pool respects connection limits
- [ ] Graceful startup/shutdown

## Technical Specifications

### Type Mapping

```python
TYPE_MAP = {
    "string": "TEXT",
    "number": "NUMERIC",
    "boolean": "BOOLEAN",
    "array": "JSONB",
    "object": "JSONB",
}
```

### Schema Naming

```
app_<session_id_slug>
  where session_id_slug = re.sub(r'[^a-z0-9_]', '_', session_id.lower())
  truncate to 63 chars with hash suffix if needed
```

### SQL Security Rules

1. All value parameters: parameterized binding only
2. All identifiers: strict regex validation + `quote_ident()`
3. No cross-schema access (reject `.` in user identifiers)
4. Table/column names must match data_model whitelist

## Testing Requirements

- [ ] Unit test: schema creation and naming sanitization
- [ ] Unit test: table creation from data_model entities
- [ ] Unit test: type mapping for all 5 types
- [ ] Unit test: CRUD operations (insert, query, delete)
- [ ] Unit test: pagination limits enforced
- [ ] Unit test: SQL injection prevention (malicious table/column names)
- [ ] Unit test: data model evolution (add entity, add field)
- [ ] Unit test: schema drop with CASCADE
- [ ] Integration test: full lifecycle (create schema → create tables → insert → query → drop)

## Notes & Warnings

- Railway PG Starter plan: ~20 connections, 1GB storage — pool must be conservative
- Schema names have 63-char PG identifier limit — handle long session IDs
- Never use string interpolation for SQL values — always parameterize
- `DROP SCHEMA CASCADE` is destructive — only call on session deletion
- Dashboard stats queries should only use current model visible fields
