# Instant Coffee Current Project Summary

Last updated: 2026-05-16

## Status

Instant Coffee is a monorepo for chat-driven mobile-first React app generation. The current runtime is centered on:

- FastAPI backend services in `packages/backend/app`
- embedded Python `ic` agent engine from `packages/agent`
- Vite React web UI in `packages/web`
- legacy Node CLI in `packages/cli`; export/stats and shared compatibility utilities have TypeScript source and tests

Older docs describe a LangGraph/Planner/Task/Agent directory architecture. Those files are historical. The current backend does not contain `packages/backend/app/agents`, `planner`, `executor`, `graph`, or `generators`.

## Package Map

```text
packages/backend
  app/api              mounted API route modules
  app/db               SQLAlchemy models, migrations, DB init
  app/engine           backend adapter around ic.soul.engine.Engine
  app/events           event models, emitter, event type constants
  app/llm              model catalog and provider config
  app/renderer         React SSG build pipeline (Vite + prerender)
  app/schemas          Pydantic API schemas
  app/services         run, build, review, pages, product docs, snapshots, app data
  tests                unit/e2e tests

packages/agent
  src/ic/soul          agentic loop, context, skills
  src/ic/tools         file, shell, ask, think, todo, skill, subagent, web tools
  src/ic/session       projects, checkpoints, undo, rollback, branches
  src/ic/llm           provider abstraction

packages/web
  src/pages            HomePage, ProjectPage, ExecutionPage, SettingsPage
  src/components       chat, preview, workbench, versions, run inspector, events
  src/hooks            chat/SSE/session/build/preview bridge hooks
  src/api              API client
  src/types            event and domain types
  src/e2e              Playwright specs

packages/cli
  src                  TypeScript source for export/stats/history-list compatibility paths and shared utilities
  tests                Node test coverage for export/stats compatibility paths
  dist                 compiled legacy Node CLI output
```

## Backend Runtime

`packages/backend/app/main.py` registers the application, initializes the DB, optionally runs migration helpers, initializes the app data store, and mounts `/assets`.
It also configures CORS and rate limiting. `/health` is lightweight by default; `/health?deep=true` checks database and disk access.

Mounted route areas:

- `/api/chat`
- `/api/sessions`
- `/api/runs`
- `/api/sessions/{id}/assets`
- `/api/sessions/{id}/build`
- `/api/sessions/{id}/data`
- `/api/sessions/{id}/events`
- `/api/settings`
- `/api/background-tasks`
- `/api/sessions/{id}/pages/{page_id}/diff`
- `/preview` and `/share`
- `/api/migrations`
- `/api/pages`
- `/api/sessions/{id}/product-doc`
- `/api/sessions/{id}/files`
- `/api/sessions/{id}/snapshots`
- `/api/sessions/{id}/schemas`
- `/api/sessions/{id}/export`
- `/api/export` (legacy CLI compatibility)
- `/api/stats`
- `/api/stats/session/{id}`
- `/api/session/{id}/abort` (legacy abort compatibility)
- `/api/plan` (event-store compatibility)
- `/api/plan/{id}/status` (event-store compatibility)
- `/api/task/{id}/status` (event-store compatibility)
- `/api/task/{id}/retry` (event-store compatibility)
- `/api/task/{id}/skip` (event-store compatibility)
- `/api/task/{id}/modify` (event-store compatibility)
- `/health`

Not mounted in the current backend:

- Legacy Plan/Task table-backed executor routes are not present; compatibility routes persist events only.

## Chat and Generation Flow

Primary endpoints:

- `POST /api/chat`
- `POST /api/chat/stream`
- `GET /api/chat/stream`

Chat supports sessions, threads, image/style references, page mentions, target pages, mentioned files, interview payloads, and pending engine questions.

The modern backend path uses `EngineOrchestrator`, which embeds `ic.soul.engine.Engine`. The orchestrator injects Product Doc, page summaries, project memory, mentioned files, and visual references into the agent context. It exposes DB-backed write/edit/multiedit tools so generated files are persisted into the project model.

When `CHAT_USE_RUN_ADAPTER=true` (the default), chat is coordinated through the durable run adapter. The older direct chat path still exists behind that flag.

## Run Coordinator

Durable run orchestration lives in `packages/backend/app/engine/run_coordinator.py`.

Run phase vocabulary includes planning and verification event labels, but the current chat adapter executes this practical sequence:

- `implement`
- `build`
- `review`
- optional `fix`
- `done`

The chat run adapter composes:

- `EngineOrchestrator` for implementation
- `BuildRunner` for React SSG/static build when the session has pages
- `ReviewService` for deterministic review gate when the session has pages
- one fix attempt when review/build fails

Sessions without generated pages still use placeholder build/review results so the run can complete after non-page interactions.

