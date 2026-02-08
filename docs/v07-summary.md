# Version 0.7 Implementation Summary

## Overview

**Version**: v0.7 - LangGraph 编排 + React SSG 多文件产物 + 场景旅程能力 + 组件一致性 + Mobile Shell 自动修复
**Status**: In Progress
**Start Date**: 2026-02-05
**Completion Date**: TBD

**Complexity normalization**:
- Canonical `complexity`: `simple | medium | complex`
- Manifest/legacy values map as: `checklist → simple`, `standard → medium`, `extended → complex`

## Implementation Progress

### Database Phases

| Phase ID | Name | Status | Completed Date |
|----------|------|--------|----------------|
| v07-D1 | Graph State Schema Extension | ✅ Complete | 2026-02-05 |

### Backend Phases

| Phase ID | Name | Status | Completed Date |
|----------|------|--------|----------------|
| v07-B1 | LangGraph Orchestration Skeleton | ✅ Complete | 2026-02-05 |
| v07-B2 | Scene/Journey Capabilities | ✅ Complete | 2026-02-05 |
| v07-B3 | Component Registry Node | ✅ Complete | 2026-02-05 |
| v07-B4 | React SSG Build Pipeline | ✅ Complete | 2026-02-05 |
| v07-B5 | Mobile Shell Auto-fix | ✅ Complete | 2026-02-05 |
| v07-B6 | Asset Registry Service | ✅ Complete | 2026-02-05 |
| v07-B7 | Aesthetic Scoring | ✅ Complete | 2026-02-05 |
| v07-B8 | API Endpoints | ✅ Complete | 2026-02-05 |

### Frontend Phases

| Phase ID | Name | Status | Completed Date |
|----------|------|--------|----------------|
| v07-F1 | Asset Upload UI | ✅ Complete | 2026-02-05 |
| v07-F2 | Data Tab Scene Classification | ✅ Complete | 2026-02-05 |
| v07-F3 | Aesthetic Score Display | ✅ Complete | 2026-02-05 |
| v07-F4 | Build Status UI | ✅ Complete | 2026-02-05 |

### Output/Generated Phases

| Phase ID | Name | Status | Completed Date |
|----------|------|--------|----------------|
| v07-O1 | React SSG Template Project | ✅ Complete | 2026-02-05 |

---

## Phase Details

### v07-D1: Graph State Schema Extension

**Status**: ✅ Complete
**Implementation Date**: 2026-02-05

**Files Modified/Created**:
- `packages/backend/app/db/models.py`
- `packages/backend/app/schemas/session_metadata.py`
- `packages/backend/app/db/migrations.py`
- `packages/backend/app/services/state_store.py`
- `packages/backend/app/api/sessions.py`
- `packages/backend/app/schemas/__init__.py`
- `packages/backend/app/db/__init__.py`
- `packages/backend/tests/test_state_store_service.py`

**Features Implemented**:
- Extend Session model with graph_state, build_status, build_artifacts, aesthetic_scores.
- Update SessionMetadata schema with build status + graph state fields.
- Add migrations to introduce new JSON columns with safe defaults.
- Implement state persistence service for save/load/clear.
- Add session metadata CRUD endpoints for graph state + build status updates.

**Acceptance Criteria**:
- [x] Session model includes new columns with backward compatibility.
- [x] Metadata schema validates graph_state and build_status enums.
- [x] Migration runs on existing DB without data loss.
- [x] State save/load/clear works for large JSON payloads.

### v07-B1: LangGraph Orchestration Skeleton

**Status**: ✅ Complete
**Implementation Date**: 2026-02-05

**Files Modified/Created**:
- `packages/backend/app/graph/__init__.py`
- `packages/backend/app/graph/state.py`
- `packages/backend/app/graph/nodes/__init__.py`
- `packages/backend/app/graph/nodes/base.py`
- `packages/backend/app/graph/nodes/brief.py`
- `packages/backend/app/graph/nodes/component_registry.py`
- `packages/backend/app/graph/nodes/generate.py`
- `packages/backend/app/graph/nodes/aesthetic_scorer.py`
- `packages/backend/app/graph/nodes/refine.py`
- `packages/backend/app/graph/nodes/render.py`
- `packages/backend/app/graph/graph.py`
- `packages/backend/app/graph/retry.py`
- `packages/backend/app/graph/orchestrator.py`
- `packages/backend/app/api/chat.py`
- `packages/backend/app/config.py`
- `packages/backend/requirements.txt`
- `packages/backend/tests/test_langgraph_skeleton.py`

