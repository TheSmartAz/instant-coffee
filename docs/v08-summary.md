# Version 0.8 Implementation Summary

## Overview

**Version**: v0.8 - Run-Centric Backend Refactor + 可恢复执行 + 事件模型升级 + 工具策略钩子 + Verify Gate + App Data Layer
**Status**: Complete
**Start Date**: 2026-02-06
**Completion Date**: 2026-02-06

**Complexity normalization**:
- Canonical `complexity`: `simple | medium | complex`
- Manifest/legacy values map as: `checklist → simple`, `standard → medium`, `extended → complex`

## Implementation Progress

### Database Phases

| Phase ID | Name | Status | Completed Date |
|----------|------|--------|----------------|
| v08-D1 | Run Data Layer | ✅ Complete | 2026-02-06 |
| v08-D2 | App Data PG Schema | ✅ Complete | 2026-02-06 |

### Backend Phases

| Phase ID | Name | Status | Completed Date |
|----------|------|--------|----------------|
| v08-B1 | Run Service + State Machine + CRUD API | ✅ Complete | 2026-02-06 |
| v08-B2 | Event Layer Upgrade | ✅ Complete | 2026-02-06 |
| v08-B3 | Orchestration Run Integration | ✅ Complete | 2026-02-06 |
| v08-B4 | Chat Compatibility Adapter | ✅ Complete | 2026-02-06 |
| v08-B5 | Tool Policy Hooks | ✅ Complete | 2026-02-06 |
| v08-B6 | Verify Gate | ✅ Complete | 2026-02-06 |
| v08-B7 | App Data API | ✅ Complete | 2026-02-06 |
| v08-B8 | Generation Integration with App Data | ✅ Complete | 2026-02-06 |

### Frontend Phases

| Phase ID | Name | Status | Completed Date |
|----------|------|--------|----------------|
| v08-F1 | Data Tab Frontend Overhaul | ✅ Complete | 2026-02-06 |

---

## Phase Details

### v08-D1: Run Data Layer

**Status**: ✅ Complete
**Implementation Date**: 2026-02-06

**Files Modified/Created (Actual)**:
- `packages/backend/app/db/models.py`
- `packages/backend/app/db/migrations.py`
- `packages/backend/app/db/__init__.py`
- `packages/backend/app/schemas/run.py`
- `packages/backend/app/schemas/__init__.py`
- `packages/backend/tests/test_migrations.py`
- `packages/backend/tests/test_run_data_layer.py`

**Features Implemented**:
- Add `session_runs` data model and session relationship.
- Extend `session_events` with `run_id` and `event_id` (nullable for history compatibility).
- Add v0.8 migrations and indexes for run + run-scoped event query.
- Define Run API schemas (`RunCreate`, `RunResponse`, `RunResumeRequest`, `RunStatus`).
- Add model-level validation for `trigger_source` and `status` allowed values.

**Acceptance Criteria**:
- [x] `session_runs` table fields match spec (status, checkpoint, error, metrics, timestamps).
- [x] `session_events` supports nullable `run_id/event_id` without breaking historical rows.
- [x] Migration remains idempotent and safe for existing DB.
- [x] Run schemas align with spec section 8 API contracts.

**Validation Completed**:
- Migration tests for table creation, column extension, and idempotency.
- SessionRun model CRUD + enum/schema validation tests.

**Plan vs Implementation Notes**:
- Spec note says `checkpoint_thread` defaults to `session_id:run_id`; this is intentionally deferred to RunService/orchestration phases (`v08-B1`/`v08-B3`) because the default depends on runtime `run_id` context rather than static DB defaults.

### v08-D2: App Data PG Schema

**Status**: ✅ Complete
**Implementation Date**: 2026-02-06

**Files Modified/Created (Actual)**:
- `packages/backend/app/services/app_data_store.py`
- `packages/backend/app/config.py`
- `packages/backend/app/main.py`
- `packages/backend/requirements.txt`
- `packages/backend/tests/test_app_data_store.py`

