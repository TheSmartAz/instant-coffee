# Phase B5: Orchestrator Update for ProductDoc Flow

## Metadata

- **Category**: Backend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: High
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: B1 (ProductDoc Service), B2 (Page Service), B3 (ProductDoc Agent), B4 (Sitemap Agent)
  - **Blocks**: B8

## Goal

Update the Orchestrator to route user messages through the new ProductDoc-first flow, including intent detection, Generate Now mode, and proper agent coordination.

## Detailed Tasks

### Task 1: Implement ProductDoc Status Detection

**Description**: Add logic to detect current ProductDoc state for routing.

**Implementation Details**:
- [ ] Check if session has ProductDoc
- [ ] Check ProductDoc status (draft/confirmed/outdated)
- [ ] Check if session has any Pages generated
- [ ] Return session state for routing decisions

**Files to modify/create**:
- `packages/backend/app/agents/orchestrator.py`

**Acceptance Criteria**:
- [ ] Correctly identifies missing ProductDoc
- [ ] Correctly identifies ProductDoc status
- [ ] Correctly identifies page existence

---

### Task 2: Implement Intent Detection for ProductDoc

**Description**: Add intent detection to determine if user wants to modify ProductDoc.

**Implementation Details**:
- [ ] Define keywords for ProductDoc modification intent:
  - Chinese: "需求", "目标", "加页面", "改功能", "加功能", "删除页面"
  - English: "requirements", "goals", "add page", "modify feature", "remove page"
- [ ] Implement `is_product_doc_intent(message: str) -> bool`
- [ ] Handle ambiguous cases (return False, let other agents handle)

**Files to modify/create**:
- `packages/backend/app/agents/orchestrator.py`

**Acceptance Criteria**:
- [ ] ProductDoc-related messages correctly identified
- [ ] Non-ProductDoc messages pass through
- [ ] Both Chinese and English supported

---

### Task 3: Implement Confirmation Detection

**Description**: Detect when user confirms ProductDoc to trigger generation.

**Implementation Details**:
- [ ] Define confirmation phrases:
  - Chinese: "可以", "开始", "确认", "生成", "好的"
  - English: "looks good", "okay", "confirm", "start", "generate"
- [ ] Implement `is_confirmation(message: str) -> bool`
- [ ] Consider context (only confirm if ProductDoc is draft)

**Files to modify/create**:
- `packages/backend/app/agents/orchestrator.py`

**Acceptance Criteria**:
- [ ] Confirmation phrases correctly detected
- [ ] False positives minimized
- [ ] Context-aware (only works in draft state)

---

### Task 4: Implement Page Refinement Intent Detection

**Description**: Detect when user wants to modify a specific page.

**Implementation Details**:
- [ ] Check if message contains page slug or title
- [ ] Implement `detect_target_page(message: str, pages: List[Page]) -> Page | None`
- [ ] Handle disambiguation when multiple pages could match
- [ ] Return None if no specific page detected

**Files to modify/create**:
- `packages/backend/app/agents/orchestrator.py`

**Acceptance Criteria**:
- [ ] Page names/slugs correctly identified
- [ ] Fuzzy matching for Chinese titles
- [ ] Returns None for global changes

---

### Task 5: Implement Main Route Function

**Description**: Update the main routing logic with ProductDoc flow.

**Implementation Details**:
- [ ] Implement routing priority:
  1. No ProductDoc → product_doc_generation (or generate_now)
  2. ProductDoc draft + generate_now → product_doc_confirm
  3. ProductDoc draft + confirmation → product_doc_confirm
  4. ProductDoc draft + other → product_doc_update
  5. ProductDoc change intent → product_doc_update
  6. Has pages + page refinement → refinement
  7. No pages → generation_pipeline
  8. Other → direct_reply
- [ ] Handle generate_now flag from request
- [ ] Return route name and any detected context (target_page, etc.)

**Files to modify/create**:
- `packages/backend/app/agents/orchestrator.py`

**Acceptance Criteria**:
- [ ] All routing paths work correctly
- [ ] Generate Now mode bypasses confirmation
- [ ] Proper context passed to downstream handlers

---

### Task 6: Implement ProductDoc Context Injection

**Description**: Automatically inject ProductDoc into all agent calls.