**Features Implemented**:
- Added LangGraph dependency and GraphState TypedDict covering workflow fields.
- Defined node contracts and stubs for brief/style/component/generate/aesthetic/refine/render.
- Built StateGraph with conditional edges for aesthetic scoring and refine loop.
- Added retry wrapper with max retries and error state propagation.
- Feature-flagged LangGraph execution with fallback to legacy orchestrator.

**Acceptance Criteria**:
- [x] GraphState includes all required fields and types.
- [x] Node contracts align with spec input/output expectations.
- [x] Graph compiles with "brief" entry point and END exit.
- [x] Conditional routing works for score/refine branches.
- [x] Retry increments and sets failed build_status on max retries.
- [x] Feature flag toggles LangGraph vs legacy with SSE preserved.

**Implementation Notes**:
- GraphState follows the spec 6.1 definition, including `aesthetic_enabled` and `aesthetic_suggestions`.

### v07-B2: Scene/Journey Capabilities

**Status**: ✅ Complete
**Implementation Date**: 2026-02-05

**Files Modified/Created**:
- `packages/backend/app/services/scenario_detector.py`
- `packages/backend/app/schemas/scenario.py`
- `packages/backend/app/schemas/product_doc.py`
- `packages/backend/app/agents/scene_prompts.py`
- `packages/backend/app/agents/classifier.py`
- `packages/backend/app/agents/product_doc.py`
- `packages/backend/app/services/product_doc.py`
- `packages/backend/app/services/data_protocol.py`
- `packages/backend/app/services/export.py`
- `packages/backend/app/services/skills/__init__.py`
- `packages/backend/app/services/skills/manifests/flow-travel-v1.json`
- `packages/backend/app/services/skills/manifests/flow-manual-v1.json`
- `packages/backend/app/services/skills/manifests/flow-kanban-v1.json`
- `packages/backend/app/services/skills/contracts/travel.json`
- `packages/backend/app/services/skills/contracts/manual.json`
- `packages/backend/app/services/skills/contracts/kanban.json`

**Features Implemented**:
- Scenario detection with keyword rules + confidence scoring (fallback keeps product_type unset when low confidence).
- Pydantic data models for ecommerce/travel/manual/kanban/landing entities (Appendix A aligned).
- ProductDoc schema updated with `data_model` and scene-aware product_type handling.
- Scene-specific LLM prompts with structured JSON output examples.
- Added first-class skill manifests + state contracts for travel/manual/kanban to avoid legacy mapping.
- Data protocol defaults extended for new scenes.

**Acceptance Criteria**:
- [x] Detects five scenarios with confidence and fallback.
- [x] Data models match spec entity definitions and relations.
- [x] ProductDoc includes product_type/complexity/page role fields.
- [x] Prompts yield valid JSON with scene relations.

**Notes**:
- `booking`/`dashboard` remain as legacy types for compatibility, but travel/manual/kanban are first-class skills now.
- Backend dependencies are pinned via `requirements.lock` (uv) to avoid Python 3.12/pydantic conflicts.

### v07-B3: Component Registry Node

**Status**: ✅ Complete
**Implementation Date**: 2026-02-05

**Files Modified/Created**:
- `packages/backend/app/schemas/component.py`
- `packages/backend/app/agents/component_registry.py`
- `packages/backend/app/agents/prompts.py`
- `packages/backend/app/agents/__init__.py`
- `packages/backend/app/graph/state.py`
- `packages/backend/app/graph/nodes/component_registry.py`
- `packages/backend/app/services/component_validator.py`
- `packages/backend/app/graph/nodes/generate.py`
- `packages/backend/tests/test_component_registry.py`

