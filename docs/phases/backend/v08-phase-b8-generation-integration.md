# Phase B8: Generation Integration with App Data

## Metadata

- **Category**: Backend
- **Priority**: P0
- **Estimated Complexity**: Medium
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: v08-D2 (App Data PG Schema)
  - **Blocks**: None

## Goal

Integrate `AppDataStore.create_tables()` into the generation flow so that when GenerationAgent produces HTML with a data_model, the corresponding PostgreSQL tables are automatically created. Also update the iframe JS runtime to write to the API instead of localStorage.

## Detailed Tasks

### Task 1: Hook create_tables into Generation Flow

**Description**: After GenerationAgent generates HTML and data_model, automatically create PG tables.

**Implementation Details**:
- [ ] In the generation pipeline (after HTML generation, after DataProtocolGenerator injects JS):
  - Extract `data_model` from generation result
  - Call `AppDataStore.create_schema(session_id)` if not exists
  - Call `AppDataStore.create_tables(session_id, data_model)`
- [ ] Handle data_model evolution: if tables already exist, run incremental migration
- [ ] Log table creation results

**Files to modify/create**:
- `packages/backend/app/graph/orchestrator.py` or relevant generation node
- `packages/backend/app/agents/generation.py`

**Acceptance Criteria**:
- [ ] Tables created automatically after generation
- [ ] Schema created if first generation for session
- [ ] Incremental migration works for subsequent generations
- [ ] Errors in table creation don't block HTML generation (graceful degradation)

---

### Task 2: Update iframe JS Runtime

**Description**: Modify the injected JS runtime to write data to the API instead of localStorage.

**Implementation Details**:
- [ ] Update `packages/backend/app/services/data_protocol.py` or `packages/backend/app/utils/product_doc.py`
- [ ] Change `data-store.js` / `data-client.js` generation:
  - Write operations → `POST /api/sessions/{id}/data/{table}`
  - Read operations → `GET /api/sessions/{id}/data/{table}`
- [ ] Keep `postMessage` for real-time notification to parent (Data Tab refresh trigger)
- [ ] Handle API errors gracefully in iframe (fallback to localStorage if API unavailable)

**Files to modify/create**:
- `packages/backend/app/services/data_protocol.py`
- `packages/backend/app/utils/product_doc.py`

**Acceptance Criteria**:
- [ ] iframe writes go to API
- [ ] iframe reads come from API
- [ ] postMessage still fires for real-time updates
- [ ] Graceful fallback on API failure

---

### Task 3: Wire data_model to state_contract

**Description**: Connect the data_model definitions with existing state_contract system.

**Implementation Details**:
- [ ] Ensure data_model entities align with state_contract definitions
- [ ] When state_contract defines entities, use them as data_model source
- [ ] Resolve any conflicts between data_model and state_contract

**Files to modify/create**:
- `packages/backend/app/services/data_protocol.py`
- `packages/backend/app/schemas/scenario.py`

**Acceptance Criteria**:
- [ ] data_model and state_contract are consistent
- [ ] No duplicate or conflicting entity definitions

## Technical Specifications

### Generation Flow Integration

```
GenerationAgent generates HTML
  → DataProtocolGenerator injects JS runtime
  → AppDataStore.create_schema(session_id)     ← NEW
  → AppDataStore.create_tables(session_id, dm) ← NEW
  → Return HTML + data_model to client
```

### iframe JS Runtime Change

```
Before:
  window.IC.cart.add(item) → localStorage.setItem(...)

After:
  window.IC.cart.add(item) → fetch('POST /api/sessions/{id}/data/CartItem', {body: item})
                            → postMessage({type: 'data_changed', table: 'CartItem'})
```

## Testing Requirements

- [ ] Unit test: create_tables called after generation
- [ ] Unit test: incremental migration on re-generation
- [ ] Unit test: generation succeeds even if table creation fails
- [ ] Unit test: iframe JS runtime generates correct API calls
- [ ] Integration test: generate → tables created → insert via API → query returns data

## Notes & Warnings

- Table creation failure should NOT block generation — log error and continue
- iframe JS runtime must include session_id in API calls (injected at generation time)
- CORS must be configured for iframe → API communication
- localStorage fallback ensures offline/error resilience
