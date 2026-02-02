# Version 0.4 Implementation Summary

## Overview

**Version**: v0.4 - Multi-Page Generation + Product Doc + Workbench
**Status**: ✅ Complete (All 18 phases done)
**Start Date**: 2026-02-01
**Completion Date**: 2026-02-02

## Implementation Progress

### Database Phases

| Phase ID | Name | Status | Completed Date |
|----------|------|--------|----------------|
| D1 | ProductDoc & Page Schema | ✅ Complete | 2026-02-01 |

### Backend Phases

| Phase ID | Name | Status | Completed Date |
|----------|------|--------|----------------|
| B1 | ProductDoc Service | ✅ Complete | 2026-02-01 |
| B2 | Page & PageVersion Service | ✅ Complete | 2026-02-01 |
| B3 | ProductDoc Agent | ✅ Complete | 2026-02-01 |
| B4 | Sitemap Agent & AutoMultiPageDecider | ✅ Complete | 2026-02-01 |
| B5 | Orchestrator Update | ✅ Complete | 2026-02-01 |
| B6 | GenerationAgent Update | ✅ Complete | 2026-02-01 |
| B7 | RefinementAgent Update | ✅ Complete | 2026-02-01 |
| B8 | Files API (Code Tab Backend) | ✅ Complete | 2026-02-01 |
| B9 | Chat API Update | ✅ Complete | 2026-02-01 |
| B10 | Export Service Update | ✅ Complete | 2026-02-01 |

### Frontend Phases

| Phase ID | Name | Status | Completed Date |
|----------|------|--------|----------------|
| F1 | ProductDocPanel Component | ✅ Complete | 2026-02-01 |
| F2 | PreviewPanel Multi-Page Enhancement | ✅ Complete | 2026-02-02 |
| F3 | CodePanel Component | ✅ Complete | 2026-02-02 |
| F4 | WorkbenchPanel (Three-Tab Container) | ✅ Complete | 2026-02-02 |
| F5 | VersionPanel Update for Page Mode | ✅ Complete | 2026-02-02 |
| F6 | Chat & Event Integration | ✅ Complete | 2026-02-02 |
| F7 | ProjectPage Layout Update | ✅ Complete | 2026-02-02 |

---

## Completed Phases Details

### D1: ProductDoc & Page Schema ✅

**Implementation Date**: 2026-02-01

**Files Modified/Created**:
- `packages/backend/app/db/models.py` - Added ProductDoc, Page, PageVersion models with relationships, constraints, and validation
- `packages/backend/app/db/migrations.py` - Added manual migrate/downgrade helpers for v04 tables
- `packages/backend/app/db/data_migration_v04.py` - Idempotent data migration for existing sessions
- `packages/backend/app/db/__init__.py` - Exported new models and migration helpers

**Features Implemented**:
- ProductDoc model (UUID string primary key, unique session_id, JSON structured data, status enum)
- Page model (slug validation, unique session+slug, current_version pointer)
- PageVersion model (unique page+version, HTML storage, version metadata)
- Session relationships for product_doc and pages
- Manual table creation/drop helpers for the v04 tables
- Data migration to seed ProductDoc + default index page + PageVersion v1

**Acceptance Criteria Met**:
- [x] ProductDoc model defined with required fields and status enum
- [x] Unique constraint on ProductDoc.session_id
- [x] Page model defined with required fields and slug validation
- [x] Unique constraint on (session_id, slug)
- [x] PageVersion model defined with required fields
- [x] Unique constraint on (page_id, version)
- [x] Data migration script is idempotent and handles missing versions

---

### B1: ProductDoc Service ✅

**Implementation Date**: 2026-02-01

**Files Modified/Created**:
- `packages/backend/app/schemas/product_doc.py` - Added ProductDoc structured data models and API response schema
- `packages/backend/app/schemas/__init__.py` - Exported ProductDoc schemas
- `packages/backend/app/services/product_doc.py` - Added ProductDocService CRUD, structured validation, status transitions, and event emission
- `packages/backend/app/api/product_doc.py` - Added `GET /api/sessions/{id}/product-doc` endpoint
- `packages/backend/app/api/__init__.py` - Registered ProductDoc router
- `packages/backend/app/main.py` - Included ProductDoc router in app
- `packages/backend/app/events/types.py` - Added ProductDoc event types
- `packages/backend/app/events/models.py` - Added ProductDoc event payload models
- `packages/backend/app/events/emitter.py` - Included ProductDoc events in emitter union
- `packages/web/src/types/events.ts` - Added ProductDoc SSE event types

**Features Implemented**:
- ProductDocService CRUD with status transition validation (draft → confirmed → outdated)
- Structured data validation + partial merge on updates
- ProductDoc GET endpoint with response schema
- SSE events for generated/updated/confirmed/outdated lifecycle changes
- Frontend event typing kept in sync

**Acceptance Criteria Met**:
- [x] CRUD methods work correctly
- [x] Invalid status transitions are rejected
- [x] Structured validation errors are raised
- [x] Endpoint returns ProductDoc or 404
- [x] Events emitted with session/doc identifiers

