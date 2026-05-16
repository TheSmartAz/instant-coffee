# AGENTS

## Project Summary
Instant Coffee is a monorepo for chat-driven, mobile-first HTML/static-site generation.

Current active surfaces:
- `packages/backend`: FastAPI API, SQLAlchemy data layer, SSE/event persistence, run lifecycle, page/version/product-doc services, asset/file/data APIs, React SSG build pipeline, review/verification/gate services, and the backend adapter around the embedded `ic` engine.
- `packages/agent`: standalone Python package `ic`, used directly as a CLI agent and embedded by the backend for the modern generation path.
- `packages/web`: Vite + React + Tailwind + Radix/shadcn UI for projects, chat, preview/code/product-doc/data workbench views, versions, settings, and run observability.
- `packages/cli`: legacy Node/Commander CLI. Compiled JS remains in `dist`; `export`, `stats`, shared config, API client, logger, stats formatter, and history list compatibility now have TypeScript source under `src` plus targeted Node tests.

The current implementation is DeepSeek-compatible by default (`deepseek-v4-pro`, `https://api.deepseek.com`) and reads keys from `DEEPSEEK_API_KEY`, `DMXAPI_API_KEY`, or `DEFAULT_KEY`. Older docs may still mention OpenAI/Anthropic or removed backend `agents/planner/executor` directories; treat those as historical unless current code confirms them.

## Repo Layout
- `packages/backend/app/api`: mounted FastAPI route modules.
- `packages/backend/app/db`: SQLAlchemy models, DB init, migration helpers.
- `packages/backend/app/engine`: adapter around `ic.soul.engine.Engine`, DB-backed tools, event bridge, run coordinator.
- `packages/backend/app/events`: event constants, Pydantic event models, event emitter.
- `packages/backend/app/llm`: model catalog and provider defaults.
- `packages/backend/app/middleware`: rate limiting.
- `packages/backend/app/renderer`: HTML/React SSG writer and build templates.
- `packages/backend/app/schemas`: API schemas.
- `packages/backend/app/services`: run, build, review, pages, versions, product docs, snapshots, app data, assets, files, token tracking, verification.
- `packages/backend/tests`: backend unit/e2e tests.
- `packages/agent/src/ic`: agent CLI/runtime, tool loop, session/checkpoint support, LLM provider, tools, UI.
- `packages/agent/tests`: agent tests.
- `packages/web/src`: React app source; alias `@/` maps to `src/`.
- `packages/web/src/e2e`: Playwright specs.
- `packages/cli/src`: checked-in TypeScript compatibility sources.
- `packages/cli/dist`: compiled legacy CLI output.
- `packages/cli/tests`: Node tests for CLI compatibility paths.
- `docs`: current summaries plus historical specs, phase plans, and roadmap material.

There is no current `packages/backend/app/agents`, `planner`, `executor`, `graph`, or `generators` directory.

## Key Runtime Flows
- Chat: `POST /api/chat`, `POST /api/chat/stream`, and `GET /api/chat/stream`.
- Sessions: `/api/sessions` plus messages, metadata, versions, preview, rollback/revert, threads, cost, undo, agent rollback, and branches.
- Runs: `/api/runs` for create/list/get/resume/cancel/approvals/verification/fix-verification/fix-gate-resolution/events.
- Pages: `/api/sessions/{id}/pages`, `/api/pages/{page_id}`, page versions, previews, pin/unpin, rollback, and per-session page diff/version routes.
- Product Docs: `/api/sessions/{id}/product-doc` plus history/diff/confirm/update routes.
- Build: `/api/sessions/{id}/build`, status, logs, stream, and delete/cancel.
- Assets/files/data/snapshots/schemas/settings/background-tasks all have mounted route modules under `packages/backend/app/api`.
- Compatibility: `/api/export`, `/api/stats`, `/api/stats/session/{id}`, `/api/plan`, `/api/task/...`, and `/api/session/{id}/abort` exist for legacy CLI/web compatibility. Plan/task routes persist events; they do not restore an old table-backed task executor.
- Health: `/health` is lightweight; `/health?deep=true` also checks DB and disk.

The modern backend path embeds `ic.soul.engine.Engine` through `EngineOrchestrator`. It injects Product Doc, page summaries, project memory, mentioned files, image/style references, and exposes DB-backed write/edit/multiedit tools so generated files persist into the project model.

The durable run coordinator uses practical phases `implement -> build -> review -> optional fix -> done`. Chat normally uses this adapter when `CHAT_USE_RUN_ADAPTER=true`. Build/review phases now run real session build/review when pages exist, otherwise they use placeholders for sessions that have not produced pages yet.

Run verification/fix observability includes command-level verification results, visual smoke checks, redacted action audit events, automatic-fix change summaries, reviewer recommendations, and a fix acceptance gate. High-risk or non-passing automatic fixes must remain blocked until the admin gate endpoint resolves them.

