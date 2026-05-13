# Known Issues

Last updated: 2026-05-13

## Current Issues

### 1) Legacy Task Control Is Event-Sourced Compatibility

Symptoms:

- Task retry/skip controls in the flow view record status events.
- Export and abort controls now have compatibility backend routes.

Cause:

- The old Plan/Task database tables and parallel task executor are no longer present.
- The backend now mounts `/api/plan` and `/api/task/...` as event-store compatibility routes.

Suggested fix:

- Keep export and abort routed through the compatibility API surface.
- Treat task retry/skip as status-event controls until a real task scheduler exists again.

Relevant files:

- `packages/web/src/api/client.ts`
- `packages/web/src/pages/ProjectPage.tsx`
- `packages/web/src/pages/ExecutionPage.tsx`
- `packages/backend/app/main.py`

### 2) Node CLI Remains Partly Legacy

Symptoms:

- `instant-coffee export` and `instant-coffee stats` use compatibility API routes and now have TypeScript source/tests.
- The remaining Node CLI commands still ship as legacy compiled JS.

Suggested fix:

- Keep the compatibility routes stable.
- Restore TypeScript source/tests for chat/history/rollback/clean/migrate if those commands remain supported.

Relevant files:

- `packages/cli/src/commands/export.ts`
- `packages/cli/src/commands/stats.ts`
- `packages/cli/tests/compat-commands.test.mjs`
- `packages/cli/dist/commands/export.js`
- `packages/cli/dist/commands/stats.js`
- `packages/cli/dist/index.js`

### 3) Duplicate Rollback Route Registration

Symptoms:

- The rollback semantics have been split, but older docs and callers may still assume a single `/rollback` path.

Suggested fix:

- Use `/api/sessions/{session_id}/versions/{version_id}/revert` for version rollback and `/api/sessions/{session_id}/agent/rollback` for turn rollback.

Relevant file:

- `packages/backend/app/api/sessions.py`

### 4) Page-Level Rollback Route Is Unsupported

Symptoms:

- `POST /api/pages/{page_id}/rollback` exists but returns `410 rollback_not_supported`.
- Docs or UI that imply page-version rollback is active will mislead users.

Suggested fix:

- Route rollback UX through project snapshots: `POST /api/sessions/{session_id}/snapshots/{snapshot_id}/rollback`.
- Keep page-version preview and pin/unpin documented separately from rollback.

Relevant files:

- `packages/backend/app/api/pages.py`
- `packages/backend/app/api/snapshots.py`
- `packages/web/src/components/custom/VersionPanel.tsx`

### 5) CLI Streaming Uses Query Parameters For Large Payloads

Symptoms:

- The legacy Node CLI prefers `GET /api/chat/stream` with query parameters.
- Long prompts, images, or structured interview payloads can exceed practical URL limits.

Suggested fix:

- Prefer `POST /api/chat/stream` for streaming chat payloads.
- Keep `GET` only for simple compatibility calls.

Relevant files:

- `packages/cli/dist/commands/chat.js`
- `packages/backend/app/api/chat.py`

### 6) Legacy Task Retry/Skip Is Compatibility-Only

Symptoms:

- The execution flow view still has retry/skip task semantics.
- The backend records task retry/skip events but does not reschedule legacy task work.

Suggested fix:

- Keep the current compatibility behavior or wire it to a real task scheduler when one exists.

## Resolved Or Obsolete Historical Issues

### Historical: Fallback Template From Old Generation Agent

Old docs referenced `packages/backend/app/agents/generation.py`. That directory no longer exists in the current backend. Generation now flows through the embedded `ic` engine and DB-backed tools.

If fallback HTML appears again, diagnose the current path instead:

- `packages/backend/app/engine/orchestrator.py`
- `packages/agent/src/ic/soul/engine.py`
- `packages/backend/app/services/page_version.py`
- `packages/backend/app/renderer/*`

### Historical: Stuck Plan/Task Executor

Old docs referenced `packages/backend/app/executor/parallel.py` and `plans/tasks` tables. Those are not part of the current backend. Durable work should be diagnosed through:

- `packages/backend/app/engine/run_coordinator.py`
- `packages/backend/app/services/run.py`
- `packages/backend/app/api/runs.py`
- `packages/backend/app/db/migrations.py`

### Historical: Events Disappear After Refresh

Session event persistence now exists through `session_events` and `session_event_sequences`, with replay via `/api/sessions/{session_id}/events`.

Relevant files:

- `packages/backend/app/events/*`
- `packages/backend/app/services/event_store.py`
- `packages/backend/app/api/events.py`
- `packages/web/src/types/events.ts`

### Historical: Cannot Preview Historical Page Versions

The current pages API includes version preview routes:

- `GET /api/pages/{page_id}/versions/{version_id}/preview`
- `POST /api/pages/{page_id}/versions/{version_id}/pin`
- `POST /api/pages/{page_id}/versions/{version_id}/unpin`

Page-level rollback is not supported; use ProjectSnapshot rollback instead:

- `POST /api/sessions/{session_id}/snapshots/{snapshot_id}/rollback`

Relevant files:

- `packages/backend/app/api/pages.py`
- `packages/backend/app/services/page_version.py`
- `packages/web/src/components/custom/VersionPanel.tsx`