---

### B4: Sitemap Agent & AutoMultiPageDecider ✅

**Implementation Date**: 2026-02-01

**Files Modified/Created**:
- `packages/backend/app/agents/multipage_decider.py` - AutoMultiPageDecider + confidence scoring + decision event emission
- `packages/backend/app/agents/sitemap.py` - SitemapAgent generation + validation + fallback handling
- `packages/backend/app/agents/prompts.py` - Added sitemap system prompt
- `packages/backend/app/agents/__init__.py` - Exported sitemap/decider utilities
- `packages/backend/app/schemas/sitemap.py` - Sitemap output Pydantic models + constraints
- `packages/backend/app/schemas/__init__.py` - Exported sitemap schemas
- `packages/backend/app/utils/style.py` - Global style token generation + color parsing
- `packages/backend/app/utils/__init__.py` - Exported style helpers
- `packages/backend/app/events/types.py` - Added multipage decision + sitemap event types
- `packages/backend/app/events/models.py` - Added event payload models
- `packages/backend/app/events/emitter.py` - Included sitemap events in emitter union
- `packages/web/src/types/events.ts` - Added frontend event typings

**Features Implemented**:
- AutoMultiPageDecider with confidence scoring (pages/features/keywords/sections)
- Decision routing (single/multi/suggest) with reasons and optional suggestions
- SitemapAgent generation with LLM prompt, JSON parsing, schema validation
- Fallback sitemap generation (index page enforced) on invalid LLM output
- Explicit multi-page enforcement ensures at least two pages when user overrides to multi-page
- Global style token generation from design direction (color + font mapping)
- SSE events for multipage decision and sitemap proposal

**Acceptance Criteria Met**:
- [x] Decision logic returns consistent results
- [x] Confidence scores are explainable and bounded
- [x] Sitemap includes all pages from ProductDoc (or fallback)
- [x] Navigation structure is complete and ordered
- [x] Explicit multi-page override enforces a minimum page count

---

### B5: Orchestrator Update ✅

**Implementation Date**: 2026-02-01

**Files Modified/Created**:
- `packages/backend/app/agents/orchestrator.py` - ProductDoc-first routing, Plan/Executor pipeline, regeneration flow, sitemap sync
- `packages/backend/app/agents/product_doc.py` - Persist affected pages for regeneration
- `packages/backend/app/services/product_doc.py` - Pending regeneration pages + outdated -> confirmed transition
- `packages/backend/app/db/models.py` - Added `pending_regeneration_pages` to ProductDoc

**Features Implemented**:
- ProductDoc-first routing with Generate Now and confirmation handling
- ProductDoc updates mark status outdated and prompt before regeneration
- Regeneration confirms ProductDoc and re-runs pipeline for affected pages only
- Generation pipeline now creates a Plan and executes via ParallelExecutor
- Sitemap sync keeps pages in sync (create/update/rename/delete)
- Multi-page override parsing (single/multi keywords in EN/ZH) with suggest/confirm flow
- Suggest-multi-page responses emit `multipage_suggested` action when user confirmation is needed

**Acceptance Criteria Met**:
- [x] Routing priority matches spec
- [x] Generate Now triggers pipeline after auto-confirm
- [x] ProductDoc context injected into multi-page generation
- [x] Regeneration is gated by user confirmation
- [x] User can explicitly force single/multi-page generation

---

### B9: Chat API Update ✅

**Implementation Date**: 2026-02-01

**Files Modified/Created**:
- `packages/backend/app/schemas/chat.py` - New ChatRequest/ChatResponse schemas with ProductDoc and preview metadata
- `packages/backend/app/schemas/__init__.py` - Exported chat schemas
- `packages/backend/app/api/chat.py` - Generate Now request flag, enriched response fields, multi-page preview selection, token usage
- `packages/backend/app/agents/orchestrator.py` - Aligned action values for refinement responses
- `packages/backend/tests/test_chat_response_fields.py` - Chat response field coverage

**Features Implemented**:
- `generate_now` accepted in ChatRequest and forwarded to orchestrator
- Chat responses include action, product_doc_updated, affected_pages, active_page_slug, tokens_used
- Preview selection returns the active page HTML (index-first for multi-page) with inline CSS
- SSE stream payloads include the same enriched response fields

**Acceptance Criteria Met**:
- [x] Parameter accepted with default false
- [x] Response fields accurately describe ProductDoc/page actions
- [x] Preview is self-contained and page-aware
- [x] Backward compatible preview_url/preview_html retained

---

### B10: Export Service Update ✅

**Implementation Date**: 2026-02-01

**Files Modified/Created**:
- `packages/backend/app/executor/task_executor.py` - Multi-page export + manifest + site.css
- `packages/backend/app/services/file_tree.py` - Code tab HTML now links to site.css

---

## Maintenance Updates

### Preview Scrollbar Hiding ✅

**Implementation Date**: 2026-02-01

