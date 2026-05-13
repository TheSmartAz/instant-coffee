# Instant Coffee - Developer Guide

Last updated: 2026-05-13

## Project Overview

Instant Coffee is a monorepo for generating mobile-first HTML pages and static sites through chat. It currently has:

- A FastAPI backend that owns sessions, pages, product docs, events, builds, runs, files, snapshots, and settings.
- A standalone Python `ic` agent engine that can run in a terminal or be embedded by the backend.
- A Vite React web UI for project creation, chat, preview/code/product-doc/data workbench views, versions, settings, and run observability.
- A legacy Node/Commander CLI with compiled JS only in `packages/cli/dist`.

The current implementation is DeepSeek-oriented by default. Historical docs still mention OpenAI/Anthropic and older agent/planner/executor directories; those are roadmap/history unless the referenced code still exists.

## Repository Layout

```text
instant-coffee/
├── packages/
│   ├── backend/
│   │   ├── app/
│   │   │   ├── api/          # mounted FastAPI route modules
│   │   │   ├── db/           # SQLAlchemy models, init, migrations
│   │   │   ├── engine/       # backend adapter around ic.soul.engine.Engine
│   │   │   ├── events/       # event models, emitter, event types
│   │   │   ├── llm/          # model catalog and provider config
│   │   │   ├── middleware/   # rate limiting
│   │   │   ├── renderer/     # HTML -> React SSG build path
│   │   │   ├── schemas/      # API schemas
│   │   │   ├── services/     # product docs, pages, runs, builds, review, app data
│   │   │   └── utils/
│   │   ├── tests/
│   │   ├── requirements.txt
│   │   └── requirements.lock
│   ├── agent/
│   │   └── src/ic/
│   │       ├── doc/          # product doc helpers
│   │       ├── llm/          # provider abstraction
│   │       ├── session/      # projects, checkpoints, branches
│   │       ├── soul/         # agentic loop, context, skills
│   │       ├── tools/        # ask, file, shell, skill, subagent, think, todo, web
│   │       └── ui/
│   ├── web/
│   │   └── src/
│   │       ├── api/          # API client and domains
│   │       ├── components/   # custom UI, EventFlow, TaskCard, shadcn ui
│   │       ├── e2e/          # Playwright specs
│   │       ├── hooks/        # chat, SSE, session, build, preview bridge
│   │       ├── pages/        # HomePage, ProjectPage, ExecutionPage, SettingsPage
│   │       ├── types/        # frontend event/domain types
│   │       └── utils/
│   └── cli/
│       └── dist/             # legacy compiled CLI commands and utils
└── docs/
```

There is no current `packages/backend/app/agents`, `planner`, `executor`, `graph`, or `generators` directory.

## Backend Architecture

`packages/backend/app/main.py` creates the FastAPI app, initializes the DB on startup, optionally runs v04 migration on startup, initializes the app data store, mounts `/assets`, and registers these route groups:

- `/api/sessions`
- `/api/chat`
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
- `/health`

`/health` is lightweight by default. `/health?deep=true` checks DB and disk health as well.

### Chat and Runs

Modern chat can run directly through the engine or through the durable run adapter:

- `POST /api/chat`
- `POST /api/chat/stream`
- `GET /api/chat/stream`

The run adapter prepares a `RunCoordinator` with these phases:

1. `implement`: `EngineOrchestrator` calls the embedded `ic` agent.
2. `build`: `BuildRunner` builds persisted pages through the React SSG pipeline.
3. `review`: `ReviewService` checks product doc, pages, page HTML, expected slugs, and build status/logs.
4. `fix`: one engine-driven repair attempt, then build/review again.
5. `verify` / `done`: emits final lifecycle and verification events.

Run state is persisted in `session_runs`, with statuses including `queued`, `running`, `waiting_input`, `completed`, `failed`, and `cancelled`. Active run conflict protection is implemented in the service and migration layer.

### Embedded Agent

`packages/backend/app/engine/orchestrator.py` wraps `ic.soul.engine.Engine`. The backend injects Product Doc, page summaries, project memory, mentioned files, image/style references, and uses DB-backed write/edit/multiedit tools. Agent/tool events are bridged into backend SSE event models.

Available agent tool groups include file read/write/edit/multiedit, glob/grep, shell, think, todo, ask-user, create subagent, create parallel subagents, execute skill, web search, and web fetch.

### Database

SQLAlchemy models currently cover these core tables:

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

Migrations in `packages/backend/app/db/migrations.py` run on startup. v12 adds an active-run uniqueness guard for queued/running runs per session.