## Local Dev
Backend:
- `cd packages/backend`
- `python -m venv .venv && source .venv/bin/activate`
- `pip install -r requirements.txt`
- `PYTHONPATH=.:../agent/src DEEPSEEK_API_KEY=your_key python -m uvicorn app.main:app --reload`
- Default DB: `sqlite:///./instant-coffee.db` relative to cwd.
- Default output dir: `instant-coffee-output` relative to cwd.

Agent CLI:
- `cd packages/agent`
- `pip install -e .`
- `DEEPSEEK_API_KEY=your_key ic`
- Non-interactive: `ic --prompt "Build a mobile signup page"`

Web:
- `cd packages/web`
- `npm install`
- `npm run dev`
- `VITE_API_URL` defaults to `http://localhost:8000`.

Legacy Node CLI:
- `cd packages/cli`
- `npm install`
- `npm run build`
- `node dist/index.js` or `npm run dev`
- Env: `BACKEND_URL`, `OUTPUT_DIR`, `VERBOSE`.

## Role-Based Workflow
Backend:
- Start with `docs/project-summary.md`, `README.md`, and `CLAUDE.md` for current state. Use `docs/phases/**` and `docs/spec/**` as historical design context unless current docs or code confirm a claim.
- When adding or changing route behavior, update schemas/services/tests in the same slice.
- When changing verification or automatic-fix behavior, keep `VerificationFixAttempt.change_summary`, `VerificationFixAttempt.gate`, deterministic reviewer recommendations, redaction helpers, action audit events, Run Inspector types/UI, and run API tests aligned.
- When adding new SSE/event types, update backend event constants/models and frontend `packages/web/src/types/events.ts` together.
- Keep compatibility routes explicit: legacy Plan/Task routes are event-store compatibility, not a real old executor.
- Run backend tests from `packages/backend` with `PYTHONPATH=.:../agent/src python -m pytest -q`.

Agent:
- Code lives under `packages/agent/src/ic`.
- Keep backend embedding needs in mind when changing tool contracts, session/checkpoint behavior, stream events, or provider configuration.
- Run `python -m pytest -q` from `packages/agent`.

Frontend Web:
- Entry points: `packages/web/src/main.tsx`, `packages/web/src/App.tsx`.
- Main routes: `/`, `/project/:id`, `/project/:id/flow`, `/settings`.
- Main project surface: `ChatPanel`, `WorkbenchPanel`, `VersionPanel`, `RunStatusStrip`, and `RunInspector`.
- API domains live in `packages/web/src/api`; chat/SSE/session/build/preview hooks live in `packages/web/src/hooks`.
- Run `npm run lint` and `npm run build` from `packages/web`; use `npx playwright test` for e2e coverage.

CLI:
- Prefer editing TypeScript source in `packages/cli/src` when it exists, then run `npm run build`.
- Commands still only present as compiled JS should be edited carefully in `dist` unless adding a proper TS source migration.
- Run `npm test` from `packages/cli` for the targeted export/stats compatibility tests.

## Tests/Lint
- Backend: `cd packages/backend && PYTHONPATH=.:../agent/src python -m pytest -q`
- Agent: `cd packages/agent && python -m pytest -q`
- Web lint/build: `cd packages/web && npm run lint && npm run build`
- Web e2e: `cd packages/web && npx playwright test`
- CLI: `cd packages/cli && npm test`
- Real provider smoke is opt-in: `cd packages/backend && RUN_REAL_CHAT_ADAPTER_SMOKE=true CHAT_USE_RUN_ADAPTER=true PYTHONPATH=.:../agent/src python -m pytest tests/e2e/test_real_chat_run_adapter_smoke.py -q`

## Conventions / Pitfalls
- Keep `packages/web/src/types/events.ts` aligned with `packages/backend/app/events/types.py` and event model payloads.
- Avoid editing generated/local-only files: `packages/cli/node_modules/`, `packages/backend/venv/`, `packages/backend/.venv/`, `packages/agent/.venv/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `*.db`, `instant-coffee-output/`, `packages/web/dist/`, and Playwright test output unless the task is specifically about those artifacts.
- `python -m app.db.migrations` is not a CLI entry point; DB init/migration helpers run from FastAPI startup.
- `POST /api/sessions/{session_id}/rollback` is legacy version rollback. Agent turn rollback uses `/api/sessions/{session_id}/agent/rollback`.
- `RUN_API_ENABLED`, `CHAT_USE_RUN_ADAPTER`, `TOOL_POLICY_*`, CORS settings, DB/output settings, and model/provider env vars are defined in `packages/backend/app/config.py`.
- README, `CLAUDE.md`, and `docs/project-summary.md` are the current documentation surfaces. Phase/spec docs are useful for intent, not authoritative file/API layout references.