**Files Modified/Created**:
- `packages/backend/app/utils/html.py` - Injected a shared style block to hide scrollbars while preserving scroll
- `packages/backend/app/api/pages.py` - Injected scrollbar-hiding CSS into page preview HTML responses
- `packages/backend/app/api/sessions.py` - Injected scrollbar-hiding CSS into session preview HTML responses
- `packages/web/src/components/custom/PreviewPanel.tsx` - Injected scrollbar-hiding CSS into srcDoc previews

**Features Implemented**:
- All preview HTML (page + session endpoints) now hides scrollbars without disabling scrolling
- srcDoc previews get the same behavior client-side to ensure consistency

**Features Implemented**:
- Export outputs `index.html`, `pages/{slug}.html`, `assets/site.css`, `product-doc.md`
- Export writes `export_manifest.json` with per-page success/failure
- Export HTML links to shared `site.css` while Preview remains inline

**Acceptance Criteria Met**:
- [x] Export layout matches spec structure
- [x] Shared CSS asset emitted
- [x] Manifest generated for page results

### Preview URL + Legacy Mapping Fixes ✅

**Implementation Date**: 2026-02-01

**Files Modified/Created**:
- `packages/backend/app/api/pages.py` - HTML/JSON preview content negotiation; response model inference disabled
- `packages/backend/app/api/sessions.py` - Legacy preview/versions map to Page/PageVersion when available
- `packages/web/src/api/client.ts` - Added `pages.previewUrl()` and JSON `Accept` header for tooling
- `packages/web/src/hooks/usePages.ts` - Use preview_url on page preview ready events
- `packages/web/src/pages/ProjectPage.tsx` - Prefer preview_url with cache-busting in iframe

**Features Implemented**:
- `/api/pages/{page_id}/preview` returns HTML when `Accept: text/html`, JSON otherwise
- Legacy session preview/versions endpoints prioritize Page/PageVersion data, with fallback to legacy Version
- Preview HTML uses ProductDoc global style CSS and cache-busted URLs to avoid stale iframes

**Acceptance Criteria Met**:
- [x] HTML previews render correctly in iframes without JSON leakage
- [x] Legacy preview/versions remain backward compatible
- [x] Global styles apply consistently in preview HTML

### Validator + Export Flow Hardening ✅

**Implementation Date**: 2026-02-01

**Files Modified/Created**:
- `packages/backend/app/generators/mobile_html.py` - Added HTML validator rules and warnings/errors output
- `packages/backend/app/executor/task_executor.py` - Validator tasks report issues without blocking pipeline
- `packages/backend/app/executor/scheduler.py` - Export tasks allowed after failed/blocked dependencies

**Features Implemented**:
- Validator checks: viewport meta, title presence, image alt text, oversized base64 assets, internal link formats
- Validation produces errors/warnings but does not fail the overall generation plan
- Export runs even if validation fails or a dependency is blocked, and manifest records per-page status

**Acceptance Criteria Met**:
- [x] Validation issues are surfaced without aborting export
- [x] Export executes after validator regardless of upstream failures
- [x] Manifest reflects page-level success/failure outcomes

### Interview Summary Rehydration ✅

**Implementation Date**: 2026-02-01

**Files Modified/Created**:
- `packages/web/src/hooks/useSession.ts` - Rebuild interview summary from stored structured payloads

**Features Implemented**:
- Rehydrates `interviewSummary` from `<INTERVIEW_ANSWERS>` on reload
- Replaces raw payload lines with readable status text for chat history

**Acceptance Criteria Met**:
- [x] Interview summaries stay human-readable after refresh
- [x] No raw JSON payload shown in the interview widget

### B2: Page & PageVersion Service ✅

**Implementation Date**: 2026-02-01

**Files Modified/Created**:
- `packages/backend/app/services/page.py` - Added PageService CRUD + slug validation + batch creation
- `packages/backend/app/services/page_version.py` - Added PageVersionService versioning/rollback + preview builder
- `packages/backend/app/api/pages.py` - Added pages CRUD + versions/preview/rollback endpoints
- `packages/backend/app/api/__init__.py` - Registered pages router
- `packages/backend/app/main.py` - Included pages router in app
- `packages/backend/app/schemas/page.py` - Page/PageVersion API schemas + rollback payloads
- `packages/backend/app/schemas/__init__.py` - Exported page schemas
- `packages/backend/app/utils/html.py` - Inline CSS helper for preview HTML
- `packages/backend/app/utils/__init__.py` - Exported HTML helpers
- `packages/backend/app/events/types.py` - Added page event types
- `packages/backend/app/events/models.py` - Added page event payload models
- `packages/backend/app/events/emitter.py` - Included page events in emitter union
- `packages/backend/app/events/__init__.py` - Exported page events
- `packages/backend/app/api/utils.py` - Added page preview URL helper
- `packages/web/src/types/events.ts` - Added frontend event typings
- `packages/backend/tests/test_page_services.py` - Page/PageVersion service unit tests
- `packages/backend/tests/test_pages_api.py` - Pages API integration tests

