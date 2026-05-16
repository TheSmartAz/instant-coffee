# Instant Coffee E2E Test Plan

Last updated: 2026-05-13

## Scope

This document tracks the current test surfaces. Older test-plan sections that referenced planner/task endpoints, legacy agents, or unmounted routes have been removed from the current plan.

## Backend Tests

Backend tests live in `packages/backend/tests`.

Current important coverage areas:

- app data store and data API
- asset registry
- data protocol runtime
- build runner
- chat run adapter
- engine config bridge
- event layer and event type mappings
- file tree and files API
- HTML/mobile shell/style utilities
- DB migrations
- page services and pages API
- product doc API, tiers, utilities
- project snapshots
- renderer builder
- deterministic review service
- run coordinator
- run service and runs API
- run data layer
- schemas and skills registry
- state store service

Backend e2e tests currently include:

- `packages/backend/tests/e2e/test_data_protocol_e2e.py`
- `packages/backend/tests/e2e/test_real_chat_run_adapter_smoke.py`

Run backend tests:

```bash
cd packages/backend
PYTHONPATH=.:../agent/src python -m pytest -q
```

Run the real-provider smoke only when credentials and live API usage are intended:

```bash
cd packages/backend
RUN_REAL_CHAT_ADAPTER_SMOKE=true CHAT_USE_RUN_ADAPTER=true PYTHONPATH=.:../agent/src python -m pytest tests/e2e/test_real_chat_run_adapter_smoke.py -q
```

The real-provider smoke creates a chat run through the durable adapter, then calls the admin
verification endpoint for that run and asserts command-level verification evidence plus redacted
action audit events are present. It intentionally does not trigger automatic fix attempts, because
those can edit the live repository worktree.

Run the real automatic-fix dogfood only when credentials and live worktree edits are explicitly
intended:

```bash
cd packages/backend
RUN_REAL_VERIFICATION_FIX_DOGFOOD=true ALLOW_REAL_FIX_WORKTREE_EDIT=true CHAT_USE_RUN_ADAPTER=true PYTHONPATH=.:../agent/src python -m pytest tests/e2e/test_real_chat_run_adapter_smoke.py::test_real_chat_run_adapter_verification_fix_dogfood -q
```

This dogfood first creates a real chat run and executes run verification. It calls
`/api/runs/{run_id}/fix-verification` only when the real verification result fails; if verification
already passes, the test skips the automatic-fix portion because there is no failed verification
evidence to repair.

## Agent Tests

Agent tests live in `packages/agent/tests`.

Run:

```bash
cd packages/agent
python -m pytest -q
```

## Web E2E Tests

Playwright specs live in `packages/web/src/e2e`.

Current specs:

- `AssetUpload.spec.ts`
- `DataTab.spec.ts`
- `ImageUpload.spec.ts`
- `PreviewBridge.spec.ts`
- `RunStatus.spec.ts`
- `v08DataTabOverhaul.spec.ts`

Shared helpers live in `packages/web/src/e2e/helpers`.

Run:

```bash
cd packages/web
npx playwright test
```

Run a single spec:

```bash
cd packages/web
npx playwright test src/e2e/RunStatus.spec.ts
```

Debug:

```bash
cd packages/web
npx playwright test --debug
```

## Web Static Checks

```bash
cd packages/web
npm run lint
npm run build
```

## Current Priority Scenarios

### 1) Chat Through Run Adapter

Goal:

- A chat request creates or reuses the correct session/run.
- Implement/build/review/optional fix lifecycle events emit, with verification events derived from review.
- The run reaches a terminal state or waiting-input state with useful metadata.

Backend evidence:

- `test_chat_run_adapter.py`
- `test_run_coordinator.py`
- `test_run_service.py`
- `test_runs_api.py`
- optional `test_real_chat_run_adapter_smoke.py`, including real-provider run verification when
  `RUN_REAL_CHAT_ADAPTER_SMOKE=true` and destructive automatic-fix dogfood when both
  `RUN_REAL_VERIFICATION_FIX_DOGFOOD=true` and `ALLOW_REAL_FIX_WORKTREE_EDIT=true`

Web evidence:

- `RunStatus.spec.ts`, including run SSE status, shell approval status display, build preview
  availability, and absence of the removed Run details entry.

### 2) Product Doc And Page Persistence

Goal:

- Product docs are generated/read with history support.
- Pages and page versions persist.
- Version preview, pin/unpin, and project snapshot rollback remain functional.

Backend evidence:

- `test_product_doc_api.py`
- `test_page_services.py`
- `test_pages_api.py`
- `test_project_snapshot_service.py`

### 3) Build And Review Gate

Goal:

- Build status/logs are persisted.
- Review issues are structured and actionable.
- Failed review/build can trigger the fix path.

Backend evidence:

- `test_build_runner.py`
- `test_review_service.py`
- `test_run_coordinator.py`

### 4) App Data And Preview Bridge

Goal:

- Generated app data can be written/read through the data API.
- Preview iframe messages populate the Data tab.

Backend evidence:

- `test_app_data_store.py`
- `test_data_api.py`
- `test_data_protocol.py`
- `test_b8_data_protocol_runtime.py`
- `tests/e2e/test_data_protocol_e2e.py`

Web evidence:

- `DataTab.spec.ts`
- `PreviewBridge.spec.ts`
- `v08DataTabOverhaul.spec.ts`

### 5) Uploads And References

Goal:

- Image and asset upload flows work.
- Uploaded references can be used by chat/preview UI.

Web evidence:

- `ImageUpload.spec.ts`
- `AssetUpload.spec.ts`

Backend evidence:

- `test_asset_registry.py`

## Known Test Gaps

- Node CLI has targeted automated tests for export/stats compatibility; other commands remain uncovered.
- Web still has legacy task/export calls; e2e coverage should either pin expected disabled/unsupported behavior or be updated after the API is restored.
- Deployment, QR sharing, and analytics dashboard are not implemented and therefore not testable as current features.
- Full live-model generation remains opt-in because it uses external API quota.