**Features Implemented**:
- Component registry schema with tokens, props, variants, slots + token normalization helper.
- LLM-backed component registry generation gated by `USE_LANGGRAPH` + API key, with fallback to default component library.
- Validator with nested checks and fuzzy auto-fix for unknown components.
- Generate node integration enforcing registry consistency and auto-fix fallback.
- Hash-based registry cache (`component_registry_hash`) computed from product_doc/pages/style_tokens.

**Acceptance Criteria**:
- [x] ComponentRegistry matches spec and includes design tokens.
- [x] Registry covers all page components per scenario (default library provides full coverage).
- [x] Validator returns errors and auto-fix suggestions.
- [x] Generate node blocks invalid schemas or fixes them.

**Implementation Notes**:
- LLM output is merged into the default component library to preserve runtime mappings.
- Registry regeneration is skipped when the input hash matches cached `component_registry_hash`.

### v07-B4: React SSG Build Pipeline

**Status**: ✅ Complete
**Implementation Date**: 2026-02-05

**Files Modified/Created**:
- `packages/backend/app/renderer/__init__.py`
- `packages/backend/app/renderer/builder.py`
- `packages/backend/app/renderer/file_generator.py`
- `packages/backend/app/graph/nodes/render.py`
- `packages/backend/app/api/build.py`
- `packages/backend/app/api/__init__.py`
- `packages/backend/app/main.py`
- `packages/backend/tests/test_renderer_builder.py`

**Features Implemented**:
- ReactSSGBuilder for template copy, npm install/build, dist output, and mobile shell post-processing.
- Schema file generator for schemas/tokens/registry/assets + page component stubs.
- Render node that updates build_status/build_artifacts with timestamps + error handling.
- Build status API for trigger/status/results (async build + persisted artifacts).

**Acceptance Criteria**:
- [x] Template copied and cleaned per build.
- [x] npm install and npm run build succeed.
- [x] JSON data files are valid and parseable.
- [x] Build status transitions pending → building → success/failed.
- [x] Build API returns status and artifacts.

**Implementation Notes**:
- Build artifacts are written under `~/.instant-coffee/sessions/{session_id}/dist`.
- Build progress is emitted as Task events (task_id: `build:{session_id}`).

### v07-B5: Mobile Shell Auto-fix

**Status**: ✅ Complete
**Implementation Date**: 2026-02-05

**Files Modified/Created**:
- `packages/backend/app/services/mobile_shell.py`
- `packages/backend/app/services/export.py`
- `packages/backend/app/cli/__init__.py`
- `packages/backend/app/cli/mobile_shell_cli.py`
- `packages/backend/requirements.txt`
- `packages/backend/tests/test_mobile_shell.py`

**Features Implemented**:
- ensure_mobile_shell post-processor to inject viewport, #app.page, and CSS.
- Mobile validation rules with auto-fix support.
- Export pipeline integration to patch generated HTML.
- CLI tool for validation and in-place fixes.

**Acceptance Criteria**:
- [x] Viewport meta tag injected with correct content.
- [x] #app.page container and max-width constraints enforced.
- [x] Touch targets meet minimum 44px requirement.
- [x] Validation report lists rule pass/fail results.
- [x] CLI supports --fix for in-place repairs.

**Implementation Notes**:
- Mobile shell post-processing now runs inside `ReactSSGBuilder` for Vite build output.
- `ExportService` still applies mobile shell for legacy HTML exports.

### v07-B6: Asset Registry Service

**Status**: ✅ Complete
**Implementation Date**: 2026-02-05

**Files Modified/Created**:
- `packages/backend/app/schemas/asset.py`
- `packages/backend/app/schemas/style_tokens.py`
- `packages/backend/app/services/asset_registry.py`
- `packages/backend/app/services/style_extractor.py`
- `packages/backend/app/graph/__init__.py`
- `packages/backend/app/graph/nodes/__init__.py`
- `packages/backend/app/graph/nodes/style_extractor.py`
- `packages/backend/tests/test_asset_registry.py`
- `packages/backend/tests/test_style_extractor.py`
- `packages/backend/requirements.txt`

**Features Delivered**:
- Asset schemas and registry with typed asset categories.
- AssetRegistryService for session-scoped storage and URL mapping.
- Style extractor with Vision API and rule-based fallback.
- Style extractor node to inject style_tokens into graph state.