**Features Implemented**:
- Implement schema-per-session `AppDataStore` with schema naming sanitization.
- Create table generation from `data_model` (`TYPE_MAP` + auto columns).
- Provide secured CRUD helpers with whitelist validation and SQL parameterization.
- Support incremental model evolution (add entity/field, preserve old data).
- Add asyncpg pool lifecycle configuration for Railway/PostgreSQL.
- Add schema/table introspection helper for API consumption (`list_tables`).

**Acceptance Criteria**:
- [x] Dynamic schema/table creation works from `data_model`.
- [x] CRUD operations support pagination and stats with injection-safe query paths.
- [x] Data model evolution preserves existing data.
- [x] Startup/shutdown manage PG pool cleanly.

**Validation Completed**:
- Unit tests added and passed for schema naming/creation, type mapping, CRUD, pagination cap, injection prevention, evolution, and schema drop.
- Targeted run: `cd packages/backend && python -m pytest tests/test_app_data_store.py -q` → `11 passed`.

**Plan vs Implementation Notes**:
- Spec text mentions identifier handling via `quote_ident()`; implementation uses strict identifier regex validation + safe double-quote identifier wrapping to enforce equivalent safety without DB-side `quote_ident()` calls.
- CRUD intentionally requires data-model whitelist initialization (via `create_tables`) before access; this is stricter than implicit fallback and prevents non-model table/column access.
- Pool sizing enforces a hard upper bound of 15 connections even if env is higher, aligning with Railway headroom guidance.

### v08-B1: Run Service + State Machine + CRUD API

**Status**: ✅ Complete
**Implementation Date**: 2026-02-06

**Files Modified/Created (Actual)**:
- `packages/backend/app/services/run.py`
- `packages/backend/app/api/runs.py`
- `packages/backend/app/services/event_store.py`
- `packages/backend/app/config.py`
- `packages/backend/app/main.py`
- `packages/backend/app/api/__init__.py`
- `packages/backend/tests/test_run_service.py`
- `packages/backend/tests/test_runs_api.py`

**Features Implemented**:
- Implement `RunService` with explicit state machine and transition validation.
- Provide run lifecycle APIs (`create/get/resume/cancel`).
- Add run event endpoint supporting SSE and JSON polling (`since_seq`/`limit`).
- Add feature flags (`run_api_enabled`, `chat_use_run_adapter`) for rollout control.
- Add `Idempotency-Key` support (24h in-memory cache) for create and resume endpoints.
- Add `EventStoreService.get_events_by_run()` for run-dimension filtering.

**Acceptance Criteria**:
- [x] All 6 run states supported (`queued/running/waiting_input/completed/failed/cancelled`).
- [x] Invalid transitions rejected with proper error code.
- [x] Cancel behavior idempotent for both active and terminal states.
- [x] Run events endpoint supports content negotiation and ordered pagination.

**Validation Completed**:
- Service state-machine tests: `test_run_service.py`.
- API tests for create/get/resume/cancel/idempotency/events/filtering/feature-flag: `test_runs_api.py`.
- Targeted run: `cd packages/backend && PYTHONPATH=. pytest tests/test_migrations.py tests/test_run_data_layer.py tests/test_run_service.py tests/test_runs_api.py -q` → `18 passed`.

**Plan vs Implementation Notes**:
- Idempotency storage is implemented as in-process memory cache (TTL 24h). This satisfies behavior for current single-process dev/test setup; distributed persistent idempotency store is deferred for later infra hardening.
- `GET /api/runs/{run_id}/events` uses run terminal state to end SSE stream loop; if no terminal transition event is emitted yet, stream still closes once status reaches terminal in DB.

### v08-B2: Event Layer Upgrade

**Status**: ✅ Complete
**Implementation Date**: 2026-02-06