**Features Implemented**:
- PageService CRUD with slug validation + per-session uniqueness checks
- Batch page creation with duplicate detection and atomic failure behavior
- PageVersionService auto-increment versions and rollback support
- Preview HTML builder with optional inline CSS injection
- Pages API for list/details/versions/preview/rollback (preview supports HTML via `Accept: text/html`; handler disables response model inference)
- SSE events for page created / version created / preview ready
- Frontend event typing aligned with backend events

**Acceptance Criteria Met**:
- [x] CRUD methods work correctly
- [x] Slug validation enforced
- [x] Batch creation works atomically
- [x] Version numbers auto-increment correctly
- [x] Rollback updates current_version_id
- [x] Version history preserved on rollback
- [x] Preview HTML renders without external dependencies when CSS provided
- [x] Events emitted with session/page identifiers
- [x] API endpoints return proper responses
- [x] Global style reflects design direction
- [x] Sitemap output schema validates and enforces limits
- [x] Events emitted for decisions and sitemap proposals

---

### B6: GenerationAgent Update ✅

**Implementation Date**: 2026-02-01

**Files Modified/Created**:
- `packages/backend/app/agents/generation.py` - Added multi-page inputs, navigation/style injection, internal link normalization, and PageVersion persistence
- `packages/backend/app/agents/prompts.py` - Added multi-page generation system prompt
- `packages/backend/app/agents/__init__.py` - Exported multi-page prompt helper
- `packages/backend/app/utils/html.py` - Added navigation HTML builder, CSS link injection, and internal link normalization utilities
- `packages/backend/app/utils/style.py` - Added global style CSS generator for multi-page prompt/context
- `packages/backend/app/utils/__init__.py` - Exported new HTML utilities
- `packages/backend/tests/test_generation_agent.py` - Added multi-page generation + PageVersion persistence test
- `packages/backend/tests/test_html_utils.py` - New unit tests for nav/link utilities
- `packages/backend/tests/test_style_utils.py` - Added global style CSS test

**Features Implemented**:
- GenerationAgent supports multi-page inputs (`page_spec`, `global_style`, `nav`, `product_doc`, `all_pages`)
- Multi-page prompt includes page context, nav, and ProductDoc excerpts
- Navigation HTML injected and active page highlighted
- Internal links normalized to `index.html` / `pages/{slug}.html` with warnings on broken links
- Global style CSS generated for prompts and preview inlining
- PageVersion created for each generated page with events emitted
- Single-page mode remains backward compatible

**Acceptance Criteria Met**:
- [x] New parameters accepted and used
- [x] Single-page mode still works
- [x] Navigation present on all pages with active state
- [x] CSS variables and base styles generated
- [x] Internal links normalized with warnings
- [x] PageVersion created and events emitted

---

### B3: ProductDoc Agent ✅

**Implementation Date**: 2026-02-01

**Files Modified/Created**:
- `packages/backend/app/agents/product_doc.py` - ProductDocAgent generation/update with robust parsing, validation, affected page detection, and persistence hooks
- `packages/backend/app/agents/prompts.py` - Added ProductDoc generate/update prompts with schema examples
- `packages/backend/app/agents/__init__.py` - Exported ProductDocAgent + prompt helpers
- `packages/backend/app/services/product_doc.py` - Added change_summary to update events
- `packages/backend/tests/test_product_doc_agent.py` - Unit/integration tests for ProductDocAgent
- `packages/backend/tests/test_agent_prompts.py` - Prompt wiring coverage

**Features Implemented**:
- ProductDocAgent generate/update methods with token tracking
- Output parsing for Markdown/JSON/message/change summary/affected pages
- Structured validation + schema normalization
- Index page enforcement and fallback Markdown builder
- Persistence through ProductDocService with event emission

**Acceptance Criteria Met**:
- [x] Agent generates valid ProductDoc structure
- [x] Agent updates existing ProductDoc correctly
- [x] Token usage tracked

---

### B8: Files API (Code Tab Backend) ✅

**Implementation Date**: 2026-02-01

**Files Modified/Created**:
- `packages/backend/app/services/file_tree.py` - Added virtual file tree + file content service
- `packages/backend/app/api/files.py` - Added Files API endpoints
- `packages/backend/app/schemas/files.py` - Added Files API response schemas
- `packages/backend/app/utils/style.py` - Added global style normalization + site.css generator
- `packages/backend/app/api/__init__.py` - Registered Files router
- `packages/backend/app/main.py` - Included Files router in app
- `packages/backend/app/schemas/__init__.py` - Exported files schemas
- `packages/backend/tests/test_file_tree_service.py` - File tree service unit tests
- `packages/backend/tests/test_files_api.py` - Files API integration tests
- `packages/backend/tests/test_style_utils.py` - Added site.css generation tests

**Features Implemented**:
- Virtual file tree generation (`index.html`, `pages/*.html`, `assets/site.css`, optional `product-doc.md`)
- File content endpoint with language detection and byte-accurate size
- site.css generated from ProductDoc design direction / global style defaults
- Backwards-compatible index HTML fallback for legacy sessions

