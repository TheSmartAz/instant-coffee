# Spec v0.9: Soul Agentic Loop — LangGraph → Tool-Calling Loop Refactor

**Version**: v0.9
**Status**: Planned
**Date**: 2026-02-07
**Predecessor**: v0.8 (Run-Centric Backend Refactor + App Data Layer)

---

## 1. Motivation

### 1.1 Current State

The v0.7/v0.8 backend uses **LangGraph** to orchestrate a 10+ node generation pipeline:

```
brief → style_extract → component_registry → generate → aesthetic_score
  → refine → verify → render → refine_gate (interrupt)
```

This introduces:

- **5 LangGraph/LangChain dependencies**: `langgraph`, `langchain-mcp-adapters`, `langgraph-checkpoint-sqlite`, `langgraph-checkpoint-postgres`, `langsmith`
- **Rigid topology**: Adding/removing/reordering nodes requires graph rewiring
- **React SSG renderer**: `app/renderer/` adds npm build steps for HTML output
- **Complex model routing**: `ModelPoolManager` with per-role, per-product-type model pools and failure tracking across 30+ model configurations
- **Tight coupling**: Graph state (`GraphState` TypedDict with 20+ fields) threads through every node

### 1.2 Target State

Replace with a **kimi-cli-inspired agentic loop** where:

- The LLM autonomously decides which tools to call (no hardcoded node graph)
- HTML is generated directly with a shared CSS design system (no React SSG build)
- Model routing is simplified to 3 tiers: `FAST`, `STANDARD`, `POWERFUL`
- Context management uses a three-layer memory system (short/medium/long-term)
- The entire orchestration is a single `while True` loop with tool calls

### 1.3 Benefits

| Dimension | LangGraph (current) | Soul Loop (target) |
|-----------|--------------------|--------------------|
| Dependencies | 5 LangGraph/LangChain packages | 0 new dependencies |
| Node count | 10+ hardcoded nodes | 9 tools, LLM decides order |
| Output format | React SSG → npm build → HTML | Direct HTML + shared CSS |
| Model config | 30+ pool entries | 3 tiers |
| State management | 20+ field TypedDict | 3-layer context |
| Adding capability | Rewire graph topology | Register new tool |

### 1.4 References

- **easy-coding-agents**: Three-layer memory (AU2 compression), task-driven autonomous loop — see `docs/code-generation-agents-analysis.md`
- **nanocode**: Minimal agentic loop pattern (250 lines, zero dependencies)
- **kimi-cli**: Tool-calling loop with context compaction

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                   API Layer                          │
│  POST /api/chat  →  SoulOrchestrator                │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│              Soul (Agentic Loop)                     │
│                                                      │
│  while True:                                         │
│    response = llm.chat(system + context + history)   │
│    if no tool_calls: break                           │
│    for tc in tool_calls:                             │
│      if tc.name == "ask_user":                       │
│        yield waiting_input(tc.questions)             │
│        # loop pauses until user responds             │
│        answer = await user_response()                │
│        history.append(answer)                        │
│        continue                                      │
│      result = tool_registry.execute(tc)              │
│      history.append(result)                          │
│    context.maybe_compact()                           │
└──────────┬───────────────────────┬──────────────────┘
           │                       │
