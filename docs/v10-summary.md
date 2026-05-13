# Version 1.0 / v10 Status Summary

Last updated: 2026-05-13

## Overview

The original v10 plan targeted generation reliability, dialogue intelligence, frontend upgrades, deployment export, and analytics. The current codebase implements part of that direction, but the scope shifted toward the embedded `ic` agent, durable run coordination, build/review gating, run observability, and DeepSeek-oriented configuration.

This document is a status snapshot against the old v10 roadmap, not a new plan.

## Current Status By Area

| Area | Original v10 intent | Current status |
| --- | --- | --- |
| Cross-session memory | Persist preferences and analytics | Partially implemented as `project_memory` and context injection; analytics schema/dashboard are not implemented. |
| Token calculation | Exact tiktoken accounting | Not implemented as exact tiktoken flow; token/cost events and tracking exist. |
| Structured HTML generation | Dedicated structured output tool | Partially covered by agent tools and DB-backed write/edit tools; no standalone structured HTML tool matching the original phase doc. |
| Atomic multi-file operations | All-or-nothing batch file writes | Partially covered by DB-backed deferred write/edit/multiedit behavior; full original atomic batch contract is not documented as complete. |
| Provider fallback | Provider fallback chain | Config now defaults to DeepSeek-compatible model settings; legacy OpenAI/Anthropic assumptions are no longer authoritative. Fallback semantics should be verified before claiming original acceptance criteria. |
| Structured compaction | Preserve state during context compression | Agent context compaction callbacks/events exist; original full v10 compaction acceptance criteria are only partially satisfied. |
| AskUser timeout | Graceful degradation on unanswered questions | Ask-user and waiting-input run states exist; timeout/default behavior should be verified before claiming complete. |
| Interview progress UI | Round/total metadata | Interview widget exists; exact v10 progress metadata is not confirmed complete. |
| Richer context injection | Product doc, pages, tokens, resources | Implemented in the embedded engine path for Product Doc, page summaries, memory, mentioned files, and visual references. |
| One-click deployment | Deploy endpoint + history | Not implemented. |
| Analytics service | Persist and query analytics | Not implemented as the original v10 service. |
| Zustand and ProjectPage split | Frontend state/layout refactor | Not implemented. ProjectPage remains the main composed surface. |
| Deploy button and QR sharing | Deployment UX | Not implemented. |
| Data dashboard | Rich data dashboard | Partially implemented through Data tab and app data APIs. |

## Implemented Since Earlier Summaries

### Backend

- `RunCoordinator` for durable implement/build/review/fix/verify lifecycle.
- `BuildRunner` for reusable build execution from persisted pages or fallback state.
- `ReviewService` for deterministic product-doc/page/build review issues.
- `/api/runs` API for create/list/get/resume/cancel/events.
- Deep health check mode through `/health?deep=true`.
- DeepSeek-oriented backend/agent configuration defaults.
- Event types for run lifecycle, verify, tool policy, files changed, context compaction, plan updates, spawned agents, and background tasks.
- Migration support through v12, including active queued/running run uniqueness.

### Agent

- Standalone `ic` package with interactive and prompt modes.
- Tool-calling loop with file, shell, ask-user, think, todo, skill, subagent, parallel subagent, web search, and web fetch tools.
- Project sessions, checkpoints, undo, rollback, branches, Product Doc context, token/cost tracking, and context compaction callbacks.

### Web

- Run Status Strip and Run Inspector.
- Run/build/review/tool-policy handling in chat stream hooks.
- Workbench tabs for preview, code, product doc, and data.
- Playwright coverage for run status inspector and existing upload/data/preview flows.

## Not Implemented Or Still Legacy

- `/api/export`, `/api/sessions/{session_id}/export`, `/api/stats`, `/api/plan`, and `/api/task/...` are compatibility-backed.
- Web task retry/skip and export client calls are legacy compatibility surfaces.
- Node CLI `export` and `stats` are compatibility-backed with TypeScript source/tests; other CLI commands remain legacy.
- One-click deployment, deployment history, QR sharing, and analytics dashboard are not implemented.
- Zustand migration and large ProjectPage split are not implemented.

## Current Verification Commands

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

Real-provider smoke:

```bash
cd packages/backend
RUN_REAL_CHAT_ADAPTER_SMOKE=true CHAT_USE_RUN_ADAPTER=true PYTHONPATH=.:../agent/src python -m pytest tests/e2e/test_real_chat_run_adapter_smoke.py -q
```