**Acceptance Criteria Met**:
- [x] Tree includes all expected files with correct hierarchy
- [x] File sizes calculated from UTF-8 bytes
- [x] File content endpoint returns correct content + language
- [x] Missing files return 404
- [x] Minimal sessions return a valid tree

---

### B7: RefinementAgent Update ✅

**Implementation Date**: 2026-02-01

**Files Modified/Created**:
- `packages/backend/app/agents/refinement.py` - Multi-page refinement interface, target detection, batch refinement, nav preservation, PageVersion creation
- `packages/backend/app/agents/prompts.py` - Refinement prompt updated with ProductDoc/global style/nav context
- `packages/backend/app/utils/html.py` - Navigation extract/replace helpers + nav slug parsing
- `packages/backend/app/utils/__init__.py` - Exported new HTML utilities
- `packages/backend/app/agents/orchestrator.py` - Integrated refinement routing, disambiguation, and batch handling
- `packages/backend/tests/test_refinement_agent.py` - Updated agent tests for new interface
- `packages/backend/tests/test_orchestrator_routing.py` - Updated routing test for refinement integration

**Features Implemented**:
- Page-targeted refinement with ProductDoc/global style context injection
- Disambiguation for ambiguous page references
- Navigation preservation/update logic during refinement
- PageVersion creation with preview event emission
- Batch refinement for site-wide changes

**Acceptance Criteria Met**:
- [x] Page parameter correctly identifies target
- [x] ProductDoc context available in refinement
- [x] Single-page mode still works
- [x] Correct page targeted from message
- [x] Disambiguation returned when ambiguous
- [x] Navigation preserved by default
- [x] Nav updates when needed
- [x] New PageVersion created after refinement
- [x] Events emitted after refinement
- [x] Batch refinement supports multiple pages with failure isolation

---

### F1: ProductDocPanel Component ✅

**Implementation Date**: 2026-02-01

**Files Modified/Created**:
- `packages/web/src/types/index.ts` - Added ProductDoc, ProductDocStructured, ProductDocFeature, DesignDirection, and ProductDocPage types
- `packages/web/src/api/client.ts` - Added `productDocs.get()` API method with 404 handling
- `packages/web/src/hooks/useProductDoc.ts` - Added useProductDoc hook for data fetching, loading states, refresh, and SSE event handling
- `packages/web/src/hooks/useChat.ts` - Added ProductDoc event dispatching for SSE integration
- `packages/web/src/components/custom/ProductDocPanel.tsx` - Added ProductDocPanel component with header, status badge, markdown rendering, loading/empty/error states, and footer guidance

**Features Implemented**:
- ProductDoc types matching backend schema (status enum, structured data, pages array)
- API client method that returns null on 404 (no ProductDoc exists yet)
- Custom hook with data fetching, loading/error states, and manual refresh
- SSE event integration via custom window events (product-doc-event)
- ReactMarkdown rendering with custom components (no typography plugin required)
- Status badges with localized Chinese labels (草稿/已确认/已过期)
- Loading skeleton and empty state with helpful messaging
- Scrollable content area with markdown styling

**Acceptance Criteria Met**:
- [x] Markdown renders correctly with custom styling
- [x] Status badge shows correct state with appropriate colors
- [x] Loading and empty states handled with visual feedback
- [x] Scrollable for long documents
- [x] SSE events trigger refresh (via custom event dispatch)

---

### F2: PreviewPanel Multi-Page Enhancement ✅

**Implementation Date**: 2026-02-02

**Files Modified/Created**:
- `packages/web/src/types/index.ts` - Added Page, PageVersion, PagePreview interfaces
- `packages/web/src/api/client.ts` - Added pages API methods (list, get, getPreview, getVersions, rollback)
- `packages/web/src/components/custom/PageSelector.tsx` - Added horizontal tab bar component for page switching
- `packages/web/src/hooks/usePages.ts` - Added hook for fetching and managing pages state with SSE event handling
- `packages/web/src/hooks/useChat.ts` - Added page event dispatching (page_created, page_version_created, page_preview_ready)
- `packages/web/src/components/custom/PreviewPanel.tsx` - Enhanced for multi-page with PageSelector integration
- `packages/web/src/pages/ProjectPage.tsx` - Integrated multi-page support with page state management

**Features Implemented**:
- PageSelector component with horizontal tab bar, active highlighting, and auto-hide for single page
- usePages hook for fetching pages, managing selection, auto-selecting first page, and SSE event listening
- Pages API client methods matching backend schema ({ pages: [...], total: number })
- PreviewPanel enhanced with optional multi-page props (pages, selectedPageId, onSelectPage, onRefreshPage)
- Page selection prefers `preview_url` (HTML endpoint) with cache-busting; JSON preview still available for tooling
- Page events dispatched via custom window events for real-time updates
- Current page title displayed in PreviewPanel header
- Backward compatible with existing single-page mode