**Files Modified/Created (Actual)**:
- `packages/backend/app/events/types.py`
- `packages/backend/app/events/models.py`
- `packages/backend/app/events/emitter.py`
- `packages/backend/app/services/event_store.py`
- `packages/backend/app/api/events.py`
- `packages/backend/tests/test_event_layer_upgrade_v08.py`

**Features Implemented**:
- Register 12 new event types across run lifecycle, verify gate, and tool policy.
- Enforce unified event envelope (`payload` object) and run-scope validation in event store path.
- Extend emitter for `run_id` + `event_id` propagation and auto-generation.
- Add run-dimension event query while preserving session-level aggregate query.

**Acceptance Criteria**:
- [x] New event types available without breaking legacy types.
- [x] Run-scoped events without `run_id` rejected (at store/record path).
- [x] `seq` semantics remain session-level monotonic.
- [x] Run query returns `ORDER BY seq ASC` with `since_seq` filter.

**Validation Completed**:
- Added `test_event_layer_upgrade_v08.py` covering new event types, run-id enforcement, payload object enforcement, emitter propagation, run-query filtering, and `since_seq`.
- Targeted run: `cd packages/backend && PYTHONPATH=. pytest tests/test_migrations.py tests/test_run_data_layer.py tests/test_run_service.py tests/test_runs_api.py tests/test_event_layer_upgrade_v08.py tests/test_event_protocol.py tests/test_events.py -q` → `31 passed`.

**Plan vs Implementation Notes**:
- Spec wording says run-scoped `run_id` should be rejected in model layer; implementation enforces this in `EventStoreService.store_event/record_event` so emitter context can still auto-populate missing `run_id` before persistence.
- `api/events.py` session endpoint behavior remains unchanged; run-level filtered endpoint is provided by B1 `api/runs.py` and now backed by the B2-upgraded store semantics.

### v08-B3: Orchestration Run Integration

**Status**: ✅ Complete
**Implementation Date**: 2026-02-06

**Files Modified/Created (Actual)**:
- `packages/backend/app/graph/state.py`
- `packages/backend/app/graph/orchestrator.py`
- `packages/backend/app/graph/graph.py`
- `packages/backend/app/services/run.py`
- `packages/backend/app/api/chat.py`
- `packages/backend/tests/test_langgraph_skeleton.py`
- `packages/backend/tests/test_orchestration_run_integration_v08.py`

**Features Implemented**:
- Extend GraphState with `run_status`, `verify_report`, `verify_blocked`, `current_node`.
- Wrap graph execution in Run lifecycle (`run_created/start/completed/failed/waiting_input`).
- Integrate resume through `Command(resume=...)` and shared checkpoint thread.
- Add cooperative cancellation behavior with run status synchronization.
- Ensure chat-side resume payload resolves to concrete `run_id` and is bound to session waiting run.
- Add run-scoped checkpoint isolation via `thread_id = checkpoint_thread` (`session_id:run_id`).

**Acceptance Criteria**:
- [x] Every graph execution maps to a persisted run record.
- [x] Interrupt/resume maintains same `run_id` and checkpoint continuity.
- [x] Cancellation moves run to terminal `cancelled` state and stops new graph progression at cooperative checkpoints.
- [x] Concurrent runs isolate checkpoints by `session_id:run_id`.

**Validation Completed**:
- Added B3 integration coverage in `test_orchestration_run_integration_v08.py` (run lifecycle, interrupt→resume continuity, cancel idempotency, checkpoint isolation).
- Updated graph state coverage in `test_langgraph_skeleton.py` for new run fields.
- Targeted run: `cd packages/backend && PYTHONPATH=. pytest -q tests/test_langgraph_skeleton.py tests/test_orchestration_run_integration_v08.py tests/test_run_service.py tests/test_runs_api.py` → `19 passed`.

