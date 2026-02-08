# Phase B6: Verify Gate

## Metadata

- **Category**: Backend
- **Priority**: P0
- **Estimated Complexity**: High
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: v08-B3 (Orchestration Run Integration)
  - **Blocks**: None

## Goal

Add a Verify Gate node to the LangGraph pipeline between `refine` and `render`. The gate runs build, structure, mobile, and security checks. Failures block render and trigger auto-retry or `waiting_input`.

## Detailed Tasks

### Task 1: Create Verify Node

**Description**: Implement the verify gate as a LangGraph node.

**Implementation Details**:
- [ ] Create `packages/backend/app/graph/nodes/verify.py`
- [ ] Implement `verify_node(state: GraphState)` function
- [ ] Run 4 check categories (see Task 2)
- [ ] On all pass: set `verify_blocked=False`, emit `verify_pass`, route to `render`
- [ ] On any fail: set `verify_blocked=True`, populate `verify_report`, emit `verify_fail`
- [ ] Write results to `state.verify_report`

**Files to modify/create**:
- `packages/backend/app/graph/nodes/verify.py`

**Acceptance Criteria**:
- [ ] Verify node executes all 4 check categories
- [ ] Pass routes to render
- [ ] Fail blocks render
- [ ] Events emitted correctly

---

### Task 2: Implement Minimum Check Set

**Description**: Implement the 4 verification checks from spec section 9.2.

**Implementation Details**:
- [ ] **Build check**: Verify React SSG build completes without fatal errors
- [ ] **Structure check**: Verify critical pages exist (at least `index`), entry node (`#app`) present
- [ ] **Mobile check**: Verify viewport meta tag, mobile shell constraints satisfied
- [ ] **Security check**: Scan for sensitive patterns (token/key/secret) in generated output
- [ ] Each check returns: `passed: bool`, `details: str`, `severity: str`

**Files to modify/create**:
- `packages/backend/app/graph/nodes/verify.py`

**Acceptance Criteria**:
- [ ] Build check catches fatal build errors
- [ ] Structure check validates index page and #app entry
- [ ] Mobile check validates viewport and mobile constraints
- [ ] Security check detects leaked secrets/tokens
- [ ] Each check independently reportable

---

### Task 3: Wire Verify into Graph Topology

**Description**: Insert verify node between refine and render in the graph.

**Implementation Details**:
- [ ] Modify `packages/backend/app/graph/graph.py`
- [ ] Change: `... → refine → render` to `... → refine → verify → render`
- [ ] Add conditional edge from verify:
  - `verify_pass` → `render`
  - `verify_fail` → auto-retry OR `waiting_input`
- [ ] Register verify node in graph builder

**Files to modify/create**:
- `packages/backend/app/graph/graph.py`

**Acceptance Criteria**:
- [ ] Verify node in correct position in graph
- [ ] Conditional routing works (pass → render, fail → retry/wait)
- [ ] Graph still compiles and runs

---

### Task 4: Implement Failure Strategy

**Description**: Handle verify failures with retry and escalation.

**Implementation Details**:
- [ ] First fail: write `verify_report`, emit `verify_fail` event
- [ ] If auto-fix enabled: retry verify once (max 1 retry)
- [ ] After retry still fails: run enters `waiting_input` (recoverable) or `failed` (unrecoverable)
- [ ] Add `verify_gate_enabled: bool = True` feature flag to config
- [ ] When disabled: skip verify, go directly to render

**Files to modify/create**:
- `packages/backend/app/graph/nodes/verify.py`
- `packages/backend/app/graph/graph.py`
- `packages/backend/app/config.py`

**Acceptance Criteria**:
- [ ] First failure triggers retry (if auto-fix enabled)
- [ ] Second failure escalates to waiting_input or failed
- [ ] Feature flag disables verify gate entirely
- [ ] Verify report available in run state for debugging

## Technical Specifications

### Graph Topology Change

```
Before: ... → generate → (aesthetic) → refine_gate → refine → render
After:  ... → generate → (aesthetic) → refine_gate → refine → verify → render
```

### Verify Report Structure

```json
{
  "checks": [
    {"name": "build", "passed": true, "details": "Build completed successfully"},
    {"name": "structure", "passed": true, "details": "index page found, #app entry present"},
    {"name": "mobile", "passed": false, "details": "Missing viewport meta tag", "severity": "error"},
    {"name": "security", "passed": true, "details": "No sensitive patterns detected"}
  ],
  "overall_passed": false,
  "retry_count": 0
}
```

### Verify Events

```json
{"type": "verify_start", "run_id": "...", "payload": {"checks": ["build","structure","mobile","security"]}}
{"type": "verify_pass", "run_id": "...", "payload": {"report": {...}}}
{"type": "verify_fail", "run_id": "...", "payload": {"report": {...}, "action": "retry|waiting_input|failed"}}
```

## Testing Requirements

- [ ] Unit test: each of the 4 checks independently
- [ ] Unit test: verify node with all-pass scenario
- [ ] Unit test: verify node with single failure
- [ ] Unit test: retry logic (first fail → retry → pass)
- [ ] Unit test: retry exhaustion (fail → retry → fail → escalate)
- [ ] Unit test: feature flag disables verify
- [ ] Integration test: full graph flow with verify pass
- [ ] Integration test: full graph flow with verify fail → waiting_input

## Notes & Warnings

- Verify gate should NOT be overly strict — false positives block valid output
- Build check requires React SSG build infrastructure from v0.7
- Security check patterns should match common leak patterns but avoid false positives
- Feature flag allows instant disable if verify causes issues in production