### Event Contract

Backend event definitions live in `packages/backend/app/events/types.py` and event models live in `packages/backend/app/events/models.py`. Frontend event types live in `packages/web/src/types/events.ts`. Keep them synchronized when adding events.

Important current event families:

- Agent/tool/token/cost/shell/delta/error/done
- Product Doc, interview, multipage, sitemap, page, version, snapshot, history
- Workflow/build/refine
- Run lifecycle, run phase, run heartbeat, run cancellation
- Verify and tool policy
- `files_changed`, `context_compacted`, `plan_update`, `agent_spawned`
- Background task events

## Web Architecture

Routes in `packages/web/src/App.tsx`:

- `/`: `HomePage`
- `/project/:id`: `ProjectPage`
- `/project/:id/flow`: `ExecutionPage`
- `/settings`: `SettingsPage`

`ProjectPage` is the primary surface:

- Left: `ChatPanel`
- Center: `WorkbenchPanel` with `preview`, `code`, `product-doc`, and `data` tabs
- Right: `VersionPanel`
- Chat integrates `RunStatusStrip` and `RunInspector` for run/build/review/policy state.

`packages/web/src/api/client.ts` contains current API domains for sessions, chat, pages, product docs, snapshots, files, export, build, runs, events, settings, and event-store-backed task compatibility actions.

## Agent CLI

`packages/agent` is a Python package named `ic`.

```bash
cd packages/agent
pip install -e .
DEEPSEEK_API_KEY=your_key ic
ic --prompt "Build a mobile product page"
```

Config priority is environment variables, project `.instant-coffee/config.local.toml`, project `.instant-coffee/config.toml`, then `~/.ic/config.toml`. Current project-supported defaults are DeepSeek-compatible (`deepseek-v4-pro`, `https://api.deepseek.com`).

## Legacy Node CLI

`packages/cli` remains legacy overall. `export` and `stats` now have TypeScript source/tests under `src/` and `tests/`; the other commands still ship as compiled JS only. Commands:

- `chat`
- `history`
- `rollback`
- `export`
- `stats`
- `clean`
- `migrate-v04`

`chat`, `history`, and parts of `rollback` target current or partially current backend endpoints. `export` and `stats` are supported through compatibility routes and covered by CLI tests.

## Local Development

Backend:

```bash
cd packages/backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=.:../agent/src DEEPSEEK_API_KEY=your_key python -m uvicorn app.main:app --reload
```

Web:

```bash
cd packages/web
npm install
npm run dev
```

Agent:

```bash
cd packages/agent
pip install -e .
ic
```

Legacy Node CLI:

```bash
cd packages/cli
npm install
node dist/index.js
```

## Environment Variables

Backend and agent:

```bash
DEEPSEEK_API_KEY=
DEFAULT_KEY=
DEFAULT_BASE_URL=
MODEL=
DEFAULT_MODEL=
DATABASE_URL=sqlite:///./instant-coffee.db
OUTPUT_DIR=instant-coffee-output
RUN_API_ENABLED=true
CHAT_USE_RUN_ADAPTER=true
RUN_STALE_TIMEOUT_SECONDS=1800
OPENAI_API_MODE=responses
OPENAI_TIMEOUT_SECONDS=60
OPENAI_MAX_RETRIES=2
MIGRATE_V04_ON_STARTUP=false
INTERVIEW_TIMEOUT_SECONDS=180
PRODUCT_DOC_TIMEOUT_SECONDS=180
```

Web:

```bash
VITE_API_URL=http://localhost:8000
```

Node CLI:

```bash
BACKEND_URL=http://localhost:8000
OUTPUT_DIR=~/instant-coffee-output
VERBOSE=false
```

## Tests

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

CLI has targeted tests for the `export` and `stats` compatibility commands.

## Current Known Gaps

- `POST /api/sessions/{session_id}/rollback` is reserved for legacy version rollback; turn rollback uses `/api/sessions/{session_id}/agent/rollback`.
- Web task retry/skip uses compatibility routes that record plan/task events; it does not restore the old parallel task executor.
- Node CLI `export` and `stats` use compatibility routes with TypeScript source/tests; remaining CLI commands are still legacy compiled JS.
- Phase and spec docs are historical plans. They are useful for intent, not authoritative API or file layout references.

## Files Not To Edit Casually

- `packages/cli/node_modules/`
- `packages/backend/venv/`, `.venv/`, `__pycache__/`, `.pytest_cache/`
- `*.db`
- `instant-coffee-output/`
- `packages/web/dist/`
