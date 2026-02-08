# Optimization Audit

This document captures optimization opportunities spotted during a repo-wide scan.
Each item includes a file reference to speed up implementation. Status is noted
for anything already optimized.

## Backend (Done)

- [x] EventEmitter ring buffer/offset to cap memory and avoid unbounded event retention.
  - packages/backend/app/events/emitter.py
- [x] Token usage aggregation moved to SQL (SUM/GROUP BY).
  - packages/backend/app/services/token_tracker.py
- [x] Message history fetch returns latest N (desc + limit, then reverse).
  - packages/backend/app/services/message.py
  - packages/backend/app/api/chat.py
- [x] EventStore sequence cached per session with dedicated sequence table + migration.
  - packages/backend/app/services/event_store.py
  - packages/backend/app/db/models.py
  - packages/backend/app/db/migrations.py
- [x] Page version retention converted to bulk updates.
  - packages/backend/app/services/page_version.py
- [x] Session events endpoint legacy merge gated to reduce heavy merges.
  - packages/backend/app/api/events.py
- [x] Session list counts batched to reduce per-row queries.
  - packages/backend/app/api/sessions.py
- [x] Product doc history pagination + API support.
  - packages/backend/app/api/product_doc.py
  - packages/backend/app/services/product_doc.py
- [x] Snapshot rollback sets VersionSource.ROLLBACK.
  - packages/backend/app/services/project_snapshot.py
- [x] Added DB indexes for messages/token usage/plan/task/page_versions.
  - packages/backend/app/db/migrations.py

## Backend (Remaining)

- None spotted after latest pass.

## Web (Done)

- [x] SSE event merging incremental + capped history, with batch flush.
  - packages/web/src/hooks/useSSE.ts
- [x] Numeric timestamps stored during normalization to avoid repeated parsing.
  - packages/web/src/hooks/useSSE.ts
  - packages/web/src/components/EventFlow/EventList.tsx
- [x] Task events pre-indexed by task_id (removes O(tasks * events) scan).
  - packages/web/src/components/TaskCard/TaskCardList.tsx
- [x] EventItem/TaskCard memoized to cut redundant rerenders.
  - packages/web/src/components/EventFlow/EventItem.tsx
  - packages/web/src/components/TaskCard/TaskCard.tsx
- [x] usePlan updates target a single task rather than rebuilding the full array.
  - packages/web/src/hooks/usePlan.ts
- [x] DataTab heavy normalization deferred and consolidated to reduce per-update work.
  - packages/web/src/components/custom/DataTab.tsx
- [x] VersionTimeline pinned/regular split uses single-pass partition + memoization.
  - packages/web/src/components/custom/VersionTimeline.tsx
- [x] VersionPanel pinned counts precomputed instead of repeated filters.
  - packages/web/src/components/custom/VersionPanel.tsx
- [x] ProjectPage export success/failed counts computed in a single pass.
  - packages/web/src/pages/ProjectPage.tsx

## Web (Remaining)

- None spotted after latest pass.

## CLI (Remaining)

- SSE parsing logic duplicated for GET/POST streams. Extract a shared parser to reduce maintenance and bugs.
  - packages/cli/dist/utils/api-client.js
- Streaming chat uses GET with query params; long prompts can exceed URL limits. Prefer POST streaming when possible.
  - packages/cli/dist/commands/chat.js
