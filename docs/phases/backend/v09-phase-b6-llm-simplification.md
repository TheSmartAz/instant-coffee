# Phase B6: LLM Layer Simplification

## Metadata

- **Category**: Backend
- **Priority**: P1 (Important)
- **Estimated Complexity**: Medium
- **Parallel Development**: ✅ Can develop in parallel (no dependencies)
- **Dependencies**:
  - **Blocked by**: None
  - **Blocks**: None (but should land before v09-B7 cleanup)

## Goal

Remove `langsmith` dependency, add `chat_with_tools()` convenience method, and simplify model routing from 30+ pool entries to 3 tiers (`FAST`, `STANDARD`, `POWERFUL`).

## Detailed Tasks

### Task 1: Remove langsmith from OpenAI Client

**Description**: Strip langsmith tracing decorators and imports.

**Implementation Details**:
- [ ] Remove `from langsmith import traceable` and all `@traceable` decorators from `openai_client.py`
- [ ] Remove langsmith imports from `app/llm/__init__.py`
- [ ] Remove `langsmith>=0.1` from `requirements.txt`

**Files to modify/create**:
- `packages/backend/app/llm/openai_client.py`
- `packages/backend/app/llm/__init__.py`
- `packages/backend/requirements.txt`

---

### Task 2: Add chat_with_tools() Method

**Description**: Convenience method that handles tool call parsing.

**Implementation Details**:
- [ ] Add to `OpenAIClient`:
  ```python
  async def chat_with_tools(self, messages, tools, model, max_tokens=4096)
      -> tuple[str, list[dict]]
  ```
- [ ] Parses response into `(text_content, tool_calls)` tuple
- [ ] Keep existing `chat_completion()` and `chat_completion_stream()` unchanged

**Files to modify/create**:
- `packages/backend/app/llm/openai_client.py`

---

### Task 3: Simplify Model Pool to 3 Tiers

**Description**: Replace complex per-role, per-product-type pools with 3 config-driven tiers.

**Implementation Details**:
- [ ] Define 3 tiers: `FAST` (classifier/compactor), `STANDARD` (generation/editing), `POWERFUL` (complex reasoning)
- [ ] Config-driven: `MODEL_FAST`, `MODEL_STANDARD`, `MODEL_POWERFUL` env vars
- [ ] Defaults: `gpt-4.1-mini`, `gpt-4.1`, `o3-mini`
- [ ] Cleaner fallback: primary → secondary → error (remove complex failure tracking with TTL)
- [ ] Keep `run_with_fallback()` method signature for backward compatibility

**Files to modify/create**:
- `packages/backend/app/llm/model_pool.py`

**Acceptance Criteria**:
- [ ] No langsmith imports remain in `app/llm/`
- [ ] `chat_with_tools()` correctly parses tool calls from response
- [ ] Model pool works with 3-tier config
- [ ] Existing `chat_completion()` and `chat_completion_stream()` unchanged

## Technical Specifications

### 3-Tier Model Routing

| Tier | Role | Use Case | Default | Env Var |
|------|------|----------|---------|---------|
| `FAST` | Classifier, compactor, validator | Quick decisions, AU2 compression | `gpt-4.1-mini` | `MODEL_FAST` |
| `STANDARD` | Generation, editing | Page HTML generation and editing | `gpt-4.1` | `MODEL_STANDARD` |
| `POWERFUL` | Complex reasoning (fallback) | Multi-page planning, difficult edits | `o3-mini` | `MODEL_POWERFUL` |

## Testing Requirements

- [ ] Verify no langsmith imports remain
- [ ] Test `chat_with_tools()` with mocked responses
- [ ] Test 3-tier model selection

## Notes & Warnings

- This phase can be developed fully in parallel with all other phases
- Keep `run_with_fallback()` signature for backward compat during migration
