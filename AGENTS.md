# AGENTS

## Project Summary
Instant Coffee is a monorepo for an AI CLI and web UI that generate mobile-first HTML pages. The backend is FastAPI with SQLite and LLM clients (OpenAI/Anthropic). The CLI is Node-based (Commander) and currently ships compiled JS in `packages/cli/dist`. The web app is Vite + React + Tailwind + shadcn.

## Repo Layout
- `packages/backend`: FastAPI app in `app/` (agents, planner, executor, services, events, db).
- `packages/cli`: Node CLI, compiled JS in `dist/` (no TS source checked in).
- `packages/web`: Vite React UI; alias `@/` -> `src/`.
- `docs`: product specs and phased roadmap.

## Key Runtime Flows
- Chat: `POST /api/chat` or `GET /api/chat/stream` (SSE). Orchestrator uses Interview/Generation/Refinement agents.
- Sessions: `/api/sessions` for list/create, plus `/messages`, `/versions`, `/preview`, `/rollback`.
- Plan/Tasks: `/api/plan`, `/api/task/...` (see `packages/backend/app/api`).
- SSE events: backend models in `packages/backend/app/events`; frontend types in `packages/web/src/types/events.ts` must stay in sync.

## Local Dev
Backend:
- `cd packages/backend`
- Create a venv if needed; deps are not pinned in repo.
- Run: `uvicorn app.main:app --reload`
- Default DB: `sqlite:///./instant-coffee.db` (relative to cwd)
- Output dir default: `instant-coffee-output` (relative to cwd)

CLI:
- `cd packages/cli`
- Uses compiled JS in `dist/`
- Run: `npm run dev` or `node dist/index.js`
- Env: `BACKEND_URL`, `OUTPUT_DIR`, `VERBOSE`

Web:
- `cd packages/web`
- `npm install`
- `npm run dev`
- Env: `VITE_API_URL` (default http://localhost:8000)

## Role-Based Workflow
Backend (API + Agents + DB):
- Start from `docs/phases/INDEX.md` to pick the active phase and dependencies.
- Code lives in `packages/backend/app`:
  - API routes: `packages/backend/app/api`
  - Agents/orchestrator: `packages/backend/app/agents`
  - Planner/executor: `packages/backend/app/planner`, `packages/backend/app/executor`
  - DB models + migrations: `packages/backend/app/db`
- When adding new SSE events, update both backend event models and frontend types.
- Run `pytest` from `packages/backend` for regressions.

Frontend Web (Vite React UI):
- Entry points: `packages/web/src/main.tsx`, `packages/web/src/App.tsx`.
- UI/event flow: `packages/web/src/components` and `packages/web/src/hooks/useSSE.ts`.
- Update event typing in `packages/web/src/types/events.ts` whenever backend events change.
- Run `npm run dev` and `npm run lint` from `packages/web`.

CLI (Commander-based):
- Compiled JS only in `packages/cli/dist`; no TS source checked in.
- Commands are registered in `packages/cli/dist/commands`.
- If you need new CLI features, prefer adding TS sources and a build step or edit `dist` directly with care.
- Run `node dist/index.js` (or `npm run dev`) from `packages/cli`.

## Tests/Lint
- Backend: `pytest` (tests in `packages/backend/tests`)
- Web: `npm run lint`
- CLI: no tests present

## Conventions / Pitfalls
- Keep `packages/web/src/types/events.ts` aligned with backend event models.
- Avoid editing generated or local-only files: `packages/cli/node_modules/`, `packages/backend/venv/`, `__pycache__/`, `.pytest_cache/`, `*.db`, `instant-coffee-output/`.
- `python -m app.db.migrations` is not a CLI entry point; DB is created on FastAPI startup.
- README shows older v0.1 flow; roadmap lives in `docs/phases/INDEX.md`.
