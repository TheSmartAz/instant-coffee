# v0.3 Spec/Impl Gap Fix List

Source docs: `docs/spec/spec-03.md`, `docs/v03-summary.md` (2026-01-31)

## High priority (blocking UI/spec claims)
- [x] **Emit token usage events + summary**
  - Add `token_usage` event type + model in backend events.
  - Emit `token_usage` per LLM call and include `token_usage` summary in `done`.
  - Files: `packages/backend/app/events/types.py`, `packages/backend/app/events/models.py`,
    `packages/backend/app/events/emitter.py`, `packages/backend/app/services/token_tracker.py`,
    `packages/backend/app/agents/base.py`, `packages/backend/app/executor/parallel.py`,
    `packages/backend/app/agents/orchestrator.py`, `packages/backend/app/api/chat.py`.
- [x] **SSE should stream tool + token events**
  - `/api/chat` SSE branch currently skips draining emitter events.
  - Files: `packages/backend/app/api/chat.py`.

## Medium priority (spec mismatch)
- [x] **Generation stream flag honored**
  - `GenerationAgent.generate(stream=True)` currently ignores `stream`.
  - Implement stream path (non-tool) and keep tool path for non-stream.
  - Files: `packages/backend/app/agents/generation.py`.
- [x] **Refinement progress events**
  - Spec shows progress events (30/80/100); currently not emitted.
  - Files: `packages/backend/app/agents/refinement.py`.
- [x] **Tool error payload shape**
  - Ensure `{success, output, error}` always present for tool errors.
  - Files: `packages/backend/app/llm/openai_client.py`, `packages/backend/app/agents/base.py`.
- [x] **Pricing fallback**
  - Spec uses default pricing when model unknown; current code returns 0 cost.
  - Files: `packages/backend/app/llm/openai_client.py`.
- [x] **Tool write size limits**
  - Spec requires max write size; not enforced in handlers.
  - Files: `packages/backend/app/llm/tool_handlers.py`,
    `packages/backend/app/agents/generation.py`, `packages/backend/app/agents/refinement.py`.

## Lower priority / larger changes
- [x] **Orchestrator flow uses Interview → Generation → Refinement**
  - Chat API currently runs Generation only.
  - Files: `packages/backend/app/agents/orchestrator.py`, `packages/backend/app/api/chat.py`.
- [ ] **Default agent_id fallback**
  - Spec expects `{agent_type}_1` if none provided.
  - Files: `packages/backend/app/agents/base.py`.

## Non-code validation
- [ ] **Performance targets & streaming behavior**
  - Verify timing targets + streaming display.
  - Requires runtime testing.
