# Phase B4: Context Management (Soul)

## Metadata

- **Category**: Backend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: High
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: v09-B3 (needs Product Doc structure)
  - **Blocks**: v09-B5 (Agentic Loop Core)

## Goal

Build the three-layer memory system (`ConversationContext`) and AU2 history compression that powers the agentic loop's context window management.

## Detailed Tasks

### Task 1: ConversationContext

**Description**: Three-layer memory dataclass that assembles LLM messages from long-term, medium-term, and short-term memory.

**Implementation Details**:
- [ ] Long-term: `product_doc: ProductDoc`, `project_card: str` (< 500 tokens), `design_system: str`
- [ ] Medium-term: `au2_summary: str` (8-dim compressed summary), `page_summaries: dict[str, str]`
- [ ] Short-term: `recent_messages: list[dict]` (last N turns)
- [ ] `build_messages(task_hint=None)` → assembles `[system_prompt, project_card, relevant_doc_sections, au2_summary, recent_messages]`
- [ ] `add_message(role, content, tool_calls=None, tool_call_id=None)` → appends to short-term
- [ ] `maybe_compact(llm_client)` → triggers AU2 when messages > threshold (default 20)
- [ ] `load_from_db(session_id, db)` → loads long-term context
- [ ] `estimate_tokens()` → rough estimate (chars / 3)

**Files to modify/create**:
- `packages/backend/app/soul/__init__.py`
- `packages/backend/app/soul/context.py`

**Acceptance Criteria**:
- [ ] `build_messages()` produces valid OpenAI message array
- [ ] `task_hint` guides selective Product Doc section injection
- [ ] `maybe_compact()` triggers compression when threshold exceeded

---

### Task 2: AU2 Compactor

**Description**: History compression algorithm adapted from easy-coding-agents.

**Implementation Details**:
- [ ] `async compress_history(messages, llm_client) -> tuple[list[dict], dict]`
- [ ] Slice strategy: preserve system messages, first 2 dialogue messages, last 4 dialogue messages
- [ ] Compress middle messages into 8 dimensions: `goal`, `progress`, `decisions`, `constraints`, `style`, `pages`, `issues`, `next_steps`
- [ ] Use FAST-tier model for compression
- [ ] Return `(new_messages, au2_summary_dict)`

**Files to modify/create**:
- `packages/backend/app/soul/compactor.py`

**Acceptance Criteria**:
- [ ] AU2 compression preserves first 2 + last 4 messages
- [ ] 8-dimension summary covers all key aspects
- [ ] Uses FAST-tier model (cheap, fast)

---

### Task 3: System Prompts

**Description**: Dynamic system prompt builder for the agentic loop.

**Implementation Details**:
- [ ] `build_system_prompt(session_state, tools) -> str`
- [ ] Dynamic sections: new project vs refinement vs multi-page
- [ ] Always includes: mobile constraints, tool descriptions, generation guidelines
- [ ] Includes interview guidance for `ask_user` tool usage
- [ ] Injects design system CSS as reference context

**Files to modify/create**:
- `packages/backend/app/soul/prompts.py`

**Acceptance Criteria**:
- [ ] System prompt adapts based on session state
- [ ] Interview guidance included for `ask_user` behavior

---

### Task 4: Unit Tests

**Files to modify/create**:
- `packages/backend/tests/test_soul_context.py`
- `packages/backend/tests/test_soul_compactor.py`

**Acceptance Criteria**:
- [ ] Context building, token estimation, compaction trigger tested
- [ ] AU2 slice preservation verified
- [ ] Selective Product Doc injection tested

## Technical Specifications

### Three-Layer Memory

| Layer | Source | Lifetime | Injection |
|-------|--------|----------|-----------|
| Long-term | DB (product_doc, design_system) | Session | Always (project_card); selective (full sections) |
| Medium-term | AU2 compression | Grows with conversation | Always injected |
| Short-term | Recent messages | Last N turns | Always injected |

### AU2 8 Dimensions

`goal`, `progress`, `decisions`, `constraints`, `style`, `pages`, `issues`, `next_steps`

## Notes & Warnings

- `build_messages()` with `task_hint` enables selective injection — editing menu page only injects `pages.menu` + `menu_data` sections
- AU2 compression uses FAST-tier model to keep costs low
- The compaction threshold (default 20 messages) is configurable via `SOUL_COMPACT_THRESHOLD` env var