**Acceptance Criteria Met**:
- [x] PageSelector renders for all pages
- [x] Active page highlighted
- [x] Click changes selection
- [x] Hidden for single page
- [x] Pages fetched correctly from API
- [x] Selection state maintained
- [x] Events trigger appropriate updates
- [x] First page auto-selected
- [x] Page switching works smoothly
- [x] Export still works

**Notes**:
- ProjectPage uses manual state management instead of usePages hook directly to avoid circular dependency with loadPagePreview callback
- The usePages hook is still available for other components to use
- Tailwind CSS used for PageSelector styling instead of custom CSS classes
- TypeScript compilation passes with no errors
- PreviewPanel now renders a branded empty state (coffee icon + Instant Coffee) when no preview is available
- ProjectPage no longer seeds preview with fallback HTML; preview starts empty
- Selected page auto-loads its preview once when first available, removing the need for manual refresh
- loadPagePreview validates the preview endpoint before setting iframe src to avoid 404 JSON rendering

---

### F3: CodePanel Component ✅

**Implementation Date**: 2026-02-02

**Files Modified/Created**:
- `packages/web/src/types/index.ts` - Added FileTreeNode and FileContent interfaces
- `packages/web/src/api/client.ts` - Added files API methods (getTree, getContent)
- `packages/web/src/hooks/useFileTree.ts` - Added hook for fetching file tree and content with caching
- `packages/web/src/components/custom/FileTree.tsx` - Added FileTree component with expandable directory structure
- `packages/web/src/components/custom/FileViewer.tsx` - Added FileViewer component with syntax highlighting
- `packages/web/src/components/custom/CodePanel.tsx` - Added CodePanel container component
- `packages/web/package.json` - Added react-syntax-highlighter and @types/react-syntax-highlighter dependencies

**Features Implemented**:
- FileTreeNode and FileContent TypeScript types matching backend schema
- API client methods for fetching file tree and individual file content
- useFileTree hook with state management, content caching, and error handling
- FileTree component with expandable folders, file type icons, and selection highlighting
- FileViewer component with react-syntax-highlighter, line numbers, and language detection
- CodePanel two-pane layout with file tree (left) and viewer (right)
- Loading skeleton and empty states
- Refresh button for reloading file tree
- Support for HTML, CSS, JavaScript, Markdown, and Plain Text files

**Acceptance Criteria Met**:
- [x] Types match backend schema
- [x] API methods work with proper URL encoding
- [x] File tree fetched correctly
- [x] File content fetched on selection
- [x] Content cached to reduce API calls
- [x] Error handling works
- [x] Two-pane layout works
- [x] File selection updates viewer
- [x] Loading state handled
- [x] Syntax highlighting works for HTML/CSS/JS/Markdown
- [x] Line numbers displayed
- [x] Scrollable for long files
- [x] Empty state shown appropriately

**Notes**:
- Used react-syntax-highlighter instead of highlight.js/prism as suggested in plan (React wrapper around highlight.js)
- Backend Files API (B8) was already complete, no backend work needed
- Language field from backend matches expected values: html, css, javascript, markdown, plaintext
- File icons use Lucide React icons with colors by file type
- Content caching reduces redundant API calls when switching between files

---

### F4: WorkbenchPanel (Three-Tab Container) ✅

**Implementation Date**: 2026-02-02

**Files Modified/Created**:
- `packages/web/src/components/custom/WorkbenchPanel.tsx` - Created main container with three-tab navigation
- `packages/web/src/pages/ProjectPage.tsx` - Integrated WorkbenchPanel, added workbenchTab state, added auto-switching logic

**Features Implemented**:
- WorkbenchPanel component with three tabs: Preview (预览), Code (代码), Product Doc (产品文档)
- Tab bar with icons (Eye, Code, FileText from Lucide React) and labels
- Controlled mode via activeTab and onTabChange props
- Integration of PreviewPanel, CodePanel, and ProductDocPanel in respective tabs
- Auto tab switching based on SSE events:
  - `page_created` → switches to Preview tab
  - `page_version_created` → switches to Preview tab
  - `product_doc_generated` → switches to Product Doc tab
  - `product_doc_updated` → switches to Product Doc tab
- Empty state handling for when sessionId is undefined (new project)
- Styled tab bar with active/hover states matching design system

**Acceptance Criteria Met**:
- [x] Three tabs rendered correctly
- [x] Tab switching works
- [x] Correct panel displayed for each tab
- [x] Parent notified of changes
- [x] Preview tab shows PreviewPanel with page selection
- [x] Code tab shows CodePanel with file tree
- [x] Product Doc tab shows ProductDocPanel
- [x] Auto-switch works on relevant events
- [x] User can manually switch tabs
- [x] Tabs look polished with consistent design
- [x] Active state is visually distinct
- [x] Empty state shown when no sessionId

**Notes**:
- WorkbenchPanel preserves the state of individual panels when switching tabs (panels remain mounted)
- Auto-switching is implemented via SSE event listeners in ProjectPage for both page events and product-doc events
- Manual tab switching clears the auto-switch behavior for the current session
- The tab bar uses a bottom border accent color to indicate the active tab
- Panel state preservation means CodePanel file tree and ProductDoc content persist when switching away and back