**Acceptance Criteria**:
- [x] Asset types include logo/style_ref/background/product_image.
- [x] Assets stored under session-scoped paths with stable URLs.
- [x] Image dimensions captured in AssetRef.
- [x] Style extraction returns tokens or fallback safely.
- [x] Node handles no style references gracefully.

**Implementation Notes**:
- Added a minimal `graph` package and node stub ahead of v07-B1; LangGraph skeleton should merge or replace this later.
- Introduced v07 `StyleTokens` schema (spec 9.2) alongside existing v06 style reference tokens; integration will need a mapping/unification step.

### v07-B7: Aesthetic Scoring

**Status**: ✅ Complete
**Implementation Date**: 2026-02-05

**Files Modified/Created**:
- `packages/backend/app/schemas/aesthetic.py`
- `packages/backend/app/services/aesthetic_scorer.py`
- `packages/backend/app/graph/nodes/aesthetic_scorer.py`
- `packages/backend/app/graph/nodes/generate.py`
- `packages/backend/app/config.py`
- `packages/backend/tests/test_aesthetic_scoring_v07.py`
- `packages/backend/tests/test_langgraph_aesthetic_flow.py`

**Features Implemented**:
- Aesthetic scoring schema with 6 dimensions, thresholds, and suggestions.
- LLM-based scoring agent with robust parsing, retry attempts, and fallbacks.
- Auto-fix for spacing and mobile touch targets applied to page schemas.
- Aesthetic scorer node selects a primary page schema, stores scores in graph state, and emits `aesthetic_score` SSE events when a page exists.
- Feature flag and thresholds configurable via settings (default disabled in `.env.example`).

**Acceptance Criteria**:
- [x] Scores returned for all six dimensions.
- [x] Suggestions include severity and auto-fixable flag.
- [x] Auto-fix updates schema for supported fixes.
- [x] Node runs only when enabled and scenario requires it.
- [x] Feature flag defaults to false.

**Implementation Notes**:
- Generate node now syncs page records from LangGraph schemas so `aesthetic_score` can resolve `page_id` before emitting.
- Scores are persisted to session metadata via LangGraph state persistence, enabling UI reloads.

### v07-B8: API Endpoints

**Status**: ✅ Complete
**Implementation Date**: 2026-02-05

**Files Modified/Created**:
- `packages/backend/app/api/assets.py`
- `packages/backend/app/api/schemas.py`
- `packages/backend/app/api/build.py`
- `packages/backend/app/api/preview.py`
- `packages/backend/app/api/__init__.py`
- `packages/backend/app/main.py`
- `packages/backend/app/services/asset_registry.py`
- `packages/backend/app/events/types.py`
- `packages/backend/app/events/models.py`
- `packages/backend/app/events/emitter.py`
- `packages/backend/app/graph/graph.py`
- `packages/backend/app/graph/orchestrator.py`
- `packages/backend/app/graph/state.py`
- `packages/backend/app/renderer/builder.py`
- `packages/web/src/types/events.ts`

**Features Implemented**:
- Asset upload/list/detail/delete endpoints (multipart), asset type filtering, 10MB cap, and metadata lookup.
- Session-scoped asset static serving via `/assets`.
- Build trigger/status/logs/cancel endpoints with async jobs, subprocess cancellation, and build log persistence.
- Build SSE stream endpoint `/api/sessions/{id}/build/stream` with keepalive for real-time progress.
- Build preview hosting endpoints `/preview/{session_id}/{path}` and share redirect `/share/{session_id}` for SSG dist output.
- Schema endpoints for page schemas, component registry, and style tokens (from graph_state).
- SSE workflow/build events for LangGraph nodes + build lifecycle with progress payloads.

**Implementation Notes**:
- Build status polling does not include progress fields; progress is surfaced via `build_progress` SSE events.
- Build cancellation maps to `failed` because `BuildStatus` has no `cancelled` state.
- Workflow events emit only in LangGraph path; legacy orchestrator does not emit new workflow events.
- Asset upload supports multi-file; the UI currently posts single files.

