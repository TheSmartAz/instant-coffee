# Phase B3: Interview & Ask User Tool

## Metadata

- **Category**: Backend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: High
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: v09-B1 (Tool Foundation), v09-B2 (Core Tools)
  - **Blocks**: v09-B4 (Context Management needs Product Doc structure), v09-B5 (Agentic Loop Core)

## Goal

Implement the `ask_user` blocking tool and the Product Doc long-term memory system. The `ask_user` tool replaces the old `InterviewAgent` state machine with emergent LLM-driven interview behavior.

## Detailed Tasks

### Task 1: ask_user Tool Implementation

**Description**: Create the blocking `ask_user` tool that pauses the agentic loop and sends structured questions to the frontend.

**Implementation Details**:
- [ ] Create `QuestionItem` Pydantic model with: `question: str`, `type: Literal["radio", "checkbox", "text"]`, `options: Optional[list[str]]`, `context: Optional[str]`
- [ ] Create `AskUserParams` model with: `questions: list[QuestionItem]`
- [ ] Implement `AskUserTool(BaseTool)` — on execute, returns a special `ToolResult` with `artifacts={"blocking": True, "questions": [...]}`
- [ ] The agentic loop detects this special result and yields `waiting_input` event
- [ ] On resume, user answers are injected as the tool result content

**Files to modify/create**:
- `packages/backend/app/tools/ask_user.py`

**Acceptance Criteria**:
- [ ] `ask_user` produces valid `QuestionItem` schema
- [ ] Radio/checkbox questions require `options` field
- [ ] Text questions work without `options`
- [ ] Tool result includes structured question payload for frontend

---

### Task 2: Product Doc Models

**Description**: Create the flexible, LLM-managed Product Doc data structures.

**Implementation Details**:
- [ ] Create `ProductDocSection` model: `title: str`, `content: str`, `updated_at: datetime`, `updated_by: str`
- [ ] Create `ProductDoc` model: `session_id: str`, `sections: dict[str, ProductDocSection]`, `project_card: str`, `updated_at: datetime`
- [ ] `project_card` is a compact summary (< 500 tokens) regenerated after each update
- [ ] Sections are LLM-decided (not fixed schema) — different project types get different sections

**Files to modify/create**:
- `packages/backend/app/schemas/product_doc.py`

**Acceptance Criteria**:
- [ ] `ProductDoc` serializes/deserializes to JSON for DB storage
- [ ] `project_card` field exists and can be regenerated

---

### Task 3: Product Doc Service

**Description**: Service layer for persisting and querying Product Doc sections.

**Implementation Details**:
- [ ] `get_product_doc(session_id) -> ProductDoc` — load from DB
- [ ] `update_section(session_id, section_name, content, updated_by) -> ProductDoc` — incremental update
- [ ] `regenerate_project_card(session_id, llm_client) -> str` — compress all sections into < 500 token summary
- [ ] `get_relevant_sections(session_id, task_hint) -> dict[str, ProductDocSection]` — selective injection based on task context
- [ ] Storage: JSON column in existing `sessions` table or dedicated `product_docs` table

**Files to modify/create**:
- `packages/backend/app/services/product_doc_v2.py`

**Acceptance Criteria**:
- [ ] Sections are created/updated incrementally (never rewritten wholesale)
- [ ] `project_card` regenerated after each update, stays < 500 tokens
- [ ] `get_relevant_sections()` returns subset based on task hint

---

### Task 4: Unit Tests

**Description**: Test ask_user tool and Product Doc service.

**Implementation Details**:
- [ ] Test `ask_user` with valid questions → correct schema output
- [ ] Test question validation: radio requires options, text does not
- [ ] Test resume with structured answers → `ToolResult` contains answers JSON
- [ ] Test Product Doc incremental updates
- [ ] Test project card regeneration

**Files to modify/create**:
- `packages/backend/tests/test_tools_ask_user.py`

**Acceptance Criteria**:
- [ ] All tests pass with `pytest tests/test_tools_ask_user.py`
- [ ] Tests use mocked LLM (no real API calls)

## Technical Specifications

### QuestionItem Schema

```python
class QuestionItem(BaseModel):
    question: str
    type: Literal["radio", "checkbox", "text"]
    options: Optional[list[str]] = None
    context: Optional[str] = None
```

### ProductDoc Schema

```python
class ProductDocSection(BaseModel):
    title: str
    content: str
    updated_at: datetime
    updated_by: str  # "llm" or "user"

class ProductDoc(BaseModel):
    session_id: str
    sections: dict[str, ProductDocSection]
    project_card: str  # < 500 tokens
    updated_at: datetime
```

### Project Card Example

```
Project: Netflix Clone | Type: streaming_app | Pages: 5 (index, search, player, profile, favorites)
Style: dark theme, #E50914 accent, sans-serif | Status: 3/5 pages generated
Constraints: mobile-first 430px, hidden scrollbar, 44px touch targets
```

### ask_user Blocking Flow

```
LLM calls ask_user({questions: [...]})
  → Tool returns ToolResult(artifacts={"blocking": True, "questions": [...]})
  → Loop yields LoopEvent(type="waiting_input", questions=...)
  → RunService sets status → "waiting_input"
  → SSE sends questions to frontend
  → Frontend renders InterviewWidget (no changes needed)
  → User submits answers
  → API receives resume with answers payload
  → Loop resumes with answers as tool_result
```

## Testing Requirements

- [ ] Unit tests for `AskUserTool` schema generation and execution
- [ ] Unit tests for `ProductDoc` CRUD operations
- [ ] Unit tests for `project_card` regeneration with mocked LLM

## Notes & Warnings

- The `ask_user` tool is the **only** blocking tool — all others execute synchronously within the loop
- Frontend `InterviewWidget` already supports `radio`, `checkbox`, `text` question types — no frontend changes needed
- Product Doc sections are LLM-decided, not a fixed schema. The LLM creates sections like `overview`, `pages`, `brand_style` as needed
- The `project_card` must stay under 500 tokens to avoid context bloat
