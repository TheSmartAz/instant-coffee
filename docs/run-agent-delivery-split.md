# Run Agent Delivery Split

Last updated: 2026-05-13

This branch contains several independent delivery lanes. Keep them separate when reviewing or committing.

Current status: these lanes are present in the worktree and should be reviewed as related but separable changes. This file is a review aid, not a product roadmap.

## 1. Run Coordinator Core

Files:
- `packages/backend/app/engine/run_coordinator.py`
- `packages/backend/app/api/chat.py`
- `packages/backend/app/services/run.py`
- `packages/backend/app/schemas/run.py`
- run and chat adapter tests

Purpose: durable non-LangGraph run lifecycle with implement, build, review, fix, waiting-input resume, heartbeat, stale-run handling, and active-run conflict protection.

Review focus:
- State transitions stay legal.
- Waiting input can resume without creating a second run.
- Active runs block duplicate starts unless stale timeout resolves them.

## 2. Build And Review Gate

Files:
- `packages/backend/app/services/build_runner.py`
- `packages/backend/app/services/review.py`
- build/review tests

Purpose: run the generated project build, then apply a deterministic review gate before completion.

Review focus:
- Fallback build payload generation should not hide broken primary state.
- Review issues must remain structured and actionable.

## 3. Frontend Run Observability

Files:
- `packages/web/src/components/custom/RunStatusStrip.tsx`
- `packages/web/src/components/custom/RunInspector.tsx`
- `packages/web/src/hooks/chat/*`
- `packages/web/src/types/index.ts`
- `packages/web/src/api/client.ts`
- EventFlow files

Purpose: show run/build/review/policy status in Chat and expose phase history, review summary, review issues, heartbeat, and cancellation.

Review focus:
- SSE events may carry fields at top level or inside `payload`; UI must handle both.
- The inspector should remain compact and not block chat input.

## 4. Agent Runtime Hardening

Files:
- `packages/agent/src/ic/session/__init__.py`
- `packages/agent/src/ic/soul/engine.py`
- `packages/agent/src/ic/log.py`
- `packages/agent/src/ic/tool_errors.py`
- `packages/agent/src/ic/tools/shell/*`
- agent runtime tests

Purpose: path validation, safer shell stop behavior, editor invocation, tool execution ordering,
stable tool error classification, and structured `error_kind` logging.

Review focus:
- No path traversal regression.
- Shell cancellation remains idempotent.
- Tool batching does not change required ordering.
- Tool failures keep stable `Error[kind]: ...` prefixes for timeout, cancellation, policy blocks, nonzero exits, validation, and exceptions.
- `ic.tool` logs include `error_kind` when a tool fails.

## 5. Runtime And Deployment Behavior

Files:
- `packages/backend/app/db/database.py`
- `packages/backend/app/main.py`
- `packages/backend/app/api/product_doc.py`
- `packages/backend/app/services/page_version.py`

Purpose: health-check shape, database pooling, product-doc missing behavior, and page-version retention.

Review focus:
- `/health` default no longer proves DB/disk unless `?deep=true`.
- PostgreSQL connection counts must fit deployment limits.
- Product-doc 404 behavior must match frontend expectations.

## 6. Provider And Model Config Migration

Files:
- `README.md`
- `packages/backend/app/config.py`
- `packages/backend/app/llm/model_catalog.py`
- `packages/backend/app/engine/config_bridge.py`
- `packages/backend/app/renderer/html_to_react.py`
- `packages/agent/src/ic/config.py`
- `packages/agent/src/ic/cascade.py`
- `packages/agent/src/ic/llm/provider.py`
- provider tests

Purpose: DeepSeek-oriented provider/model defaults.

Review focus:
- This is broad and should be accepted independently from run coordination.
- It changes or removes compatibility expectations for OpenAI/Anthropic-style configuration.
- Token-limit constants should be centralized to avoid drift.

## Verification Commands

Backend:

```bash
cd packages/backend
PYTHONPATH=.:../agent/src python3.11 -m pytest -q
```

Web:

```bash
cd packages/web
npm run lint
npm run build
npx playwright test
```

Agent:

```bash
cd packages/agent
.venv/bin/python -m pytest -q
```

Default fake smoke:

```bash
cd packages/backend
PYTHONPATH=.:../agent/src python3.11 -m pytest tests/e2e/test_chat_run_adapter_fake_smoke.py -q
```

Opt-in real provider smoke:

```bash
cd packages/backend
RUN_REAL_CHAT_ADAPTER_SMOKE=true CHAT_USE_RUN_ADAPTER=true REAL_CHAT_ADAPTER_SMOKE_TIMEOUT=180 PYTHONPATH=.:../agent/src:../agent/.venv/lib/python3.11/site-packages python3.11 -m pytest tests/e2e/test_real_chat_run_adapter_smoke.py -q
```

If this test times out, treat it as a real-provider integration blocker: inspect provider credentials,
base URL/model routing, and coordinator phase persistence before accepting the run-agent lane.
It runs the real provider call in a child process so the parent pytest process can terminate a stuck integration attempt.
