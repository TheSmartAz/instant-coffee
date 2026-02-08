# Phase B1: LangGraph Orchestration Skeleton

## Metadata

- **Category**: Backend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: High
- **Parallel Development**: ⚠️ Can start immediately (foundational)
- **Dependencies**:
  - **Blocked by**: None
  - **Blocks**: B2, B3, B4, B5, B6, B7, B8 (all other backend phases depend on this)

## Goal

Implement the core LangGraph StateGraph orchestration skeleton with all node definitions, state contracts, and conditional branching logic to replace the legacy orchestrator.

## Detailed Tasks

### Task 1: Install LangGraph and Define GraphState

**Description**: Set up LangGraph dependency and define the complete state schema

**Implementation Details**:
- [ ] Add `langgraph` to `requirements.txt`
- [ ] Create `packages/backend/app/graph/state.py` with TypedDict
- [ ] Define all state fields: session_id, user_input, assets, product_doc, pages, data_model, style_tokens, component_registry, page_schemas, aesthetic_scores, user_feedback, build_artifacts, build_status, error, retry_count

**Files to create**:
- `packages/backend/app/graph/__init__.py`
- `packages/backend/app/graph/state.py`

**Acceptance Criteria**:
- [ ] `GraphState` TypedDict includes all fields from spec section 6.1
- [ ] State types are properly typed with Optional/List
- [ ] Type imports work correctly

---

### Task 2: Create Node Base Classes and Contracts

**Description**: Define base node interface and individual node contracts

**Implementation Details**:
- [ ] Create `packages/backend/app/graph/nodes/__init__.py`
- [ ] Define node input/output contracts based on spec section 6.2
- [ ] Create brief_node, style_extractor_node, component_registry_node, generate_node, aesthetic_scorer_node, refine_node, render_node stubs

**Files to create**:
- `packages/backend/app/graph/nodes/__init__.py`
- `packages/backend/app/graph/nodes/base.py` (node interface)

**Acceptance Criteria**:
- [ ] Node contracts match spec section 6.2
- [ ] Each node has clear input/output field requirements

---

### Task 3: Implement Graph Builder with Conditional Edges

**Description**: Create the StateGraph assembly with all nodes and conditional routing

**Implementation Details**:
- [ ] Create `packages/backend/app/graph/graph.py`
- [ ] Implement `create_generation_graph()` function
- [ ] Add conditional edges for aesthetic scoring (should_score_aesthetic)
- [ ] Add conditional edges for refine loop (should_refine)
- [ ] Implement check_refine_node as passthrough

**Files to create**:
- `packages/backend/app/graph/graph.py`

**Acceptance Criteria**:
- [ ] Graph compiles without errors
- [ ] Entry point is "brief"
- [ ] Conditional routing works for aesthetic scoring skip
- [ ] Conditional routing works for refine/render loop
- [ ] Graph ends at END node

---

### Task 4: Implement Error Handling and Retry

**Description**: Add retry wrapper with max retries and graceful error handling

**Implementation Details**:
- [ ] Create `packages/backend/app/graph/retry.py`
- [ ] Implement `with_retry` decorator (MAX_RETRIES = 3)
- [ ] Handle state update on retry: retry_count increment, error capture
- [ ] Transition to failed state on max retries exceeded

**Files to create**:
- `packages/backend/app/graph/retry.py`

**Acceptance Criteria**:
- [ ] Retry count increments on failure
- [ ] State preserves error message
- [ ] Max retries leads to failed build_status

---

### Task 5: Integrate with Existing Chat API

**Description**: Update chat.py to use LangGraph when feature flag enabled

**Implementation Details**:
- [ ] Update `packages/backend/app/api/chat.py`
- [ ] Add FeatureFlag check for USE_LANGGRAPH
- [ ] Fallback to legacy orchestrator when flag is false
- [ ] Wire LangGraph execution into chat flow

**Files to modify**:
- `packages/backend/app/api/chat.py`

**Acceptance Criteria**:
- [ ] Feature flag controls execution path
- [ ] Legacy orchestrator works when USE_LANGGRAPH=false
- [ ] LangGraph runs when USE_LANGGRAPH=true
- [ ] SSE events emit correctly from both paths

## Technical Specifications

### GraphState Definition

```python
from typing import TypedDict, Optional, List
from langgraph.graph import StateGraph

class GraphState(TypedDict):
    # 输入
    session_id: str
    user_input: str
    assets: List[dict]

    # Brief 输出
    product_doc: Optional[dict]
    pages: List[dict]
    data_model: Optional[dict]

    # Style 输出
    style_tokens: Optional[dict]

    # Component Registry 输出
    component_registry: Optional[dict]

    # Generate 输出
    page_schemas: List[dict]

    # Aesthetic Scorer 输出
    aesthetic_enabled: bool
    aesthetic_scores: Optional[dict]
    aesthetic_suggestions: List[dict]

    # Refine 输入/输出
    user_feedback: Optional[str]

    # Render 输出
    build_artifacts: Optional[dict]
    build_status: str  # pending / building / success / failed

    # 错误处理
    error: Optional[str]
    retry_count: int
```

### Node Contracts

| Node | Input Fields | Output Fields |
|------|--------------|---------------|
| **Brief** | user_input, assets | product_doc, pages, data_model |
| **StyleExtractor** | assets (style_refs) | style_tokens |
| **ComponentRegistry** | product_doc, style_tokens, pages | component_registry |
| **Generate** | component_registry, pages, data_model | page_schemas |
| **AestheticScorer** | page_schemas, style_tokens | aesthetic_scores, aesthetic_suggestions |
| **Refine** | page_schemas, user_feedback, aesthetic_suggestions | page_schemas (updated) |
| **Render** | page_schemas, component_registry | build_artifacts, build_status |

### Conditional Functions

```python
def should_score_aesthetic(state: GraphState) -> str:
    """判断是否需要执行审美评分"""
    if not state.get("aesthetic_enabled", False):
        return "skip"
    product_type = state.get("product_doc", {}).get("product_type", "")
    if product_type in ("landing", "card", "invitation"):
        return "aesthetic"
    return "skip"

def should_refine(state: GraphState) -> str:
    if state.get("user_feedback"):
        return "refine"
    return "render"
```

## Testing Requirements

- [ ] Unit test: GraphState type checking
- [ ] Unit test: Node contract validation
- [ ] Unit test: Conditional edge routing
- [ ] Integration test: Full graph compilation
- [ ] Integration test: Error handling and retry flow

## Notes & Warnings

- **Critical Path**: This phase blocks all other backend phases
- Ensure backward compatibility with legacy orchestrator via Feature Flag
- LangGraph version compatibility: use latest stable (0.2.x)
- State must be JSON-serializable for SSE event emission