┌──────────▼──────┐  ┌────────────▼─────────────────┐
│  Tool Registry   │  │  Context Manager              │
│  (9 tools)       │  │  - Short-term (messages)       │
│                  │  │  - Medium-term (AU2 summary)  │
│  analyze_brief   │  │  - Long-term (product_doc,    │
│  create_design   │  │    design_system in DB)        │
│  generate_page   │  └────────────────────────────────┘
│  edit_page       │
│  read_page       │  ┌────────────────────────────────┐
│  list_pages      │  │  Product Doc (Long-term Memory) │
│  validate_html   │  │  - LLM-decided sections         │
│  extract_style   │  │  - Incremental updates          │
│  ask_user ◄──────┼──│  - Compact "project card" for   │
│  (blocking)      │  │    LLM context injection        │
└──────────────────┘  └────────────────────────────────┘
```

---

## 3. Phase Breakdown

### Phase 0: Contract Freeze & Tool System Foundation

**Priority**: P0
**Complexity**: Medium
**Depends On**: Nothing
**Blocks**: Phase 1, Phase 3

#### Step 0a: Contract Freeze

Before writing any code, explicitly document the **immutable contracts** that the new system must preserve. This prevents accidental breakage during migration.

**Contracts to freeze:**

1. **`OrchestratorResponse` fields** — all 12 fields in the dataclass must remain in the yield contract:
   - `session_id`, `phase`, `message`, `is_complete`, `preview_url`, `preview_html`, `progress`, `questions`, `action`, `product_doc_updated`, `affected_pages`, `active_page_slug`

2. **SSE event types** — existing `EventType` enum values must not be removed (new types may be added):
   - `WORKFLOW_*`, `RUN_*`, `GENERATION_*`, `INTERVIEW_*`, etc.

3. **Run state machine** — `RunService` status transitions remain source of truth:
   - `queued → running → waiting_input → completed/failed/cancelled`

4. **Chat API response shape** — `POST /api/chat` and `POST /api/chat/stream` response fields unchanged

5. **Interview payload** — `questions` field in `OrchestratorResponse` must support:
   - `type: "radio" | "checkbox" | "text"`
   - `options: list[str]` (for radio/checkbox)
   - Frontend `InterviewWidget` renders these without changes

**Output**: A checklist file or section in this spec that can be verified item-by-item during integration testing.

#### Step 0b: Tool System

#### New Files

| File | Purpose |
|------|---------|
| `app/tools/__init__.py` | Package init, re-exports |
| `app/tools/base.py` | `BaseTool` ABC, `ToolContext`, `ToolResult` |
| `app/tools/registry.py` | `ToolRegistry` class |

#### `app/tools/base.py`

- `BaseTool` abstract base class:
  - `name: str` — tool name for LLM function calling
  - `description: str` — tool description for LLM
  - `parameters_model: type[BaseModel]` — Pydantic model defining input parameters
  - `async execute(params: BaseModel, ctx: ToolContext) -> ToolResult` — abstract method
  - `get_openai_schema() -> dict` — auto-generates OpenAI function schema from the Pydantic model using `model_json_schema()`
- `ToolContext` dataclass:
  - `session_id: str`
  - `db: AsyncSession`
  - `settings: Settings`
  - `event_emitter: EventEmitter`
  - `output_dir: str`
  - `llm_client: OpenAIClient`
  - `run_id: Optional[str]`
- `ToolResult` Pydantic model:
  - `success: bool`
  - `output: str` — human-readable output for LLM context
  - `error: Optional[str]`
  - `artifacts: Optional[dict]` — structured data (e.g., `{"html": "...", "slug": "index"}`)

#### `app/tools/registry.py`

- `ToolRegistry` class:
  - `register(tool: BaseTool)` — adds tool to registry
  - `get_openai_tools() -> list[dict]` — returns all tool schemas in OpenAI function-calling format
  - `async execute(name: str, arguments: dict, ctx: ToolContext) -> ToolResult` — validates params via Pydantic, calls tool, catches exceptions, returns `ToolResult` on error (never raises)

#### Acceptance Criteria

- [ ] `BaseTool` subclass can define parameters via Pydantic model
- [ ] `get_openai_schema()` produces valid OpenAI function schema
- [ ] `ToolRegistry.execute()` validates input, returns `ToolResult` on success or error
- [ ] No new external dependencies required

---

### Phase 1: Core Tools

**Priority**: P0
**Complexity**: High
**Depends On**: Phase 0
**Blocks**: Phase 3

Each tool wraps existing business logic into the new `BaseTool` interface.

#### New Files

| File | Tool Name | Reuses From | Purpose |
|------|-----------|-------------|---------|
| `app/tools/brief.py` | `analyze_brief` | `app/services/scenario_detector.py`, `app/schemas/scenario.py` | Detect product type, scenario, default data model |
| `app/tools/design_system.py` | `create_design_system` | New (LLM-generated) | Generate shared CSS design system |
| `app/tools/generate_page.py` | `generate_page` | `app/agents/generation.py` (prompt logic) | Generate standalone HTML page |
| `app/tools/edit_page.py` | `edit_page` | `app/agents/refinement.py` (prompt logic) | Edit existing page HTML |
| `app/tools/read_page.py` | `read_page` | `app/services/file_tree.py` | Read current HTML of a page |
| `app/tools/list_pages.py` | `list_pages` | `app/services/file_tree.py` | List all pages in session |
| `app/tools/validate.py` | `validate_html` | `app/utils/html.py` | Validate HTML for mobile compliance |
| `app/tools/style_extract.py` | `extract_style` | `app/services/style_extractor.py` | Extract style tokens from images |
| `app/tools/ask_user.py` | `ask_user` | New (blocking tool) | Ask user structured questions; loop pauses until response |

#### Tool Details

**`analyze_brief`** — Pydantic params: `{ user_request: str, conversation_summary: Optional[str] }`
- Calls `ScenarioDetector.detect()` to identify product type and scenario
- Returns product type, scenario classification, suggested page list, default data model
- Reuses existing `app/services/scenario_detector.py` and `app/schemas/scenario.py`

**`create_design_system`** — Pydantic params: `{ product_type: str, style_tokens: Optional[dict], brand_colors: Optional[list[str]] }`
- Uses LLM (via `ctx.llm_client`) to generate `design-system.css`
- CSS contains: variables (colors, spacing, typography), component classes, mobile utilities
- Saves to `{output_dir}/{session_id}/design-system.css`
- Returns CSS content in `artifacts`

**`generate_page`** — Pydantic params: `{ slug: str, title: str, description: str, design_system_css: Optional[str], data_model: Optional[dict] }`
- Uses LLM to generate standalone HTML page
- HTML includes `<link rel="stylesheet" href="design-system.css">`, page-specific `<style>`, page-specific `<script>`
- Mobile-first: viewport meta, max-width 430px, hidden scrollbar, 44px touch targets
- Saves to `{output_dir}/{session_id}/pages/{slug}.html`
- Reuses prompt logic from `app/agents/generation.py` and `app/agents/prompts.py`
- Creates page version record via existing `PageVersionService`

**`edit_page`** — Pydantic params: `{ slug: str, edit_instructions: str, current_html: Optional[str] }`
- Uses LLM to apply targeted edits to existing page HTML
- If `current_html` not provided, reads from disk
- Reuses prompt logic from `app/agents/refinement.py`
- Creates new page version record

**`read_page`** — Pydantic params: `{ slug: str }`
- Reads HTML content from `{output_dir}/{session_id}/pages/{slug}.html`
- Returns HTML string in output

**`list_pages`** — Pydantic params: `{}` (no params)
- Lists all `.html` files in `{output_dir}/{session_id}/pages/`
- Returns list of `{ slug, title, size_bytes, modified_at }`

**`validate_html`** — Pydantic params: `{ slug: str, html: Optional[str] }`
- Runs mobile compliance checks from `app/utils/html.py`
- Checks: viewport meta, max-width constraint, touch target sizes, scrollbar hiding, font sizes
- Returns structured validation report

**`extract_style`** — Pydantic params: `{ image_url: str }`
- Extracts style tokens (colors, typography, spacing) from reference image
- Reuses `app/services/style_extractor.py`
- Returns style tokens dict in `artifacts`

**`ask_user`** — Pydantic params: `{ questions: list[QuestionItem] }`
- **Blocking tool**: when the LLM calls this, the agentic loop **pauses** and yields `waiting_input` to the API layer
- The API layer sends the questions to the frontend via SSE; the frontend renders them using `InterviewWidget`
- The loop resumes only when the user submits answers (via `resume` on the run)
- `QuestionItem` schema:
  ```python
  class QuestionItem(BaseModel):
      question: str                          # The question text
      type: Literal["radio", "checkbox", "text"]  # Widget type
      options: Optional[list[str]] = None    # For radio/checkbox
      context: Optional[str] = None          # Why this question matters
  ```
- Returns user answers as structured JSON in `ToolResult.output`
- The LLM decides **when** to ask (not hardcoded): first message, mid-generation, post-generation
- Supports **adaptive depth**: vague user input → more questions; detailed input → fewer or none

#### Design System Approach

- `create_design_system` generates `design-system.css` with CSS variables, component classes, mobile utilities
- `generate_page` produces standalone HTML that `<link>`s the design system
- For preview, CSS is inlined into the HTML (reuse existing `build_global_style_css()` pattern)
- Consistency across pages comes from shared CSS + LLM having design system in context

#### HTML Generation Approach

- Each page is a single HTML file with `<link rel="stylesheet" href="design-system.css">`
- Page-specific CSS in `<style>` block, page-specific JS in `<script>` block
- Mobile-first: viewport meta, max-width 430px, hidden scrollbar, 44px touch targets
- Saved to `{output_dir}/{session_id}/pages/{slug}.html`

#### Acceptance Criteria

- [ ] All 9 tools implement `BaseTool` and register with `ToolRegistry`
- [ ] `generate_page` produces valid mobile-optimized HTML
- [ ] `edit_page` preserves unmodified sections of the page
- [ ] `validate_html` catches common mobile compliance issues
- [ ] `ask_user` pauses the loop and yields `waiting_input` to the API layer
- [ ] `ask_user` resumes correctly when user submits answers
- [ ] Tools reuse existing services where noted (no duplication)

---

### Phase 1b: Interview & Product Doc Design

**Priority**: P0
**Complexity**: High
**Depends On**: Phase 0 (tool system), Phase 1 (`ask_user` tool)
**Blocks**: Phase 2 (context layer needs Product Doc structure), Phase 3

> This section defines how the system gathers requirements from users and maintains
> a persistent Product Doc as long-term memory. Unlike the old `InterviewAgent` with
> its hardcoded 3-5 round state machine, Interview is now **emergent behavior** driven
> by the LLM calling the `ask_user` tool when it needs clarification.

#### 1b.1 Interview as Emergent Behavior

The LLM decides when to ask questions — there is no separate Interview state machine.
The system prompt instructs the LLM to:

1. **First message (adaptive depth)**:
   - Vague input ("make me a coffee shop app") → LLM calls `ask_user` with 3-5 questions covering product type, target audience, key pages, visual style
   - Detailed input ("make a Netflix clone with 5 pages, dark theme, red accent") → LLM may skip questions entirely or ask 1 clarifying question
   - The LLM judges input completeness and decides depth autonomously

2. **Anytime re-interview**:
   - During generation, if the LLM encounters ambiguity → calls `ask_user`
   - After generation, if user requests a new feature → LLM may ask clarifying questions before editing
   - User can also proactively provide vague requests ("add a favorites feature") and the LLM will prompt for details

3. **Hybrid UX**:
   - Natural chat for open-ended exploration ("what kind of app do you want?")
   - Structured widgets (radio/checkbox/text) for key decisions where users benefit from seeing options
   - The LLM chooses the format per question via the `type` field in `ask_user`

#### 1b.2 `ask_user` Blocking Behavior

When the LLM calls `ask_user`:

```
Loop step N:
  LLM response includes tool_call: ask_user({questions: [...]})
  │
  ├─ Orchestrator yields OrchestratorResponse(
  │    phase="waiting_input",
  │    questions=[{question, type, options, context}],
  │    is_complete=False
  │  )
  │
  ├─ RunService sets run status → "waiting_input"
  │
  ├─ SSE sends questions to frontend
  │
  ├─ Frontend renders InterviewWidget (existing component, no changes needed)
  │
  ├─ User submits answers
  │
  ├─ API receives resume request with answers payload
  │
  ├─ Loop resumes: answers injected as tool_result for the ask_user call
  │
  └─ LLM sees answers in context, continues with next action
