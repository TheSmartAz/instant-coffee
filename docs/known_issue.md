# Known Issues

## 1) Incomplete or Wrong Page HTML (Fallback Template)

### Symptoms
- Some generated pages contain a minimal HTML template instead of the expected UI.
- The output looks identical across different pages and only includes the user prompt text.
- File size is small (~2–3 KB) compared to normal pages.

### Root Cause
- The Generation Agent requires a complete HTML document to be returned by the model.
- If the model response is missing required tags (e.g., `<html>`, `<body>`) or does not match the expected extraction format, the agent treats it as invalid and falls back to a minimal template.
- This is triggered by:
  - Partial or truncated model responses
  - Responses that include extra text outside the expected HTML markers
  - Provider quirks with streaming or non-HTML output

### Suggested Fix
- Add a strict retry path before falling back:
  - If HTML extraction fails, re-run the request once with a stricter prompt or lower temperature.
- Record fallback usage explicitly:
  - Persist a `fallback_used` flag and a short excerpt of the raw model response in task results for easier diagnosis.

### Relevant Code
- `packages/backend/app/agents/generation.py`:
  - `_extract_html`, `_is_html_complete`, `_fallback_html`

---

## 2) Missing Pages / Stuck "in_progress" Tasks

### Symptoms
- One or more pages never appear in the output folder.
- DB shows `tasks.status = in_progress` with no `completed_at`.
- Export task remains `pending` because dependencies never finish.

### Root Cause
- The multi-page generation executor runs inside the request lifecycle.
- If the client disconnects, the server restarts, or the request is cancelled mid-run, the executor stops without updating task statuses.
- Tasks can remain `in_progress` indefinitely, blocking dependent tasks.

### Suggested Fix
- On request cancellation, explicitly abort the executor and mark running tasks as `aborted`.
- Consider moving the plan execution to a background worker so it survives request cancellation.
- Add a cleanup routine:
  - Any `in_progress` task older than a threshold can be retried or marked failed.

### Relevant Code
- `packages/backend/app/agents/orchestrator.py`:
  - `_run_generation_pipeline` (request-scoped executor)
- `packages/backend/app/executor/parallel.py`:
  - `abort`, task lifecycle handling

---

## 3) Interview Widget and Agent/Tool Events Disappear After Refresh

### Symptoms
- Interview widget contents vanish after a page reload.
- Agent/tool execution logs in the UI do not persist across refresh.
- Only the live SSE stream shows the events; historical data is missing.

### Root Cause
- Frontend event state lives in memory only:
  - `useSSE` stores events in component state and clears on refresh.
  - `useChat` builds agent/tool steps from live SSE only.
- Backend does not persist chat SSE events:
  - `EventEmitter` in `/api/chat` is not wired to `EventStoreService`.
  - `EventStoreService` only stores plan/task events that include `plan_id` or `task_id`.
  - Interview-stage events have no `task_id` and are dropped.

### Suggested Fix
- Persist events on the backend:
  - Wire `EventEmitter` in `/api/chat` with `EventStoreService(db)`.
  - Add a `session_events` table for non-task events (interview, agent lifecycle without task_id).
  - Store events that do not have `task_id` or `plan_id` into `session_events`.
- Provide a historical events API:
  - `GET /api/sessions/{session_id}/events`
  - Returns merged `session_events`, `plan_events`, and `task_events` ordered by timestamp.
- Frontend bootstrap:
  - Load historical events on page load and merge with live SSE.
  - Reconstruct interview widget state from stored interview events.

### Relevant Code
- `packages/backend/app/api/chat.py`:
  - EventEmitter is created without `event_store`
- `packages/backend/app/services/event_store.py`:
  - Drops events without `task_id` or `plan_id`
- `packages/web/src/hooks/useSSE.ts`:
  - In-memory event list only
- `packages/web/src/hooks/useChat.ts`:
  - Builds agent/tool steps from live SSE only

---

## 4) Version Panel Cannot Preview Historical Page Versions (Rollback Only)

### Symptoms
- The version panel shows page versions but only offers “rollback”.
- There is no way to preview an older page version without changing the current version.

### Root Cause
- The page versions API returns metadata only:
  - `GET /api/pages/{page_id}/versions` does not include HTML.
- The preview endpoint always returns the current version only:
  - `GET /api/pages/{page_id}/preview` resolves only `current_version_id`.
- The UI is in “page mode” by default and does not expose the legacy session-version preview flow.

### Suggested Fix
- Add a preview endpoint for a specific page version:
  - `GET /api/pages/{page_id}/versions/{version_id}/preview`
  - Return HTML for that version without changing `current_version_id`.
- Update the Version panel to include a “View” action for page versions that loads the preview.

### Current Capabilities
- Rollback works and is reversible:
  - Rolling back only changes the current pointer; versions are not deleted.
  - You can “roll forward” by rolling back to the latest version again.

### Relevant Code
- `packages/backend/app/api/pages.py`:
  - `/pages/{page_id}/versions`, `/pages/{page_id}/preview`, `/pages/{page_id}/rollback`
- `packages/backend/app/services/page_version.py`:
  - `build_preview`, `rollback`
- `packages/web/src/components/custom/VersionPanel.tsx`:
  - Page mode UI only exposes rollback