---

### F5: VersionPanel Update for Page Mode ✅

**Implementation Date**: 2026-02-02

**Files Modified/Created**:
- `packages/web/src/hooks/usePageVersions.ts` - Added hook for fetching page versions with rollback support
- `packages/web/src/components/custom/VersionPanel.tsx` - Updated component to support page-specific version display
- `packages/web/src/pages/ProjectPage.tsx` - Connected VersionPanel to page version data

**Features Implemented**:
- usePageVersions hook with `versions`, `currentVersionId`, `isLoading`, `error`, `revert`, `refresh` return values
- Fetches page versions from `GET /api/pages/{pageId}/versions`
- Rollback via `POST /api/pages/{pageId}/rollback`
- Listens for `page_version_created` events to auto-refresh
- VersionPanel now accepts both legacy session version props and new page mode props
- Page mode displays current page title ("当前页面: {title}")
- Version timeline with version number, relative time (e.g., "2 hours ago"), and description
- Current version highlighted with accent color (solid dot)
- Non-current versions show hollow dot with rollback button
- Empty state ("本版本仅页面有历史") shown in Code/Product Doc tabs
- Confirmation dialog before rollback
- Loading state with spinner during rollback
- Backward compatible with existing session version mode

**Acceptance Criteria Met**:
- [x] New props accepted (pageVersions, currentPageVersionId, onRevertPageVersion, selectedPageTitle, activeTab)
- [x] Existing collapse functionality preserved
- [x] Type safety enforced (TypeScript compilation passes)
- [x] Versions list renders correctly with page title
- [x] Current version highlighted
- [x] Rollback buttons visible for non-current versions
- [x] Empty state shows for Code tab
- [x] Empty state shows for Product Doc tab
- [x] Rollback triggers API call
- [x] Confirmation prevents accidental rollback
- [x] UI updates after success
- [x] Error handling works

**Notes**:
- VersionPanel auto-detects mode based on presence of `activeTab` prop
- Page mode only shows version history in Preview tab
- Collapsed state shows version dots for both modes
- Rollback handler refreshes preview HTML after successful rollback
- Toast notifications shown for success/failure

---

### F6: Chat & Event Integration ✅

**Implementation Date**: 2026-02-02

**Files Modified/Created**:
- `packages/web/src/types/index.ts` - Added ChatAction type, updated ChatResponse and Message interfaces with new fields, added Disambiguation types
- `packages/web/src/hooks/useChat.ts` - Added onTabChange/onPageSelect callbacks, generateNow support, handleActionTabSwitch helper, new SSE event handlers
- `packages/web/src/api/client.ts` - Added generateNow parameter to chat.send and chat.streamUrl
- `packages/web/src/components/custom/ChatMessage.tsx` - Added action/affectedPages/disambiguation props, ProductDoc link buttons, affected pages chips, disambiguation UI
- `packages/web/src/components/custom/ChatPanel.tsx` - Added onTabChange/onDisambiguationSelect props, passed through to ChatMessage
- `packages/web/src/pages/ProjectPage.tsx` - Added onTabChange/onPageSelect callbacks to useChat, onDisambiguationSelect handler in ChatPanel
- `packages/web/src/components/EventFlow/EventItem.tsx` - Added event titles/status/badges for new ProductDoc, multipage, sitemap, and page events
- `packages/web/src/components/EventFlow/EventList.tsx` - Added new event types to phase mode filter

**Features Implemented**:
- ChatAction type: product_doc_generated, product_doc_updated, product_doc_confirmed, pages_generated, page_refined, multipage_suggested, direct_reply
- ChatResponse extended with: active_page_slug, product_doc_updated, affected_pages, action, tokens_used
- Message extended with: action, affectedPages, activePageSlug, disambiguation
- Disambiguation UI for page selection with clickable chips
- generateNow parameter support in chat API
- Auto tab switching based on chat action (product_doc → Product Doc tab, pages → Preview tab)
- Auto page selection when active_page_slug is provided
- SSE event handlers for multipage_decision_made and sitemap_proposed
- Event display for all new event types in Events panel

**Acceptance Criteria Met**:
- [x] New response fields parsed correctly
- [x] State updated appropriately
- [x] No breaking changes to existing behavior
- [x] Generate Now parameter sent correctly
- [x] UI control available for tab switching
- [x] Response handled properly
- [x] All new event types handled
- [x] Events trigger appropriate updates
- [x] Type definitions complete
- [x] Tabs switch appropriately
- [x] User can override
- [x] Not annoyingly repetitive
- [x] ProductDoc messages informative
- [x] Tab link works
- [x] Affected pages shown clearly
- [x] New events displayed
- [x] Events formatted nicely
- [x] Relevant details shown
- [x] Disambiguation options displayed
- [x] Clicking option sends response
- [x] User can also type manually