**Plan vs Implementation Notes**:
- Plan expected graph completion to transition run directly to `completed`. Actual current graph topology includes `refine_gate` interrupt by default when no feedback is provided, so first pass typically lands in `waiting_input`; completion happens after resume.
- Plan stated `RunService.resume_run()` should invoke graph `Command(resume=...)`. Actual implementation keeps `RunService` focused on state-machine validation/persistence, while orchestrator performs graph invocation after calling `RunService.resume_run()`.
- Plan statement “No new events emitted after cancellation” is approximated via cooperative cancellation checks at safe points; events already emitted by an in-flight node before the next check may still appear.

### v08-B4: Chat Compatibility Adapter

**Status**: ✅ Complete
**Implementation Date**: 2026-02-06

**Files Modified/Created (Actual)**:
- `packages/backend/app/api/chat.py`
- `packages/backend/tests/test_chat_compat_adapter_v08.py`

**Features Implemented**:
- Add `chat_use_run_adapter` branch in `/api/chat` and `/api/chat/stream` (`POST` + `GET` with `message`).
- Adapter ON (legacy orchestrator path) now maps chat calls to `RunService.create_run()+start_run()` and resume calls to `RunService.resume_run()`.
- Keep adapter OFF behavior unchanged for existing frontend compatibility.
- Emit run lifecycle events (`run_created`, `run_started`, `run_resumed`, `run_waiting_input`, `run_completed`, `run_failed`) while preserving existing SSE payload compatibility.
- Finalize run status from chat orchestrator outcomes (`completed` / `waiting_input` / `failed`) with rollback still controlled by feature flag.

**Acceptance Criteria**:
- [x] Adapter OFF keeps current chat behavior fully unchanged.
- [x] Adapter ON uses run lifecycle internally while preserving response contract.
- [x] Stream endpoint remains backward compatible and includes new event types safely.
- [x] Switching flag provides low-risk rollback path.

**Validation Completed**:
- Added `tests/test_chat_compat_adapter_v08.py` covering adapter OFF legacy path, adapter ON create path, adapter ON resume path, and stream lifecycle events.
- Targeted regression run:
  - `cd packages/backend && PYTHONPATH=. pytest -q tests/test_chat_compat_adapter_v08.py tests/test_chat_response_fields.py tests/test_chat_stream_compat.py`
  - `cd packages/backend && CHAT_USE_RUN_ADAPTER=false USE_LANGGRAPH=false PYTHONPATH=. pytest -q tests/test_chat_stream_tool_events.py tests/test_run_service.py tests/test_runs_api.py tests/test_event_layer_upgrade_v08.py tests/test_event_protocol.py tests/test_events.py`
- Result: targeted suites passed.

**Plan vs Implementation Notes (Conflicts)**:
- Plan text implies adapter should always own `create_run/start_run/resume_run` when `chat_use_run_adapter=true`; actual implementation enables this only when `use_langgraph=false` to avoid duplicate run lifecycle ownership with `v08-B3` (LangGraph already manages run create/resume/state transitions).
- Plan lists `packages/backend/app/config.py` as B4 change; no config code update was required because `chat_use_run_adapter` (default `False`) was already introduced in `v08-B1`.

### v08-B5: Tool Policy Hooks

**Status**: ✅ Complete
**Implementation Date**: 2026-02-06

**Files Modified/Created (Actual)**:
- `packages/backend/app/services/tool_policy.py`
- `packages/backend/app/agents/base.py`
- `packages/backend/app/config.py`
- `packages/backend/tests/test_tool_policy.py`

**Features Implemented**:
- Add `ToolPolicyService` with `pre_tool_use()` and `post_tool_use()` hooks and structured `PolicyResult` output.
- Implement default policies:
  - command whitelist for shell-like tools
  - path boundary checks for path-like arguments
  - sensitive content detection in tool arguments/results
  - large output truncation with summary metadata