**Acceptance Criteria**:
- [x] Multipart asset upload updates registry.
- [x] Build trigger starts async job and status polls.
- [x] Schema endpoints return full and per-page schemas.
- [x] SSE events emit workflow/progress/error payloads.
- [x] New routers registered without conflicts.

### v07-F1: Asset Upload UI

**Status**: ✅ Complete
**Implementation Date**: 2026-02-05

**Files Modified/Created**:
- `packages/web/src/components/custom/ChatInput.tsx`
- `packages/web/src/components/custom/AssetTypeSelector.tsx`
- `packages/web/src/components/custom/AssetThumbnail.tsx`
- `packages/web/src/components/custom/ChatMessage.tsx`
- `packages/web/src/components/custom/ChatPanel.tsx`
- `packages/web/src/hooks/useChat.ts`
- `packages/web/src/lib/assetStorage.ts`
- `packages/web/src/api/assets.ts`
- `packages/web/src/api/client.ts`
- `packages/web/src/pages/ProjectPage.tsx`
- `packages/web/src/types/index.ts`

**Features Implemented**:
- Upload button + asset type selector dialog in ChatInput.
- Client-side validation for PNG/JPEG/WebP/SVG; 10MB limit for uploads.
- Upload progress indicator + toast errors.
- Asset thumbnails with type badges + view/download actions in chat.
- Asset state persisted per session via localStorage.
- Asset upload E2E coverage with mocked API + UI selectors.

**Notes / Blockers**:
- Upload now succeeds via v07-B8 asset endpoints (`/api/sessions/{id}/assets`).
- Asset removal currently only affects local state; backend delete exists but UI does not call it yet.

**Acceptance Criteria**:
- [x] Upload button opens file picker and type selector.
- [x] Asset type selection persists for the upload.
- [x] Upload progress and errors displayed.
- [x] Thumbnails render with type badges.
- [x] Uploaded assets persist across refresh (local storage; server persistence now available).
- [x] Tests cover selector render + upload flow.

### v07-F2: Data Tab Scene Classification

**Status**: ✅ Complete
**Implementation Date**: 2026-02-05

**Files Modified/Created**:
- `packages/web/src/components/custom/DataTab.tsx`
- `packages/web/src/types/events.ts`
- `packages/web/src/hooks/usePreviewBridge.ts`
- `packages/backend/app/utils/product_doc.py`
- `packages/backend/app/services/data_protocol.py`

**Features Implemented**:
- Scene selector with event filtering in Data Tab.
- Event category mapping with labels/icons/colors.
- Grouped event display with timestamps and expand/collapse.
- Data store bridge updates to include scene type + typed payloads.
- Preview injector provides product type for scene inference.

**Acceptance Criteria**:
- [x] Scene selector visible with "All Events" option.
- [x] Events filter and group correctly by scene.
- [x] Icons/colors applied per event type.
- [x] Scene selection persists across reloads.
- [x] Events include scene type from preview bridge.

**Notes / Blockers**:
- `useDataStore` hook does not exist; scene-aware parsing is handled in `usePreviewBridge`.
- Data client event names still include legacy types (e.g. `submit_order`); UI normalizes and falls back when labels are missing.

### v07-F3: Aesthetic Score Display

**Status**: ✅ Complete
**Implementation Date**: 2026-02-05

**Files Modified/Created**:
- `packages/web/src/types/aesthetic.ts`
- `packages/web/src/components/ui/AestheticScore.tsx`
- `packages/web/src/components/custom/AestheticScoreCard.tsx`
- `packages/web/src/hooks/useAestheticScore.ts`
- `packages/web/src/hooks/useChat.ts`
- `packages/web/src/components/custom/PreviewPanel.tsx`
- `packages/web/src/components/custom/WorkbenchPanel.tsx`
- `packages/web/src/pages/ProjectPage.tsx`
- `packages/web/src/types/events.ts`
- `packages/web/src/api/client.ts`

**Features Implemented**:
- Aesthetic score card with overall score, dimension breakdown, and suggestions.
- Visual score components (gauge + bars) with clear pass/fail states.
- Preview panel integration with a collapsible score section and empty states.
- SSE event handling for `aesthetic_score` updates via a custom window event.
- Metadata preload from `/api/sessions/{id}/metadata` to persist scores across refreshes.