```

Key properties:
- **Blocking**: loop fully pauses, no background work while waiting
- **Resumable**: answers arrive via the existing `resume` mechanism on `RunService`
- **Idempotent**: if user refreshes, pending questions are re-sent from run state
- **Cancellable**: user can cancel the run while waiting

#### 1b.3 Product Doc as Long-Term Memory

The Product Doc replaces the old `product_doc` dict with a more flexible, LLM-driven structure.

**Key design decisions:**

1. **LLM-decided sections** — not a fixed schema. Different project types get different sections:
   - A coffee shop app might have: `overview`, `pages`, `brand_style`, `menu_data`
   - A portfolio site might have: `overview`, `pages`, `projects`, `contact_info`
   - The LLM creates/updates sections as it learns about the project

2. **Incremental updates** — Product Doc is never rewritten wholesale:
   - Each `ask_user` answer or user message may trigger a partial update
   - The LLM updates only the relevant section(s)
   - Updates are stored as patches with timestamps for auditability

3. **Selective injection** — not all sections are sent to the LLM every turn:
   - The system prompt includes a compact **"project card"** (< 500 tokens): project type, page list, key constraints
   - Full sections are injected only when relevant to the current task
   - Example: editing the menu page → inject `pages.menu` + `menu_data` sections, skip `contact_info`

4. **Storage**: Product Doc lives in the existing `sessions` table (JSON column) or a dedicated `product_docs` table with per-section rows

#### 1b.4 Product Doc Structure

```python
class ProductDoc(BaseModel):
    """Flexible, LLM-managed product documentation."""
    session_id: str
    sections: dict[str, ProductDocSection]  # key = section name (LLM-decided)
    project_card: str                        # compact summary for LLM context (< 500 tokens)
    updated_at: datetime

class ProductDocSection(BaseModel):
    title: str
    content: str          # markdown or structured text
    updated_at: datetime
    updated_by: str       # "llm" or "user"
```

The `project_card` is a compressed summary regenerated after each Product Doc update:
```
Project: Netflix Clone | Type: streaming_app | Pages: 5 (index, search, player, profile, favorites)
Style: dark theme, #E50914 accent, sans-serif | Status: 3/5 pages generated
Constraints: mobile-first 430px, hidden scrollbar, 44px touch targets
```

#### 1b.5 Product Doc Update Flow

When the Product Doc changes (from interview answers or user messages):

1. LLM updates relevant section(s) via internal logic (not a separate tool — the LLM writes updates as part of its reasoning, and the orchestrator persists them)
2. Orchestrator regenerates the `project_card` summary
3. Orchestrator yields `OrchestratorResponse(product_doc_updated=True)`
4. Frontend shows an **expandable update card** in the chat:
   - Collapsed: "Product Doc updated: added brand_style section"
   - Expanded: shows the updated section content
   - Link: "View full Product Doc →" navigates to the Product Doc tab

#### 1b.6 System Prompt Guidance for Interview

The system prompt (in `app/soul/prompts.py`) includes interview guidance:

```
## Gathering Requirements