- Wire hooks into `BaseAgent._wrap_tool_handler()` pre/post tool execution path.
- Add policy modes (`off`, `log_only`, `enforce`) and emit `tool_policy_warn` / `tool_policy_blocked` with run-context propagation through `EventEmitter`.
- Add config knobs: `tool_policy_enabled`, `tool_policy_mode`, `tool_policy_allowed_cmd_prefixes`, `tool_policy_large_output_bytes`.

**Acceptance Criteria**:
- [x] Hooks run for every tool call through BaseAgent wrapper.
- [x] `log_only` emits warning without blocking.
- [x] `enforce` blocks high-risk tool calls consistently.
- [x] Config options support environment override.

**Validation Completed**:
- Added `tests/test_tool_policy.py` covering command whitelist, path boundary, sensitive pattern detection, output truncation, mode switching, and BaseAgent event behavior.
- Regression run:
  - `cd packages/backend && PYTHONPATH=. pytest -q tests/test_tool_policy.py tests/test_tool_events.py`
  - `cd packages/backend && CHAT_USE_RUN_ADAPTER=false USE_LANGGRAPH=false PYTHONPATH=. pytest -q tests/test_chat_stream_tool_events.py tests/test_chat_compat_adapter_v08.py tests/test_event_layer_upgrade_v08.py tests/test_runs_api.py tests/test_run_service.py tests/test_event_protocol.py tests/test_events.py`
- Result: targeted suites passed.

**Plan vs Implementation Notes (Conflicts)**:
- Plan only required three config keys; implementation added `tool_policy_large_output_bytes` to make the truncation threshold externally configurable (aligned with phase notes about configurable threshold).
- Spec phrase “block on high risk” is implemented as policy-level `block` findings transformed by mode: `enforce` keeps block, `log_only` downgrades block to warn, `off` bypasses checks.
- Path-boundary enforcement is implemented via path-like argument heuristics in the generic wrapper (tool-name agnostic) rather than hard-coding per-tool adapters.

### v08-B6: Verify Gate

**Status**: ✅ Complete
**Implementation Date**: 2026-02-06

**Files Modified/Created (Actual)**:
- `packages/backend/app/graph/nodes/verify.py`
- `packages/backend/app/graph/graph.py`
- `packages/backend/app/config.py`
- `packages/backend/app/graph/nodes/base.py`
- `packages/backend/app/graph/nodes/__init__.py`
- `packages/backend/tests/test_verify_gate_v08.py`
- `packages/backend/tests/test_langgraph_skeleton.py`

**Features Implemented**:
- Add verify node between `refine` and `render` in graph topology.
- Execute build, structure, mobile, and security checks with structured report.
- Emit `verify_start/pass/fail` events and store verify report in state.
- Add failure strategy (single retry + escalate to `refine_gate` waiting-input path) with feature flags.

**Acceptance Criteria**:
- [x] Verify pass routes to render; verify fail blocks direct render.
- [x] Retry and escalation strategy follows recoverable path (`refine_gate` interrupt) and keeps run recoverability.
- [x] Verify gate can be disabled via config for fast rollback.
- [x] Verify report is available in run context for debugging.

**Validation Completed**:
- Added `test_verify_gate_v08.py` for: check categories, pass/fail behavior, retry exhaustion, feature-flag disable, and verify event emission.
- Updated `test_langgraph_skeleton.py` routing checks for `should_verify`.
- Targeted run: `cd packages/backend && PYTHONPATH=. pytest -q tests/test_verify_gate_v08.py tests/test_langgraph_skeleton.py tests/test_orchestration_run_integration_v08.py` → `15 passed`.