**Notes**:
- Tab switching coordination uses callbacks instead of direct state manipulation for cleaner separation
- Disambiguation uses clickable Button components instead of plain chips for better UX
- Event display includes status indicators (done/failed/pending) and badges for each event type
- handleActionTabSwitch helper reduces code duplication and provides centralized tab switching logic

---

### F7: ProjectPage Layout Update ✅

**Implementation Date**: 2026-02-02

**Files Modified/Created**:
- `packages/web/src/pages/ProjectPage.tsx` - Refactored to use usePages and useProductDoc hooks, implemented export functionality, fixed type issues
- `packages/web/src/api/client.ts` - Added export API method (api.export.session)
- `packages/web/src/types/index.ts` - Added ExportManifest, ExportPageInfo, ExportAssetInfo types
- `packages/web/src/components/custom/WorkbenchPanel.tsx` - Removed broken imperative handle, fixed type mismatches
- `packages/web/src/components/custom/PreviewPanel.tsx` - Fixed state types for null handling

**Features Implemented**:
- Replaced manual page state management with usePages hook (selectedPageId, pages, selectPage)
- Added useProductDoc hook for ProductDoc state management with auto-tab-switching
- Implemented proper export functionality via api.export.session() with user feedback
- Fixed TypeScript type issues (removed unused variables, fixed null/undefined mismatches)
- Maintained three-column layout (Chat 35%, Workbench flex-1, VersionPanel 48px/256px)
- Export shows toast with success/failed page counts and export directory

**Acceptance Criteria Met**:
- [x] WorkbenchPanel replaces PreviewPanel (already done)
- [x] All three tabs functional (already done)
- [x] State properly managed using hooks
- [x] ProductDoc fetched and auto-switches on events
- [x] Pages fetched correctly with usePages hook
- [x] Page selection works via selectPage callback
- [x] VersionPanel shows correct versions via usePageVersions
- [x] Rollback works (already implemented)
- [x] Empty state for non-preview tabs (already done)
- [x] Chat actions trigger tab switches (already done)
- [x] Page selection works from chat (already done)
- [x] User can override tab selection (already done)
- [x] Preview loads for selected page (already done)
- [x] Loading state shown (already done)
- [x] Error handling works (already done)
- [x] Export triggers correctly with API call
- [x] User gets feedback via toast
- [x] Layout matches spec (three columns maintained)
- [x] TypeScript compilation passes

**Notes**:
- usePages hook manages page state with auto-selection and real-time updates via SSE events
- useProductDoc hook manages product doc state with auto-tab-switching on events
- Export functionality calls POST /api/sessions/{sessionId}/export and displays results
- All type errors in ProjectPage, WorkbenchPanel, and PreviewPanel resolved
- Three-column layout preserved: Chat (35%), Workbench (flex-1), VersionPanel (48px/256px collapsible)

---

## Supporting Changes (Session Work)

These were added to make v04 data migration easy to run in existing environments.

**Backend**:
- `packages/backend/app/config.py` - Added `MIGRATE_V04_ON_STARTUP` flag
- `packages/backend/app/main.py` - Optional migration on startup
- `packages/backend/app/api/migrations.py` - `POST /api/migrations/v04` endpoint
- `packages/backend/app/api/__init__.py` - Router export

**CLI**:
- `packages/cli/dist/commands/migrate.js` - `instant-coffee migrate-v04` command
- `packages/cli/dist/commands/index.js` - Command registration

---

## Notes & Conflicts With Plan

- Alembic migrations are not used in this repo. The plan references
  `packages/backend/app/db/migrations/versions/...`, but the repo has
  `packages/backend/app/db/migrations.py` as a file. A migrations package cannot
  coexist with that filename, so manual helpers were added instead.
- The plan assumes Postgres features (`gen_random_uuid()`, `JSONB`, regex CHECK).
  The repo defaults to SQLite, so UUID generation and slug validation are enforced
  in Python, and JSONB is mapped to JSON.
- The B1 spec shows async methods and UUID types in the ProductDocService interface,
  but the codebase uses synchronous service methods and string UUIDs, so the
  implementation follows the repo conventions.
- B4 currently generates sitemap/decision data directly from `ProductDoc.structured`
  (no service dependency). Orchestrator wiring remains in B5.
- B6 keeps `GenerationResult` backward compatible with preview/filepath fields
  while adding page-level metadata; navigation styling is in shared site CSS
  instead of inline nav template styles.

## Testing

- Added unit tests for B4 sitemap/decider/style utilities and sitemap prompt wiring:
  - `packages/backend/tests/test_multipage_decider.py`
  - `packages/backend/tests/test_sitemap_schema.py`
  - `packages/backend/tests/test_style_utils.py`
  - `packages/backend/tests/test_sitemap_agent.py`
  - `packages/backend/tests/test_agent_prompts.py`
- Added unit tests for B6 generation utilities:
  - `packages/backend/tests/test_generation_agent.py`
  - `packages/backend/tests/test_html_utils.py`
  - `packages/backend/tests/test_style_utils.py`
- Run from `packages/backend` with `PYTHONPATH=.` for module resolution.

---

**Last Updated**: 2026-02-01
