# Instant Coffee

> AI-assisted, mobile-first page and static-site generation through chat.

Last updated: 2026-05-13

## Current Status

Instant Coffee is now a monorepo with four active surfaces:

- `packages/backend`: FastAPI API, SQLite/PostgreSQL-compatible data layer, SSE events, run lifecycle, page/version/product-doc services, React SSG build pipeline, and the embedded agent adapter.
- `packages/agent`: standalone Python `ic` agent engine with tool calling, subagents, shell/file/web tools, product-doc context, checkpoints, undo/rollback/branches, and token/cost tracking.
- `packages/web`: Vite + React + Tailwind + shadcn/Radix web UI for projects, chat, preview, code, product docs, data, versions, settings, and run observability.
- `packages/cli`: legacy Node/Commander CLI. Only compiled JavaScript in `dist/` is checked in.

The current implementation is DeepSeek-oriented by default (`DEEPSEEK_API_KEY` or `DEFAULT_KEY`) and uses the Python agent engine for the modern generation path. Older phase/spec documents remain in `docs/` as historical planning records; use this README, `CLAUDE.md`, and `docs/project-summary.md` for the current implementation snapshot.

## Features

- Chat generation through `POST /api/chat` and SSE through `GET|POST /api/chat/stream`.
- Product Doc-first generation and refinement with persisted history.
- Multi-page projects with pages, page versions, version preview/pinning, and project snapshot rollback.
- Asset upload and references for logos, backgrounds, style references, and product images.
- React SSG build and `/preview/{session_id}` static preview.
- Durable run lifecycle through `/api/runs`: implement, build, review, optional fix, done, complete/fail/cancel, plus verification events from review.
- Deterministic build/review gate for generated output quality checks.
- Event persistence and replay via `/api/sessions/{session_id}/events`.
- Web Run Status Strip for lightweight chat-adjacent run/build/review state. The former Run details drawer and Run Inspector UI are intentionally removed from ProjectPage.
- App Data API and Data tab for generated app state/tables.
- Standalone `ic` CLI agent for direct terminal use.

## Requirements

- Python 3.11+
- Node.js 18+
- A DeepSeek-compatible API key via `DEEPSEEK_API_KEY` or `DEFAULT_KEY`

## Quick Start

### Backend

```bash
cd packages/backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=.:../agent/src DEEPSEEK_API_KEY=your_key python -m uvicorn app.main:app --reload
```

The backend initializes its database on startup. Default DB is `sqlite:///./instant-coffee.db`; default generated output directory is `instant-coffee-output`.

Health checks:

```bash
curl http://localhost:8000/health
curl "http://localhost:8000/health?deep=true"
```

The default health check is lightweight. `deep=true` also checks database and disk access.

### Web

```bash
cd packages/web
npm install
npm run dev
```

Set `VITE_API_URL` when the backend is not on `http://localhost:8000`.

### Agent CLI

```bash
cd packages/agent
pip install -e .
DEEPSEEK_API_KEY=your_key ic
```

Non-interactive use:

```bash
ic --prompt "Build a mobile signup page"
```

### Legacy Node CLI

```bash
cd packages/cli
npm install
node dist/index.js
```

The Node CLI commands are still present (`chat`, `history`, `rollback`, `export`, `stats`, `clean`, `migrate-v04`). `export` and `stats` now have TypeScript source and tests around the compatibility API routes; the remaining commands are still legacy compiled JS.

## Key Environment Variables

Backend and agent:

- `DEEPSEEK_API_KEY` / `DEFAULT_KEY`: required for live model calls.
- `DEFAULT_BASE_URL`: model API base URL, defaulting to DeepSeek-compatible configuration.
- `MODEL` / `DEFAULT_MODEL`: default model override.
- `DATABASE_URL`: defaults to `sqlite:///./instant-coffee.db`.
- `OUTPUT_DIR`: defaults to `instant-coffee-output`.
- `RUN_API_ENABLED`: enables the run API surface.
- `CHAT_USE_RUN_ADAPTER`: routes chat through the durable run coordinator, enabled by default. Set `false` to use the older chat path.
- `RUN_STALE_TIMEOUT_SECONDS`: active-run stale timeout.
- `OPENAI_API_MODE`, `OPENAI_TIMEOUT_SECONDS`, `OPENAI_MAX_RETRIES`: provider compatibility settings.

Frontend:

- `VITE_API_URL`: backend API base URL.

Node CLI:

- `BACKEND_URL`: backend API base URL.
- `OUTPUT_DIR`: legacy output directory.
- `VERBOSE`: enables verbose logging.

## Project Structure

```text
instant-coffee/
├── packages/
│   ├── agent/            # Python ic agent engine and tool runtime
│   ├── backend/          # FastAPI API, services, DB, events, renderer
│   ├── cli/              # Legacy Node CLI; export/stats have TS source/tests
│   └── web/              # Vite React web app
├── docs/                 # Current summaries plus historical specs/phases
├── AGENTS.md             # Agent operating contract
├── CLAUDE.md             # Current developer guide
└── README.md
```

## Verification

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
```

Playwright e2e:

```bash
cd packages/web
npx playwright test
```

## Documentation Map

- `CLAUDE.md`: current development guide and architecture notes.
- `docs/project-summary.md`: current implementation snapshot.
- `docs/v10-summary.md`: v1.0/v10 status against the planned roadmap.
- `docs/known_issue.md`: current known gaps and resolved historical issues.
- `docs/run-agent-delivery-split.md`: review lanes for the active run-agent delivery changes.
- `docs/phases/INDEX.md` and `docs/phases/**`: historical roadmap and implementation plans.
- `docs/spec/**`: historical product and architecture specs.

## Current Gaps

- `/api/plan` and `/api/task/...` are mounted as event-store compatibility routes; task retry/skip records status events but does not restore the old parallel task executor.
- The Node CLI remains partly legacy; `export` and `stats` have TypeScript source/tests, while chat/history/rollback/clean/migrate remain compiled JS only.