**Plan vs Implementation Notes**:
- Plan mentions structure check should verify `#app` entry while renderer currently mounts at `#root` and uses `#app` as in-app shell container; implementation treats this as satisfied when template/app shell contracts are present.
- Plan proposes verify fail may escalate to `waiting_input` or `failed`; implementation uses recoverable escalation by routing verify-fail back to `refine_gate` interrupt path (`waiting_input` via orchestrator) instead of immediate terminal `failed`.
- Plan says build check validates React SSG build completion. At verify stage (pre-render), implementation validates pre-render fatal error state plus schema/template integrity; actual build success/failure remains authoritative in `render` node.

### v08-B7: App Data API

**Status**: ✅ Complete
**Implementation Date**: 2026-02-06

**Files Modified/Created (Actual)**:
- `packages/backend/app/api/data.py`
- `packages/backend/app/main.py`
- `packages/backend/app/api/sessions.py`
- `packages/backend/app/api/__init__.py`
- `packages/backend/tests/test_data_api.py`

**Features Implemented**:
- Add app-data REST endpoints under `/api/sessions/{id}/data/*`.
- Support tables listing, paginated query, insert, delete, and stats.
- Enforce strict whitelist validation for table/column/order parameters.
- Integrate schema cleanup on session deletion.

**Acceptance Criteria**:
- [x] All 5 endpoints available with correct status codes.
- [x] Limit/offset/order_by input validation and bounds checks enforced.
- [x] SQL injection and cross-schema attempts blocked.
- [x] Session deletion triggers best-effort schema cleanup.

**Validation Completed**:
- Added API tests for list/query/insert/delete/stats, invalid table/order_by/body validation, and session-delete schema cleanup.
- Targeted runs:
  - `cd packages/backend && python -m pytest tests/test_data_api.py -q` → `3 passed`
  - `cd packages/backend && python -m pytest tests/test_app_data_store.py tests/test_data_api.py -q` → `14 passed`

**Plan vs Implementation Notes**:
- Router registration follows project convention (`api/__init__.py` aggregation + `main.py` include), equivalent to direct registration.
- `GET /data/{table}` response includes `order_by`; `total` comes from store when provided, otherwise falls back to current page length.

### v08-B8: Generation Integration with App Data

**Status**: ✅ Complete
**Implementation Date**: 2026-02-06

**Files Modified/Created (Actual)**:
- `packages/backend/app/agents/generation.py`
- `packages/backend/app/services/data_protocol.py`
- `packages/backend/app/utils/product_doc.py`
- `packages/backend/tests/test_b8_generation_integration.py`
- `packages/backend/tests/test_b8_data_protocol_runtime.py`

**Features Implemented**:
- Hook `AppDataStore.create_schema/create_tables` after generation returns `data_model`.
- Support incremental migration for re-generation with changed model.
- Move iframe runtime data read/write from localStorage to Data API.
- Implement entity-aware runtime sync: map each `data_model.entities` table result back to precise state paths.
- Keep `postMessage` as refresh signal and provide graceful local fallback.
- Align `data_model` with existing `state_contract` definitions.

**Acceptance Criteria**:
- [x] Table/schema auto-creation runs after generation.
- [x] Table creation failures degrade gracefully without blocking HTML generation.
- [x] iframe data operations target backend API with session context.
- [x] `data_model` and `state_contract` stay consistent.

**Validation Completed**:
- Added tests for generation-side schema/table provisioning and failure degradation.
- Added tests for runtime contract injection (`session_id`/`api_base_url`/`data_model`) and API-oriented script output.
- Targeted run: `cd packages/backend && python -m pytest tests/test_b8_generation_integration.py tests/test_b8_data_protocol_runtime.py -q` → `6 passed`.

**Plan vs Implementation Notes**:
- Generation hook is implemented inside `GenerationAgent` after data-protocol injection (covers both single/multi-page execution paths) rather than in graph/orchestrator glue.
- Runtime write path is API-first with asynchronous best-effort posting; local state + localStorage remains as resilience fallback.
- Runtime read path now performs entity-level sync (`table/entity -> state path`) and updates state slices per entity before emitting refresh events.
- `entity_state_map` is generated from `data_model + schema` (with deterministic hints) and injected into runtime contract; when mapping can't be resolved, script-level heuristic fallback is retained.

