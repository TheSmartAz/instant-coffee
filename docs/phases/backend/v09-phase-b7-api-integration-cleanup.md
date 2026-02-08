# Phase B7: API Integration & LangGraph Cleanup

## Metadata

- **Category**: Backend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: Medium
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: v09-B5 (Agentic Loop Core)
  - **Blocks**: None

## Goal

Wire the `SoulOrchestrator` into the Chat API behind a feature flag, verify end-to-end, then remove all LangGraph code, dependencies, and configuration.

## Detailed Tasks

### Task 1: Feature Flag & API Integration

**Description**: Add `USE_SOUL_ORCHESTRATOR` feature flag and wire `SoulOrchestrator` into `chat.py`.

**Implementation Details**:
- [ ] Add `use_soul_orchestrator: bool = False` to `Settings` in `app/config.py`
- [ ] Import `SoulOrchestrator` in `app/api/chat.py`
- [ ] In `_create_orchestrator()`, branch on `settings.use_soul_orchestrator`
- [ ] No changes to SSE streaming, run lifecycle, or frontend contract

**Files to modify/create**:
- `packages/backend/app/api/chat.py`
- `packages/backend/app/config.py`

**Acceptance Criteria**:
- [ ] `USE_SOUL_ORCHESTRATOR=false` (default) uses existing orchestrator
- [ ] `USE_SOUL_ORCHESTRATOR=true` routes to `SoulOrchestrator`
- [ ] SSE streaming works identically with both orchestrators
- [ ] Frontend requires zero changes

---

### Task 2: End-to-End Verification

**Description**: Manual verification before cleanup.

**Implementation Details**:
- [ ] Scenario A: Detailed input → direct generation (no interview)
- [ ] Scenario B: Vague input → `ask_user` → interview → generation
- [ ] Scenario C: Refinement → `read_page` → `edit_page`
- [ ] Scenario D: Mid-generation re-interview
- [ ] Verify SSE events, run lifecycle, Product Doc updates

**Acceptance Criteria**:
- [ ] All 4 scenarios pass with `USE_SOUL_ORCHESTRATOR=true`

---

### Task 3: Remove LangGraph Code

**Description**: Delete LangGraph directories, dependencies, and config.

> **Gate**: Only execute after Task 2 verification passes.

**Implementation Details**:
- [ ] Delete `app/graph/` directory (~19 files)
- [ ] Delete `app/renderer/` directory (3 files)
- [ ] Remove from `requirements.txt`: `langgraph`, `langchain-mcp-adapters`, `langgraph-checkpoint-sqlite`, `langgraph-checkpoint-postgres`, `langsmith`
- [ ] Remove from `app/config.py`: `use_langgraph`, `langgraph_checkpointer`, `langgraph_checkpoint_url`
- [ ] Change `use_soul_orchestrator` default to `True`
- [ ] Remove LangGraph import/branch from `app/api/chat.py`

**Files to modify/create**:
- `packages/backend/app/graph/` (DELETE)
- `packages/backend/app/renderer/` (DELETE)
- `packages/backend/requirements.txt`
- `packages/backend/app/config.py`
- `packages/backend/app/api/chat.py`

**Acceptance Criteria**:
- [ ] `app/graph/` fully deleted
- [ ] `app/renderer/` fully deleted
- [ ] `pip install -r requirements.txt` succeeds without LangGraph
- [ ] `USE_SOUL_ORCHESTRATOR=true` (now default) works correctly
- [ ] No import errors or dead references

---

### Task 4: Regression Tests

**Implementation Details**:
- [ ] Run existing test suite: `pytest tests/test_migrations.py tests/test_run_service.py tests/test_event_*.py`
- [ ] Run chat tests: `pytest tests/test_chat_*.py tests/test_file_tree_service.py`
- [ ] Verify `python -c "from app.main import app; print('OK')"` succeeds

**Acceptance Criteria**:
- [ ] All existing tests pass
- [ ] No import errors at startup

## Technical Specifications

### Dependencies Removed

```
langgraph>=1.0,<2.0
langchain-mcp-adapters>=0.2,<0.3
langgraph-checkpoint-sqlite>=3.0,<4.0
langgraph-checkpoint-postgres>=3.0,<4.0
langsmith>=0.1
```

### Deleted Directories

| Directory | File Count | Reason |
|-----------|-----------|--------|
| `app/graph/` | ~19 files | LangGraph orchestration replaced by soul loop |
| `app/renderer/` | 3 files | React SSG replaced by direct HTML generation |

### New Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `USE_SOUL_ORCHESTRATOR` | `false` → `true` after cleanup | Feature flag |

## Notes & Warnings

- Keep `AgentOrchestrator` as legacy fallback for one release cycle (remove in v0.10)
- Run `rg -n "langgraph\|use_langgraph\|LANGGRAPH_" packages/backend` after cleanup to verify no stale references
- The cleanup task is gated on successful E2E verification — do not skip