**Acceptance Criteria**:
- [x] Overall score and six dimensions render with color coding.
- [x] Pass/fail status visible.
- [x] Suggestions expandable with severity styling.
- [x] Preview panel shows loading/empty states.
- [x] SSE events update score state reliably.
- [x] Latest score loads from session metadata on refresh.

### v07-F4: Build Status UI

**Status**: ✅ Complete
**Implementation Date**: 2026-02-05

**Files Modified/Created**:
- `packages/web/src/components/custom/BuildStatusIndicator.tsx`
- `packages/web/src/components/custom/PreviewPanel.tsx`
- `packages/web/src/components/custom/WorkbenchPanel.tsx`
- `packages/web/src/hooks/useBuildStatus.ts`
- `packages/web/src/hooks/useSSE.ts`
- `packages/web/src/hooks/useChat.ts`
- `packages/web/src/pages/ProjectPage.tsx`
- `packages/web/src/types/build.ts`
- `packages/web/src/api/client.ts`
- `packages/backend/app/api/build.py`

**Features Implemented**:
- Build status indicator with spinner, retry, cancel, and elapsed time.
- Progress bar with step/percent/message from build SSE.
- Preview panel integration with disabled iframe + placeholder during builds.
- Build lifecycle updates via dedicated build SSE stream (with keepalive).
- Build API integration for start/cancel + status fallback.
- Pages list and selector after build completion.

**Acceptance Criteria**:
- [x] All build states visually distinct.
- [x] Progress updates in real time from SSE.
- [x] Preview reloads after successful build.
- [x] Failed builds show error + retry.
- [x] Page list appears on success with selection support.

### v07-O1: React SSG Template Project

**Status**: ✅ Complete
**Implementation Date**: 2026-02-05

**Files Modified/Created**:
- `packages/backend/app/renderer/templates/react-ssg/`
- `packages/backend/app/renderer/templates/react-ssg/package.json`
- `packages/backend/app/renderer/templates/react-ssg/vite.config.ts`
- `packages/backend/app/renderer/templates/react-ssg/tailwind.config.js`
- `packages/backend/app/renderer/templates/react-ssg/postcss.config.js`
- `packages/backend/app/renderer/templates/react-ssg/tsconfig.json`
- `packages/backend/app/renderer/templates/react-ssg/index.html`
- `packages/backend/app/renderer/templates/react-ssg/src/main.tsx`
- `packages/backend/app/renderer/templates/react-ssg/src/App.tsx`
- `packages/backend/app/renderer/templates/react-ssg/src/index.css`
- `packages/backend/app/renderer/templates/react-ssg/src/components/*.tsx`
- `packages/backend/app/renderer/templates/react-ssg/src/lib/schema-renderer.tsx`
- `packages/backend/app/renderer/templates/react-ssg/src/lib/data-store.ts`
- `packages/backend/app/renderer/templates/react-ssg/src/types.ts`
- `packages/backend/app/renderer/templates/react-ssg/src/pages/_template.tsx`
- `packages/backend/app/renderer/templates/react-ssg/src/pages/index.tsx`
- `packages/backend/app/renderer/templates/react-ssg/scripts/prerender.ts`

**Features Implemented**:
- Template directory structure with data/pages/components/lib/public assets.
- Vite + Tailwind + TS config for SSG build output.
- Core app shell that reads schema/token/assets JSON (bundled + runtime fetch fallback).
- 20 component IDs mapped to the pre-built React component library with schema-driven props.
- Schema renderer with safe bindings, repeats, conditionals, and asset resolution.
- LocalStorage data store with event logging and postMessage bridge.
- Page templates for dynamic slug routing and mobile shell styling.
- Prerender script to emit `dist/index.html` and `dist/pages/{slug}/index.html`.

**Acceptance Criteria**:
- [x] Template installs and builds via npm successfully.
- [x] SSG build outputs dist/index.html and per-page HTML.
- [x] Components render with Tailwind styling and typed props.
- [x] Schema renderer supports bindings, repeats, and conditionals.
- [x] Data store persists state across pages and refresh.
- [x] Page templates render schema-defined component trees.