### v08-F1: Data Tab Frontend Overhaul

**Status**: ✅ Complete
**Implementation Date**: 2026-02-06

**Files Modified/Created (Actual)**:
- `packages/web/src/api/client.ts`
- `packages/web/src/hooks/useAppData.ts`
- `packages/web/src/components/custom/WorkbenchPanel.tsx`
- `packages/web/src/components/custom/PreviewPanel.tsx`
- `packages/web/src/components/custom/DataTab.tsx`
- `packages/web/src/types/events.ts`
- `packages/web/src/hooks/useSSE.ts`
- `packages/web/src/components/EventFlow/EventItem.tsx`
- `packages/web/src/components/custom/ChatMessage.tsx`
- `packages/web/src/components/custom/ChatPanel.tsx`
- `packages/web/src/hooks/useChat.ts`
- `packages/web/src/components/custom/VersionPanel.tsx`

**Features Implemented**:
- Promote Data Tab to Workbench top-level tab.
- Build `useAppData` hook for tables / active table / records / stats / pagination.
- Add postMessage-triggered refresh (`data_changed` + `instant-coffee:update`) with cleanup.
- Rewrite DataTab into `Table View` + `Dashboard View` with JSON-friendly cell rendering.
- Migrate DataTab data source from preview bridge to backend App Data API.
- Add run/verify/policy event typings and SSE dedup key preference (`run_id + seq` when available).
- Keep event timeline UI stable for newly introduced run/verify/policy events.

**Acceptance Criteria**:
- [x] Workbench tabs become `[Preview] [Code] [Product Doc] [Data]`.
- [x] DataTab supports table selector, pagination, and JSONB-friendly rendering.
- [x] Dashboard view displays summary cards + distribution data from stats endpoint.
- [x] Data refresh reacts to iframe `data_changed`/`instant-coffee:update` signal.
- [x] SSE hook/event typing remains stable with new event families.

**Validation Completed**:
- `cd packages/web && npm run lint` passed (existing repo-level warnings remain, no new lint errors from F1).
- `cd packages/web && npx playwright test src/e2e/v08DataTabOverhaul.spec.ts` → `4 passed`.
- `cd packages/web && npm run build` still fails due pre-existing unrelated TypeScript issues (`AestheticScore*`, `useAestheticScore`, `useBuildStatus`).

**Plan vs Implementation Notes (Conflicts)**:
- Plan lists `v08-F1` as blocked by `v08-B7`, while the repository already contains usable `/api/sessions/{id}/data/*` endpoints; implementation proceeded against the existing API surface.
- Plan suggested possible `usePreviewBridge` changes; actual implementation fully removed DataTab's dependency on preview-bridge data and kept preview postMessage behavior only as refresh trigger for compatibility.
- Dashboard scope stays lightweight (cards + CSS bars) without adding chart libraries, matching warning notes and current API capabilities.

---

## Dependency & Rollout Notes

**Critical Path (Run System)**:
- `v08-D1 → v08-B1 → v08-B3 → v08-B6`

**Critical Path (App Data)**:
- `v08-D2 → v08-B7 → v08-F1`

**Parallel Tracks**:
- Run track (`D1/B1/B2/B3/B4/B5/B6`) and App Data track (`D2/B7/B8/F1`) can run mostly in parallel, with integration crossover at `B8` and frontend readiness at `F1`.

**Migration Mapping (from `docs/phases/INDEX.md`)**:
- `M1`: D1, D2 (database foundations)
- `M2`: B1, B2 (run service + event envelope)
- `M3`: B3, B5, B6 (orchestration + policy + verify)
- `M4`: B4 (chat compatibility bridge)
- `M5`: B7, B8, F1 (app data API + generation + frontend)
