# Instant Coffee Web

Last updated: 2026-05-13

This package is the Vite + React UI for Instant Coffee. It is no longer the stock Vite template.

## Stack

- React 19
- React Router 7
- Vite 7
- TypeScript 5.9
- Tailwind CSS 4
- shadcn/Radix components
- Playwright e2e specs under `src/e2e`

## Routes

- `/`: `HomePage`, project list/search/sort/create/manage/delete.
- `/project/:id`: `ProjectPage`, the main chat + workbench + versions UI.
- `/project/:id/flow`: `ExecutionPage`, the legacy flow/event visualization surface.
- `/settings`: `SettingsPage`, account/model/preferences/runtime settings.

## Main Project Layout

`ProjectPage` is organized as:

- Left: `ChatPanel`
  - chat messages
  - interview widget
  - file/page mentions
  - asset uploads
  - `RunStatusStrip`
  - no Run details drawer or Run Inspector; those ProjectPage surfaces were intentionally removed
- Center: `WorkbenchPanel`
  - `preview`
  - `code`
  - `product-doc`
  - `data`
- Right: `VersionPanel`

## API Client

Primary API client files:

- `src/api/client.ts`
- `src/api/client-core.ts`
- `src/api/domains/*`

Current supported domains include sessions, chat, pages, product docs, snapshots, files, export, build, runs, events, settings, and task compatibility actions.

Known legacy calls still present in the client/UI:

- The execution flow view can record task retry/skip through compatibility routes; these routes do not restore the old task executor.
- Session abort currently uses the compatibility `/api/session/{session_id}/abort` route.

## Events

Frontend event types in `src/types/events.ts` must stay aligned with backend event definitions in `packages/backend/app/events/types.py` and models in `packages/backend/app/events/models.py`.

Current UI handles:

- agent/tool/token/cost events
- product doc, page, version, snapshot, build events
- run lifecycle, phase, heartbeat, cancellation, review, verify, and tool-policy events
- context compaction, files changed, plan updates, spawned agent events

## Scripts

```bash
npm install
npm run dev
npm run lint
npm run build
npm run preview
npx playwright test
```

Set `VITE_API_URL` if the backend is not running at `http://localhost:8000`.

## E2E Specs

Current Playwright specs include:

- `AssetUpload.spec.ts`
- `DataTab.spec.ts`
- `ImageUpload.spec.ts`
- `PreviewBridge.spec.ts`
- `RunStatus.spec.ts`
- `v08DataTabOverhaul.spec.ts`