**Implementation Details**:
- [ ] Load ProductDoc at start of orchestration
- [ ] Convert ProductDoc.structured to context string
- [ ] Inject into system prompt or context for all agents
- [ ] Handle missing ProductDoc gracefully

**Files to modify/create**:
- `packages/backend/app/agents/orchestrator.py`
- `packages/backend/app/agents/base.py` (if needed)

**Acceptance Criteria**:
- [ ] All agents receive ProductDoc context
- [ ] Context format is consistent
- [ ] Missing ProductDoc doesn't crash

---

### Task 7: Implement Generation Pipeline Trigger

**Description**: After ProductDoc confirmation, trigger the full generation pipeline.

**Implementation Details**:
- [ ] After confirmation, run AutoMultiPageDecider
- [ ] Run SitemapAgent to get page structure
- [ ] Create Page records in database
- [ ] Trigger GenerationAgent for each page (via Planner/Executor)
- [ ] Handle Generate Now mode (auto-confirm and generate)

**Files to modify/create**:
- `packages/backend/app/agents/orchestrator.py`
- `packages/backend/app/api/chat.py`

**Acceptance Criteria**:
- [ ] Full pipeline triggers on confirmation
- [ ] Pages created before generation
- [ ] Generate Now completes full flow

---

## Technical Specifications

### Route Function Signature

```python
@dataclass
class RouteResult:
    route: str  # Route name
    target_page: Page | None = None  # For refinement
    generate_now: bool = False  # Generate Now mode

class Orchestrator:
    async def route(
        self,
        user_message: str,
        session: Session,
        generate_now: bool = False
    ) -> RouteResult:
        """Determine routing for user message."""
        pass
```

### Route Names and Handlers

| Route | Handler | Description |
|-------|---------|-------------|
| `product_doc_generation` | ProductDocAgent.generate | First time, create ProductDoc |
| `product_doc_generation_generate_now` | ProductDocAgent.generate + auto-confirm | Generate Now mode |
| `product_doc_confirm` | Confirm + trigger pipeline | User confirms ProductDoc |
| `product_doc_update` | ProductDocAgent.update | Modify existing ProductDoc |
| `refinement` | RefinementAgent | Modify specific page |
| `generation_pipeline` | Sitemap + Generation | Generate pages from ProductDoc |
| `direct_reply` | Direct response | Questions, feedback, etc. |

### Intent Detection Keywords

```python
PRODUCT_DOC_KEYWORDS = {
    "zh": ["需求", "目标", "功能", "页面结构", "加页面", "删页面", "改功能", "设计方向"],
    "en": ["requirements", "goals", "features", "page structure", "add page",
           "remove page", "modify feature", "design direction"]
}

CONFIRMATION_KEYWORDS = {
    "zh": ["可以", "确认", "开始", "生成", "好的", "没问题", "就这样"],
    "en": ["looks good", "okay", "confirm", "start", "generate", "proceed", "lgtm"]
}

PAGE_REFINEMENT_KEYWORDS = {
    "zh": ["修改", "调整", "改一下", "更新"],
    "en": ["change", "modify", "update", "adjust", "fix"]
}
```

### ProductDoc Context Template

```python
PRODUCT_DOC_CONTEXT = """
=== Product Document Context ===
Project: {project_name}
Description: {description}
Target Audience: {target_audience}

Goals:
{goals_list}

Design Direction:
- Style: {style}
- Colors: {color_preference}
- Tone: {tone}

Pages:
{pages_list}

Constraints:
{constraints_list}
=== End Product Document ===
"""
```

## Testing Requirements

- [ ] Unit tests for intent detection (ProductDoc, confirmation, page)
- [ ] Unit tests for route function with all scenarios
- [ ] Unit tests for ProductDoc context injection
- [ ] Integration test for full flow (message → route → agent)
- [ ] Integration test for Generate Now mode
- [ ] Test disambiguation handling

## Notes & Warnings

- **Routing Priority**: Order matters; check conditions in specified priority
- **Generate Now Race**: Ensure Generate Now doesn't partially execute on failure
- **Context Size**: ProductDoc context can be large; consider truncation for token limits
- **Disambiguation**: When page cannot be determined, return list for user to choose
- **Backward Compatibility**: Old sessions without ProductDoc should still work (create default)