You have an `ask_user` tool for asking the user structured questions.

**First message behavior:**
- If the user's request is vague or missing key details, call `ask_user` with
  questions about: product type, target audience, key pages, visual style, data needs.
- If the user's request is already detailed, you may proceed directly or ask
  1-2 clarifying questions.
- Adapt the number and depth of questions to the information already provided.

**Ongoing behavior:**
- When you encounter ambiguity during generation or editing, call `ask_user`
  rather than guessing.
- When the user requests a new feature with insufficient detail, ask for specifics.
- Prefer structured questions (radio/checkbox) when there are clear options the
  user should choose from. Use text questions for open-ended input.

**Product Doc:**
- After gathering information, update the relevant Product Doc sections.
- The project card in your context reflects the current state of the project.
- Use the Product Doc to maintain consistency across pages and sessions.
```

#### Acceptance Criteria

- [ ] LLM calls `ask_user` on first vague message; skips or reduces questions on detailed input
- [ ] `ask_user` pauses loop, frontend renders `InterviewWidget`, answers resume the loop
- [ ] Product Doc sections are created/updated incrementally by the LLM
- [ ] `project_card` is regenerated after each Product Doc update (< 500 tokens)
- [ ] Frontend shows expandable update card when Product Doc changes
- [ ] Existing `InterviewWidget` component works without modification

---

### Phase 2: Context Management (Soul)

**Priority**: P0
**Complexity**: High
**Depends On**: Nothing (can parallel with Phase 0 and Phase 1)
**Blocks**: Phase 3

#### New Files

| File | Purpose |
|------|---------|
| `app/soul/__init__.py` | Package init |
| `app/soul/context.py` | `ConversationContext` — three-layer memory |
| `app/soul/compactor.py` | AU2 history compression |
| `app/soul/prompts.py` | System prompts for the agentic loop |

#### `app/soul/context.py` — ConversationContext

Three-layer memory dataclass:

**Long-term** (from DB, loaded once per session):
- `product_doc: ProductDoc` — flexible, LLM-managed product documentation (see Phase 1b)
- `project_card: str` — compact summary of Product Doc (< 500 tokens), always injected into context
- `design_system: str` — CSS string from `design-system.css` on disk

**Medium-term** (compressed history):
- `au2_summary: str` — 8-dimensional compressed summary of older conversation
- `page_summaries: dict[str, str]` — per-page summary (slug → description)

**Short-term** (recent conversation):
- `recent_messages: list[dict]` — last N conversation turns (user + assistant + tool results)

Key methods:
- `build_messages(task_hint: Optional[str] = None) -> list[dict]` — assembles `[system_prompt, project_card, relevant_doc_sections, au2_summary, recent_messages]` for LLM call. `task_hint` guides selective Product Doc section injection.
- `add_message(role, content, tool_calls=None, tool_call_id=None)` — appends to short-term
- `maybe_compact(llm_client) -> bool` — triggers AU2 compression when message count exceeds threshold (default: 20 messages)
- `load_from_db(session_id, db)` — loads long-term context from database
- `estimate_tokens() -> int` — rough token estimate (chars / 3)

#### `app/soul/compactor.py` — AU2 Compression

Adapted from easy-coding-agents AU2 algorithm:

- `async compress_history(messages, llm_client) -> tuple[list[dict], dict]`
- Slice strategy:
  - System messages: preserved
  - First 2 dialogue messages: preserved (conversation opening)
  - Last 4 dialogue messages: preserved (recent context)
  - Middle messages: compressed into 8-dimensional summary
- 8 dimensions: `goal`, `progress`, `decisions`, `constraints`, `style`, `pages`, `issues`, `next_steps`
- Uses FAST-tier model for compression (cheap, fast)
- Returns `(new_messages, au2_summary_dict)`

#### `app/soul/prompts.py` — System Prompts

- `build_system_prompt(session_state, tools) -> str`
- Dynamic sections based on session state:
  - **New project**: Emphasizes brief analysis, design system creation, page generation
  - **Refinement**: Emphasizes reading existing pages, targeted edits, validation
  - **Multi-page**: Includes page list and cross-page consistency guidance
- Always includes: mobile constraints, tool descriptions, generation guidelines
- Injects design system CSS (if exists) as reference context

#### Acceptance Criteria

- [ ] `ConversationContext.build_messages()` produces valid OpenAI message array
- [ ] `maybe_compact()` triggers compression when threshold exceeded
- [ ] AU2 compression preserves first 2 + last 4 messages
- [ ] System prompt adapts based on session state (new vs refinement)

---

### Phase 3: Agentic Loop Core

**Priority**: P0
**Complexity**: High
**Depends On**: Phase 0, Phase 1, Phase 2
**Blocks**: Phase 5

#### New Files

| File | Purpose |
|------|---------|
| `app/soul/loop.py` | `run_agentic_loop()` async generator |
| `app/soul/orchestrator.py` | `SoulOrchestrator` — drop-in replacement for `AgentOrchestrator` |

#### `app/soul/loop.py` — Agentic Loop

```python
async def run_agentic_loop(
    context: ConversationContext,
    registry: ToolRegistry,
    llm_client: OpenAIClient,
    tool_ctx: ToolContext,
    event_emitter: EventEmitter,
    max_steps: int = 30,
    max_consecutive_errors: int = 3,
) -> AsyncGenerator[LoopEvent, None]:
```

Core loop logic:

1. Build messages from `context.build_messages()`
2. Call `llm_client.chat_completion()` with `tools=registry.get_openai_tools()`
3. If response has no `tool_calls` → yield final text message, break
4. For each tool call:
   - Emit `TOOL_CALL` event (tool name, arguments)
   - **If `ask_user`**: yield `LoopEvent(type="waiting_input", questions=...)` and **return** — the loop suspends. When the user responds, the orchestrator calls `run_agentic_loop()` again with the answers injected as a tool result in context. The loop resumes from where it left off.
   - Otherwise: execute via `registry.execute(name, args, tool_ctx)`
   - Emit `TOOL_RESULT` event (success/error, output summary)
   - Append tool call + result to context
5. Call `context.maybe_compact()` to check if compression needed
6. Check cancellation via `RunService.is_cancelled(run_id)`
7. Increment step counter; break if `max_steps` reached
8. Break if `max_consecutive_errors` reached

Safety limits:
- **Max 30 steps** per invocation (configurable)
- **3 consecutive errors** triggers early exit with error message
- **Cancellation check** after each tool execution

Events yielded per step:
- `LoopEvent(type="step_start", step=N)`
- `LoopEvent(type="tool_call", name=..., arguments=...)`
- `LoopEvent(type="tool_result", name=..., result=...)`
- `LoopEvent(type="waiting_input", questions=...)` — loop suspends, waiting for user
- `LoopEvent(type="text", content=...)` — assistant text output
- `LoopEvent(type="step_end", step=N)`
- `LoopEvent(type="complete")` or `LoopEvent(type="error", error=...)`

#### `app/soul/orchestrator.py` — SoulOrchestrator

Must implement the same interface as the existing `AgentOrchestrator` so it can be swapped in via feature flag.

```python
class SoulOrchestrator:
    async def stream_responses(
        self,
        session_id: str,
        user_message: str,
        output_dir: str,
        history: list[dict],
        trigger_interview: bool = False,
        generate_now: bool = False,
        style_reference: Optional[dict] = None,
        target_pages: Optional[list[str]] = None,
        resume: Optional[dict] = None,
    ) -> AsyncGenerator[OrchestratorResponse, None]:
```

Responsibilities:
1. Build `ToolContext` from session state
2. Load `ConversationContext` from DB (product_doc, design_system, history)
3. Register all tools into `ToolRegistry`
4. Select system prompt based on session state (new project vs refinement)
5. Run `run_agentic_loop()` and translate `LoopEvent`s into `OrchestratorResponse` yields
6. Manage run lifecycle (create/start/complete/fail) via `RunService`

**Key interface contract** — must yield `OrchestratorResponse`:

```python
@dataclass
class OrchestratorResponse:
    session_id: str
    phase: str          # "soul_loop", "tool_call", "complete", "error"
    message: str
    is_complete: bool
    preview_url: Optional[str] = None
    preview_html: Optional[str] = None
    progress: Optional[int] = None
    questions: Optional[list[dict]] = None
    action: Optional[str] = None
    product_doc_updated: Optional[bool] = None
    affected_pages: Optional[list[str]] = None
    active_page_slug: Optional[str] = None
```

#### Acceptance Criteria

- [ ] Agentic loop terminates on: no tool calls, max steps, max errors, or cancellation
- [ ] `SoulOrchestrator.stream_responses()` yields `OrchestratorResponse` objects
- [ ] Events stream correctly to frontend via existing SSE infrastructure
- [ ] Run lifecycle (create/start/complete/fail) is managed correctly
- [ ] Retry with exponential backoff for transient LLM errors

---

### Phase 4: LLM Layer Simplification

**Priority**: P1
**Complexity**: Medium
**Depends On**: Nothing (can parallel with Phase 0–3)
**Blocks**: Nothing (but should land before Phase 6 cleanup)

#### Modified Files

| File | Changes |
|------|---------|
| `app/llm/openai_client.py` | Remove `langsmith` `@traceable` decorator; add `chat_with_tools()` convenience method |
| `app/llm/model_pool.py` | Simplify to 3 roles: `FAST`, `STANDARD`, `POWERFUL`; config-driven mapping |
| `app/llm/__init__.py` | Remove langsmith imports |
| `requirements.txt` | Remove `langsmith>=0.1` |

#### `app/llm/openai_client.py` Changes

- Remove `from langsmith import traceable` and all `@traceable` decorators
- Keep existing `chat_completion()`, `chat_completion_stream()` methods unchanged
- Add convenience method:

```python
async def chat_with_tools(
    self,
    messages: list[dict],
    tools: list[dict],
    model: str,
    max_tokens: int = 4096,
) -> tuple[str, list[dict]]:
    """Single call that returns (text_content, tool_calls)."""