Run state is stored through `RunService` and exposed via `/api/runs`. Runs can be listed, retrieved, resumed, cancelled, and queried for events.
The run API also supports approvals, verification audit submission, verification-fix attempts, and fix gate resolution.

Verification/fix maturity currently includes:

- allowlisted backend verification commands with structured command results;
- mobile visual smoke checks when a build artifact has a `dist_path`;
- stale automatic-fix recovery and per-run fix locking;
- structured verification failure routing with safe `route`, `kind`, and `fix_hint` fields for
  repair prompts and action audit flags;
- redacted public run responses for prompts, engine payloads, command output, metrics, and memory content;
- automatic-fix change summaries scoped to files changed during the fix attempt;
- redacted action audit events for verification commands, visual checks, fix prompt preparation, agent execution, edit summaries, and gate decisions;
- deterministic reviewer recommendations for blocked fix gates, generated without exposing prompt text, command output, raw diffs, or engine payloads;
- an automatic fix acceptance gate: verification-passing low/medium-risk fixes are auto-accepted, while high-risk or non-passing fixes remain blocked until the admin gate endpoint approves or rejects them.
- duplicate admin resolution of an already accepted, rejected, or manually resolved fix gate is rejected with a conflict response.

## Database

Current SQLAlchemy tables include:

- `sessions`
- `session_runs`
- `threads`
- `project_memory`
- `messages`
- `versions`
- `token_usage`
- `product_docs`
- `product_doc_histories`
- `project_snapshots`
- `project_snapshot_docs`
- `project_snapshot_pages`
- `pages`
- `page_versions`
- `session_events`
- `session_event_sequences`

There are no current `plans` or `tasks` tables in `models.py`.

## Events

Backend event constants live in `packages/backend/app/events/types.py`; frontend event types live in `packages/web/src/types/events.ts`.

Current event families cover:

- agent lifecycle
- tool calls/results/progress
- token/cost updates
- shell/background task events
- product doc, interview, page, version, snapshot, history
- workflow, build, refine
- run lifecycle, run phase, heartbeat, cancellation
- verify and tool policy
- files changed, context compaction, plan updates, spawned agents

Events are persisted through the session event store and can be replayed with `/api/sessions/{session_id}/events`.

## Web App

Routes:

- `/`: `HomePage`
- `/project/:id`: `ProjectPage`
- `/project/:id/flow`: `ExecutionPage`
- `/settings`: `SettingsPage`

`ProjectPage` is the main application surface:

- `ChatPanel` for chat, interview, mentions, uploads, and lightweight run status.
- ProjectPage intentionally does not include the removed Run details drawer or Run Inspector UI.
- `WorkbenchPanel` with `preview`, `code`, `product-doc`, and `data` tabs.
- `VersionPanel` for legacy and page version history.

`ExecutionPage` can record legacy task retry/skip actions through event-store compatibility routes.

## Agent Package

`packages/agent` is a Python package named `ic`.

Capabilities:

- interactive and non-interactive CLI
- tool-calling loop
- file/shell/web/ask/todo/think/skill/subagent tools
- parallel subagents
- checkpoints, undo, rollback, branches
- Product Doc context
- token/cost tracking
- context compaction callbacks

Current project-supported defaults are DeepSeek-compatible.

## CLI Package

The Node CLI is legacy overall, but `export` and `stats` now have TypeScript source and tests.

Commands in `packages/cli/dist`:

- `chat`
- `history`
- `rollback`
- `export`
- `stats`
- `clean`
- `migrate-v04`

Known mismatches:

- Node CLI `export` and `stats` are backed by compatibility routes and covered by targeted tests.
- Node CLI shared config/API/logger/stat-formatting utilities and `history/list` now have checked-in TypeScript source.
- Node CLI `chat`, most `history`, `rollback`, `clean`, and `migrate-v04` still lack checked-in TypeScript source.
- Web task retry/skip is compatibility-only and records events; it does not reschedule old executor tasks.
- `chat` uses a query-string SSE mode that can become brittle for large payloads.

## Test Commands

Backend:

```bash
cd packages/backend
PYTHONPATH=.:../agent/src python -m pytest -q
```

Agent:

```bash
cd packages/agent
python -m pytest -q
```

Web:

```bash
cd packages/web
npm run lint
npm run build
npx playwright test
```

CLI:

```bash
cd packages/cli
npm test
```

Opt-in real provider smoke:

```bash
cd packages/backend
RUN_REAL_CHAT_ADAPTER_SMOKE=true CHAT_USE_RUN_ADAPTER=true PYTHONPATH=.:../agent/src python -m pytest tests/e2e/test_real_chat_run_adapter_smoke.py -q
```

## Current Documentation Rule

Use current guides in this order:

1. `README.md`
2. `CLAUDE.md`
3. `docs/project-summary.md`
4. package README files

Use `docs/spec/**`, `docs/phases/**`, and early implementation plans as historical design context unless a newer current guide confirms the claim.