```

This method handles parsing the response into text content and tool call list, simplifying the loop code.

#### `app/llm/model_pool.py` Changes

Simplify role definitions from 5+ roles with per-product-type pools to 3 tiers:

| Tier | Role | Use Case | Default Model |
|------|------|----------|---------------|
| `FAST` | Classifier, compactor, validator | Quick decisions, AU2 compression | `gpt-4.1-mini` / env override |
| `STANDARD` | Generation, editing | Page HTML generation and editing | `gpt-4.1` / env override |
| `POWERFUL` | Complex reasoning (fallback) | Multi-page planning, difficult edits | `o3-mini` / env override |

- Config-driven: `MODEL_FAST`, `MODEL_STANDARD`, `MODEL_POWERFUL` env vars
- Cleaner fallback: primary → secondary → error (remove complex failure tracking with TTL)
- Keep `run_with_fallback()` method signature for backward compatibility

#### Acceptance Criteria

- [ ] No langsmith imports remain in `app/llm/`
- [ ] `chat_with_tools()` correctly parses tool calls from response
- [ ] Model pool works with 3-tier config
- [ ] Existing `chat_completion()` and `chat_completion_stream()` unchanged

---

### Phase 5: API Integration

**Priority**: P0
**Complexity**: Medium
**Depends On**: Phase 3
**Blocks**: Phase 6

#### Modified Files

| File | Changes |
|------|---------|
| `app/api/chat.py` | Add `use_soul` branch in `_create_orchestrator()` |
| `app/config.py` | Add `use_soul_orchestrator: bool = False` setting |

#### `app/api/chat.py` Changes

- Import `SoulOrchestrator` from `app.soul.orchestrator`
- In `_create_orchestrator()`, check `settings.use_soul_orchestrator`:
  - If `True`: instantiate `SoulOrchestrator`
  - If `False`: use existing `AgentOrchestrator` (or LangGraph orchestrator)
- Feature flag: `USE_SOUL_ORCHESTRATOR=true` env var (default: `false`)
- No changes to SSE streaming, run lifecycle, or frontend contract
- `SoulOrchestrator` plugs in via same `stream_responses()` interface

#### `app/config.py` Changes

- Add `use_soul_orchestrator: bool = False` to `Settings`
- Reads from `USE_SOUL_ORCHESTRATOR` env var

#### Acceptance Criteria

- [ ] `USE_SOUL_ORCHESTRATOR=false` (default) uses existing orchestrator unchanged
- [ ] `USE_SOUL_ORCHESTRATOR=true` routes to `SoulOrchestrator`
- [ ] SSE streaming works identically with both orchestrators
- [ ] Frontend requires zero changes to work with soul orchestrator

---

### Phase 6: Cleanup — Remove LangGraph

**Priority**: P1
**Complexity**: Medium
**Depends On**: Phase 5 (verified working)
**Blocks**: Nothing

> **Gate**: Only execute this phase after manual verification that `USE_SOUL_ORCHESTRATOR=true` produces correct results end-to-end.

#### Deleted Directories

| Directory | Contents | Reason |
|-----------|----------|--------|
| `app/graph/` | `__init__.py`, `graph.py`, `state.py`, `checkpointer.py`, `mcp.py`, `orchestrator.py`, `retry.py`, `nodes/` (12 files) | LangGraph orchestration replaced by soul loop |
| `app/renderer/` | `__init__.py`, `builder.py`, `file_generator.py` | React SSG build replaced by direct HTML generation |

#### Modified Files

| File | Changes |
|------|---------|
| `requirements.txt` | Remove 5 LangGraph/LangChain dependencies |
| `app/api/chat.py` | Remove LangGraph orchestrator import and branch |
| `app/config.py` | Remove `use_langgraph`, `langgraph_checkpointer`, `langgraph_checkpoint_url`; make `use_soul_orchestrator` default `True` |

#### `requirements.txt` — Remove

```
langgraph>=1.0,<2.0
langchain-mcp-adapters>=0.2,<0.3
langgraph-checkpoint-sqlite>=3.0,<4.0
langgraph-checkpoint-postgres>=3.0,<4.0
langsmith>=0.1
```

#### `app/config.py` Changes

- Remove settings: `use_langgraph`, `langgraph_checkpointer`, `langgraph_checkpoint_url`
- Change `use_soul_orchestrator` default from `False` to `True`

#### `app/api/chat.py` Changes

- Remove `from app.graph.orchestrator import ...` import
- Remove `use_langgraph` branch in `_create_orchestrator()`
- Keep `AgentOrchestrator` as legacy fallback (optional — can remove entirely)

#### Decision: Keep or Remove Legacy Orchestrator

The existing `app/agents/orchestrator.py` (`AgentOrchestrator`) can be:
- **Kept** as a fallback for `USE_SOUL_ORCHESTRATOR=false` (safer rollback)
- **Removed** entirely if soul orchestrator is proven stable

Recommendation: Keep for one release cycle, then remove in v0.10.

#### Acceptance Criteria

- [ ] `app/graph/` directory fully deleted
- [ ] `app/renderer/` directory fully deleted
- [ ] `pip install -r requirements.txt` succeeds without LangGraph packages
- [ ] `USE_SOUL_ORCHESTRATOR=true` (now default) works correctly
- [ ] No import errors or dead references to deleted modules

---

### Phase 7: Tests

**Priority**: P0
**Complexity**: Medium
**Depends On**: Phase 3 (can write incrementally alongside earlier phases)
**Blocks**: Nothing

#### New Test Files

| File | Covers | Key Scenarios |
|------|--------|---------------|
| `tests/test_tool_registry.py` | Phase 0 | Tool registration, schema generation, execute with valid/invalid params, error handling |
| `tests/test_tools_brief.py` | Phase 1 | `analyze_brief` with mocked `ScenarioDetector` |
| `tests/test_tools_generate.py` | Phase 1 | `generate_page` with mocked LLM, file output verification |
| `tests/test_tools_edit.py` | Phase 1 | `edit_page` with mocked LLM, diff verification |
| `tests/test_tools_ask_user.py` | Phase 1b | `ask_user` blocking, resume with answers, question schema validation |
| `tests/test_soul_context.py` | Phase 2 | Context building, token estimation, compaction trigger, selective Product Doc injection |
| `tests/test_soul_compactor.py` | Phase 2 | AU2 compression with mocked LLM, slice preservation |
| `tests/test_soul_loop.py` | Phase 3 | Agentic loop with mocked LLM returning tool calls, termination conditions |
| `tests/test_soul_orchestrator.py` | Phase 3 | Full orchestrator integration, `OrchestratorResponse` contract |

#### Key Test Scenarios

**test_tool_registry.py**:
- Register a tool, verify schema output matches OpenAI format
- Execute tool with valid params → `ToolResult(success=True)`
- Execute tool with invalid params → `ToolResult(success=False, error=...)`
- Execute unknown tool → `ToolResult(success=False, error="Tool not found")`
- Pydantic validation rejects bad input types

**test_soul_loop.py**:
- Mock LLM returns text only → loop exits after 1 step
- Mock LLM returns tool call → tool executes → LLM returns text → loop exits after 2 steps
- Mock LLM returns 30+ tool calls → loop exits at max_steps
- Mock LLM returns errors → loop exits at max_consecutive_errors
- Cancellation check returns True → loop exits early
- Mock LLM calls `ask_user` → loop yields `waiting_input` and suspends
- Resume with answers → loop continues from where it left off

**test_tools_ask_user.py**:
- `ask_user` with valid questions → yields `waiting_input` event
- Question schema validation: radio requires options, text does not
- Resume with structured answers → `ToolResult` contains answers JSON
- Resume with empty answers → `ToolResult` indicates no answers provided

**test_soul_orchestrator.py**:
- New session: LLM calls `analyze_brief` → `create_design_system` → `generate_page`
- New session (vague input): LLM calls `ask_user` → yields `waiting_input` → resume → continues generation
- Refinement: LLM calls `read_page` → `edit_page`
- Product Doc updated after interview answers → `product_doc_updated=True` in response
- Verify `OrchestratorResponse` fields match expected contract
- Run lifecycle events emitted correctly

#### Acceptance Criteria

- [ ] All test files pass with `pytest tests/test_tool_registry.py tests/test_soul_*.py tests/test_tools_*.py`
- [ ] Tests use mocked LLM (no real API calls)
- [ ] Existing tests in `tests/` still pass (services, DB, events)

---

## 4. Execution Order & Dependency Graph

```
Phase 0 (Contract Freeze + Tool Foundation)
    │
    ├── Phase 1 (Core Tools)       ← can start after Phase 0
    │       │
    │   Phase 1b (Interview & Product Doc) ← after Phase 0 + 1
    │       │
    ├── Phase 2 (Context/Soul)     ← parallel with Phase 0 & 1; needs 1b for Product Doc structure
    │       │
    ├── Phase 4 (LLM Improvements) ← parallel with Phase 0–3
    │       │
    └───────┼───────────────────────┘
            │
      Phase 3 (Agentic Loop)       ← needs Phase 0 + 1 + 2
            │
      Phase 5 (API Integration)    ← needs Phase 3
            │
      Phase 6 (Cleanup)            ← needs Phase 5 verified
            │
      Phase 7 (Tests throughout, final pass here)
```

### Wave Execution Plan

| Wave | Phases | Can Parallel? |
|------|--------|---------------|
| Wave 1 | Phase 0, Phase 2 (partial), Phase 4 | Yes — all independent |
| Wave 2 | Phase 1, Phase 1b | After Phase 0; 1b after 1 |
| Wave 3 | Phase 2 (finalize with Product Doc), Phase 3 | After Phase 0 + 1 + 1b + 2 |
| Wave 4 | Phase 5 | After Phase 3 |
| Wave 5 | Phase 6 | After Phase 5 verified |
| Continuous | Phase 7 | Tests written alongside each phase |

---

## 5. Files Summary

### New Files (18)

| File | Phase |
|------|-------|
| `app/tools/__init__.py` | 0 |
| `app/tools/base.py` | 0 |
| `app/tools/registry.py` | 0 |
| `app/tools/brief.py` | 1 |
| `app/tools/design_system.py` | 1 |
| `app/tools/generate_page.py` | 1 |
| `app/tools/edit_page.py` | 1 |
| `app/tools/read_page.py` | 1 |
| `app/tools/list_pages.py` | 1 |
| `app/tools/validate.py` | 1 |
| `app/tools/style_extract.py` | 1 |
| `app/tools/ask_user.py` | 1b |
| `app/soul/__init__.py` | 2 |
| `app/soul/context.py` | 2 |
| `app/soul/compactor.py` | 2 |
| `app/soul/prompts.py` | 2 |
| `app/soul/loop.py` | 3 |
| `app/soul/orchestrator.py` | 3 |

### New Test Files (9)

| File | Phase |
|------|-------|
| `tests/test_tool_registry.py` | 0 |
| `tests/test_tools_brief.py` | 1 |
| `tests/test_tools_generate.py` | 1 |
| `tests/test_tools_edit.py` | 1 |
| `tests/test_tools_ask_user.py` | 1b |
| `tests/test_soul_context.py` | 2 |
| `tests/test_soul_compactor.py` | 2 |
| `tests/test_soul_loop.py` | 3 |
| `tests/test_soul_orchestrator.py` | 3 |

### Modified Files (5)

| File | Phase | Changes |
|------|-------|---------|
| `app/llm/openai_client.py` | 4 | Remove langsmith, add `chat_with_tools()` |
| `app/llm/model_pool.py` | 4 | Simplify to 3-tier roles |
| `app/llm/__init__.py` | 4 | Remove langsmith imports |
| `app/api/chat.py` | 5, 6 | Add soul orchestrator branch; later remove LangGraph branch |
| `app/config.py` | 5, 6 | Add `use_soul_orchestrator`; later remove LangGraph settings |
| `requirements.txt` | 4, 6 | Remove langsmith; later remove all LangGraph deps |

### Deleted Files (~20, Phase 6)

**`app/graph/`** (entire directory):
- `__init__.py`
- `graph.py`
- `state.py`
- `checkpointer.py`
- `mcp.py`
- `orchestrator.py`
- `retry.py`
- `nodes/__init__.py`
- `nodes/base.py`
- `nodes/brief.py`
- `nodes/component_registry.py`
- `nodes/generate.py`
- `nodes/refine.py`
- `nodes/refine_gate.py`
- `nodes/render.py`
- `nodes/verify.py`
- `nodes/aesthetic_scorer.py`
- `nodes/style_extractor.py`
- `nodes/mcp_setup.py`

**`app/renderer/`** (entire directory):
- `__init__.py`
- `builder.py`
- `file_generator.py`

### Kept Unchanged

- `app/events/` — EventEmitter, event types, models
- `app/services/` — all services (run, page, version, token, event_store, etc.)
- `app/db/` — database layer
- `app/schemas/` — Pydantic schemas
- `app/agents/base.py` — BaseAgent (tools may reuse)
- `app/agents/prompts.py` — prompt templates (tools may reuse)
- `app/api/sessions.py`, `settings.py`, `events.py`, `runs.py`, `data.py` — other API endpoints
- `packages/web/` — entire frontend (zero changes required)

---

## 6. Verification Plan

### 6.1 Unit Tests

```bash
cd packages/backend
pytest tests/test_tool_registry.py tests/test_tools_*.py tests/test_soul_*.py -q
```

### 6.2 Feature Flag Verification

```bash
# Enable soul orchestrator
export USE_SOUL_ORCHESTRATOR=true

# Start backend
cd packages/backend && uvicorn app.main:app --reload
```

### 6.3 Manual E2E Test

**Scenario A: Detailed input (skip interview)**
1. Send a detailed chat message ("Netflix clone, 5 pages, dark theme, red accent")
2. Verify the LLM proceeds directly to `analyze_brief` → `create_design_system` → `generate_page`
3. Verify events stream correctly to frontend via SSE
4. Verify generated HTML is valid, mobile-optimized, uses design system

**Scenario B: Vague input (triggers interview)**
1. Send a vague chat message ("make me a coffee shop app")
2. Verify the LLM calls `ask_user` with structured questions
3. Verify frontend renders `InterviewWidget` with radio/checkbox/text widgets
4. Submit answers; verify the loop resumes and proceeds to generation
5. Verify Product Doc is created/updated with interview answers

**Scenario C: Refinement**
1. Send a follow-up refinement message on an existing session
2. Verify the LLM calls `read_page` → `edit_page`
3. Verify the edited page preserves unmodified sections

**Scenario D: Mid-generation re-interview**
1. After generation, send a vague feature request ("add a favorites feature")
2. Verify the LLM calls `ask_user` to clarify before editing

### 6.4 Regression

```bash
# Existing tests must still pass
cd packages/backend
pytest tests/test_migrations.py tests/test_run_service.py tests/test_event_*.py -q
pytest tests/test_chat_*.py tests/test_file_tree_service.py -q
```

### 6.5 Dependency Check (Phase 6)

```bash
# After removing LangGraph deps
pip install -r requirements.txt
python -c "from app.main import app; print('OK')"
```

---

## 7. Risk & Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| LLM doesn't call tools in correct order | Generated pages may be incomplete | System prompt includes explicit workflow guidance; `validate_html` tool catches issues |
| AU2 compression loses critical context | LLM makes inconsistent decisions | Preserve first 2 + last 4 messages; 8-dimension summary covers key aspects |
| Soul orchestrator breaks existing frontend | User-facing regression | Feature flag (`USE_SOUL_ORCHESTRATOR`) defaults to `false`; same `OrchestratorResponse` contract |
| Removing LangGraph breaks other code paths | Import errors, dead references | Phase 6 gated on Phase 5 verification; grep for all `app.graph` imports before deletion |
| Tool execution errors cascade | Loop exits prematurely | `max_consecutive_errors` limit; `ToolResult` never raises; LLM sees error and can retry |
| LLM never calls `ask_user` on vague input | Poor generation quality, missing requirements | System prompt explicitly instructs when to ask; fallback: if no Product Doc exists after first generation, prompt LLM to gather info |
| LLM over-asks (too many `ask_user` calls) | Frustrating UX, user abandonment | System prompt limits: prefer 1 batch of 3-5 questions; avoid asking what can be inferred |
| Product Doc grows unbounded | Context window waste | `project_card` is always < 500 tokens; full sections injected selectively; compaction on section count |
| `ask_user` resume loses loop state | Loop restarts from scratch | Context (messages + tool calls) is persisted; loop rebuilds from conversation history on resume |

---

## 8. Migration Strategy

### 8.1 Rollout Phases

1. **Phase 5 complete**: `USE_SOUL_ORCHESTRATOR=false` (default). Both orchestrators available, soul behind flag.
2. **Internal testing**: `USE_SOUL_ORCHESTRATOR=true` on staging. Verify all scenarios.
3. **Phase 6 complete**: `USE_SOUL_ORCHESTRATOR=true` (default). LangGraph removed. Legacy `AgentOrchestrator` kept as fallback.
4. **v0.10**: Remove legacy `AgentOrchestrator` if soul is stable.

### 8.2 Data Compatibility

- **Sessions**: No schema changes. Soul orchestrator reads/writes same `sessions`, `messages`, `versions` tables.
- **Events**: Soul emits events via same `EventEmitter`. New event types (`soul_step_start`, `soul_tool_call`, etc.) are additive — frontend ignores unknown types gracefully.
- **Pages**: Same file layout (`{output_dir}/{session_id}/pages/{slug}.html`). Design system CSS is a new file alongside pages.
- **Runs**: Soul orchestrator uses same `RunService` for run lifecycle management.

### 8.3 Environment Variables

New env vars introduced by this spec:

| Variable | Default | Phase | Purpose |
|----------|---------|-------|---------|
| `USE_SOUL_ORCHESTRATOR` | `false` (→ `true` after Phase 6) | 5 | Feature flag for soul orchestrator |
| `MODEL_FAST` | `gpt-4.1-mini` | 4 | Fast-tier model for classifier/compactor |
| `MODEL_STANDARD` | `gpt-4.1` | 4 | Standard-tier model for generation/editing |
| `MODEL_POWERFUL` | `o3-mini` | 4 | Powerful-tier model for complex reasoning |
| `SOUL_MAX_STEPS` | `30` | 3 | Max agentic loop steps per invocation |
| `SOUL_COMPACT_THRESHOLD` | `20` | 2 | Message count before AU2 compression |

---

## 9. Parallel Development Guide

You can run **3 Claude Code instances in parallel**:

1. **Tool System Agent**: Phase 0 → Phase 1
2. **Soul Context Agent**: Phase 2 (independent)
3. **LLM Cleanup Agent**: Phase 4 (independent)

After all three complete, a single agent handles:
- Phase 3 (Agentic Loop — depends on 0 + 1 + 2)
- Phase 5 (API Integration — depends on 3)
- Phase 6 (Cleanup — depends on 5 verified)

**Critical Path**: Phase 0 → Phase 1 → Phase 3 → Phase 5 → Phase 6

---

## 10. Quick Start Commands

```bash
# Read this spec
cat docs/spec/spec-09-soul-agentic-loop.md

# Start with Phase 0 (Tool Foundation)
# Create: app/tools/__init__.py, app/tools/base.py, app/tools/registry.py

# Start with Phase 2 (Context — parallel)
# Create: app/soul/__init__.py, app/soul/context.py, app/soul/compactor.py, app/soul/prompts.py

# Start with Phase 4 (LLM — parallel)
# Modify: app/llm/openai_client.py, app/llm/model_pool.py
```

---

**Document Version**: v1.1
**Last Updated**: 2026-02-07
**Total New Files**: 18 source + 9 test = 27
**Total Deleted Files**: ~22 (Phase 6)
**Total Modified Files**: 6
**Dependencies Removed**: 5 (langgraph, langchain-mcp-adapters, langgraph-checkpoint-sqlite, langgraph-checkpoint-postgres, langsmith)
