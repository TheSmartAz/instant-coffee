# Version 0.6 Implementation Summary

## Overview

**Version**: v0.6 - Skills 编排 + Orchestrator 路由 + 多模型路由 + 数据传递 + 风格参考 + 移动端约束
**Status**: Complete
**Start Date**: 2026-02-03
**Completion Date**: 2026-02-03

**Complexity normalization**:
- Canonical `complexity`: `simple | medium | complex`
- Manifest/legacy values map as: `checklist → simple`, `standard → medium`, `extended → complex`

## Implementation Progress

### Database Phases

| Phase ID | Name | Status | Completed Date |
|----------|------|--------|----------------|
| v06-D1 | Session Metadata Extension | ✅ Complete | 2026-02-03 |

### Backend Phases

| Phase ID | Name | Status | Completed Date |
|----------|------|--------|----------------|
| v06-B1 | Skills Registry + Profiles + Guardrails | ✅ Complete | 2026-02-03 |
| v06-B2 | Orchestrator Routing + Style/Guardrail Injection | ✅ Complete | 2026-02-03 |
| v06-B3 | Style Reference Service | ✅ Complete | 2026-02-03 |
| v06-B4 | Product Doc Tiers | ✅ Complete | 2026-02-03 |
| v06-B5 | Data Protocol Generation | ✅ Complete | 2026-02-03 |
| v06-B6 | Multi-model Routing | ✅ Complete | 2026-02-03 |
| v06-B7 | Aesthetic Scoring | ✅ Complete | 2026-02-03 |
| v06-B8 | API: Chat Image Upload | ✅ Complete | 2026-02-03 |

### Frontend Phases

| Phase ID | Name | Status | Completed Date |
|----------|------|--------|----------------|
| v06-F1 | Data Tab UI | ✅ Complete | 2026-02-03 |
| v06-F2 | Image Upload & @Page Support | ✅ Complete | 2026-02-03 |
| v06-F3 | Preview Message Bridge | ✅ Complete | 2026-02-03 |
| v06-F4 | Page Mention Component | ✅ Complete | 2026-02-03 |

### Output/Generated Phases

| Phase ID | Name | Status | Completed Date |
|----------|------|--------|----------------|
| v06-O1 | Data Store Scripts | ✅ Complete | 2026-02-03 |

---

## Phase Details (Draft)

### v06-D1: Session Metadata Extension

**Status**: ✅ Complete
**Implementation Date**: 2026-02-03

**Files Modified/Created**:
- `packages/backend/app/db/models.py`
- `packages/backend/app/db/migrations.py`
- `packages/backend/app/db/__init__.py`
- `packages/backend/app/api/sessions.py`
- `packages/backend/app/schemas/session_metadata.py`
- `packages/backend/app/schemas/__init__.py`
- `packages/backend/tests/test_migrations.py`

**Features Implemented**:
- Added nullable routing metadata + model usage fields to sessions table/model.
- Added v06 migration to backfill schema on startup.
- Exposed new fields in session API payloads.
- Added pydantic models for routing metadata + model usage.

**Acceptance Criteria Met**:
- [x] All new fields are added to the sessions table
- [x] Fields are nullable (for backward compatibility with existing sessions)
- [x] Migration script is created

### v06-B1: Skills Registry + Profiles + Guardrails

**Status**: ✅ Complete
**Implementation Date**: 2026-02-03

**Files Modified/Created**:
- `packages/backend/app/services/skills/__init__.py`
- `packages/backend/app/services/skills/manifests/flow-ecommerce-v1.json`
- `packages/backend/app/services/skills/manifests/flow-booking-v1.json`
- `packages/backend/app/services/skills/manifests/flow-dashboard-v1.json`
- `packages/backend/app/services/skills/manifests/static-landing-v1.json`
- `packages/backend/app/services/skills/manifests/static-invitation-v1.json`
- `packages/backend/app/services/skills/contracts/ecommerce.json`
- `packages/backend/app/services/skills/contracts/booking.json`
- `packages/backend/app/services/skills/contracts/dashboard.json`
- `packages/backend/app/services/skills/rules/style-profiles.json`
- `packages/backend/app/services/skills/rules/style-router.json`
- `packages/backend/app/services/skills/rules/mobile-guardrails.json`
- `packages/backend/tests/test_skills_registry.py`

**Features Implemented**:
- SkillManifest schema + validation, including model preference keys and product/doc tier checks.
- Skills registry service with manifest loading, skill lookup, filtering, and contract/guardrail resolution.
- Sample skill manifests for flow + static product types with complexity metadata.
- State contract templates for ecommerce, booking, and dashboard.
- Style profiles, style router, and mobile guardrails rules.
- Unit tests for manifest validation, registry loading, and contract access.

**Acceptance Criteria Met**:
- [x] SkillManifest model validates all required fields
- [x] product_types is a list of valid product type enums
- [x] model_prefs contains valid role keys (classifier, writer, validator, expander)
- [x] Registry loads all manifests from directory on startup
- [x] Can retrieve skill by ID
- [x] Can filter skills by product_type and complexity
- [x] Returns None for invalid skill IDs
- [x] All manifests validate against SkillManifest schema
- [x] Flow app manifests include state_contract references
- [x] Static manifests have empty/no state_contract
- [x] Manifests reference guardrail rules
- [x] Contracts define state structure for their product type
- [x] Include events_key for shared event log
- [x] Include records structure for submitted data
- [x] Style profiles include colors, typography, radius, spacing, layout_patterns
- [x] Router maps keywords to profiles with a default fallback
- [x] Guardrails separate critical (hard) vs optimization (soft) rules

### v06-B2: Orchestrator Routing + Style/Guardrail Injection

**Status**: ✅ Complete
**Implementation Date**: 2026-02-03

**Files Modified/Created**:
- `packages/backend/app/agents/classifier.py`
- `packages/backend/app/agents/orchestrator.py`
- `packages/backend/app/agents/orchestrator_routing/__init__.py`
- `packages/backend/app/agents/orchestrator_routing/complexity.py`
- `packages/backend/app/agents/orchestrator_routing/doc_tier.py`
- `packages/backend/app/agents/orchestrator_routing/routing.py`
- `packages/backend/app/agents/orchestrator_routing/skill_selector.py`
- `packages/backend/app/agents/orchestrator_routing/targets.py`
- `packages/backend/app/agents/product_doc.py`
- `packages/backend/app/agents/generation.py`
- `packages/backend/app/executor/task_executor.py`
- `packages/backend/app/utils/guardrails.py`
- `packages/backend/app/generators/mobile_html.py`
- `packages/backend/tests/test_orchestrator_router.py`
- `packages/backend/tests/test_generation_agent.py`

**Features Implemented**:
- Product type classifier (LLM + heuristic fallback) with confidence score.
- Complexity evaluator (heuristic + optional LLM) with structured report.
- @Page resolver with slug/title/partial matching.
- Skill selector wired to SkillsRegistry + complexity/doc-tier normalization.
- Style profile routing with manifest-allowed profile filtering.
- Guardrail injection into ProductDoc + Generation prompts; validator checks form labels.
- Doc tier selection (complexity mapping + static overrides).
- Orchestrator routing orchestration with session metadata updates.
- Routing decision reused across product doc and generation pipelines.

**Acceptance Criteria Met**:
- [x] Classifies “I want an online store” as ecommerce
- [x] Classifies “Make a booking page” as booking
- [x] Classifies “Create a landing page” as landing
- [x] Single page showcase = simple
- [x] Multi-page with forms = medium
- [x] Multi-page with complex data flow = complex
- [x] Extracts @Home from “Update @Home with new hero”
- [x] Returns empty list when no @Page found
- [x] Handles multiple @Page mentions
- [x] ecommerce + any complexity → flow-ecommerce-v1
- [x] landing + simple → static-landing-v1
- [x] invitation/card + simple → static-invitation-v1
- [x] “luxury spa” → soft-elegant
- [x] “AI analytics dashboard” → bold-tech
- [x] No keywords → clean-modern
- [x] Landing/card/invitation → checklist
- [x] Simple flow app → checklist
- [x] Medium flow app → standard
- [x] Complex flow app → extended
- [x] Routing completes before generation starts
- [x] Decisions stored in session metadata
- [x] Guardrails injected into internal context only

### v06-B3: Style Reference Service

**Status**: ✅ Complete
**Implementation Date**: 2026-02-03

**Files Modified/Created**:
- `packages/backend/app/schemas/style_reference.py`
- `packages/backend/app/services/style_reference.py`
- `packages/backend/app/agents/prompts.py`
- `packages/backend/app/agents/orchestrator.py`
- `packages/backend/app/agents/product_doc.py`
- `packages/backend/app/api/chat.py`
- `packages/backend/app/schemas/chat.py`
- `packages/backend/tests/test_style_reference.py`

**Features Implemented**:
- Style reference schemas + tokens normalization/merge utilities
- Vision-based style token extraction with WCAG contrast check + fallback to style_only
- Prompt templates for style-only vs full-mimic extraction
- Style token injection into ProductDoc + Generation pipeline (scope-aware)
- Profile token fallback + merge (reference tokens override profile)
- Manual style tokens accepted via chat payload
- Unit tests for schema validation, scope, and token mapping

**Acceptance Criteria Met**:
- [x] StyleReference model validates fields and limits to 1–3 images
- [x] Modes are enum-validated
- [x] Extracts color palette/typography/radius/shadow/spacing (vision path)
- [x] Full-mimic prompt includes layout patterns + confidence
- [x] Style tokens appear in generation context and merge with profiles
- [x] Scope filtering limits token injection to target pages
- [x] Fallback to profile tokens when no images or extraction fails

### v06-B4: Product Doc Tiers

**Status**: ✅ Complete
**Implementation Date**: 2026-02-03

**Files Modified/Created**:
- `packages/backend/app/schemas/product_doc.py`
- `packages/backend/app/services/product_doc.py`
- `packages/backend/app/agents/product_doc.py`
- `packages/backend/app/agents/prompts.py`
- `packages/backend/tests/test_product_doc_agent.py`
- `packages/backend/tests/test_product_doc_tiers.py`

**Features Implemented**:
- Added tiered ProductDoc schemas (Checklist/Standard/Extended) with shared structured fields.
- Implemented tier selection + normalization with complexity/doc_tier compatibility.
- Updated ProductDoc agent prompts and parsing for tier-specific output.
- Added structured field normalization (pages/data_flow/state_contract/style_reference/component_inventory).
- Added optional mermaid diagram generation for extended tier.
- Synced routing metadata into session records on create/update.

**Acceptance Criteria Met**:
- [x] All tiers share base fields (product_type, complexity, doc_tier)
- [x] Checklist tier has minimal structure
- [x] Standard tier includes pages, data_flow, state_contract
- [x] Extended tier supports mermaid and multi-doc

### v06-B5: Data Protocol Generation

**Status**: ✅ Complete
**Implementation Date**: 2026-02-03

**Files Modified/Created**:
- `packages/backend/app/services/data_protocol.py`
- `packages/backend/app/utils/product_doc.py`
- `packages/backend/app/agents/generation.py`
- `packages/backend/app/agents/refinement.py`
- `packages/backend/app/services/export.py`
- `packages/backend/app/schemas/product_doc.py`
- `packages/backend/app/services/product_doc.py`
- `packages/backend/app/agents/product_doc.py`
- `packages/backend/app/agents/prompts.py`
- `packages/backend/app/services/skills/contracts/ecommerce.json`
- `packages/backend/app/services/skills/contracts/booking.json`
- `packages/backend/app/services/skills/contracts/dashboard.json`
- `packages/backend/tests/test_data_protocol.py`

**Features Implemented**:
- DataProtocolGenerator generates state contracts with skill contract fallback and default event lists.
- Script generators for `data-store.js` and `data-client.js` with localStorage, events log, and preview postMessage.
- Auto injection of data scripts into generated/refined HTML (flow apps: store + client; static: store only).
- Export pipeline writes shared assets (`shared/state-contract.json`, `shared/data-store.js`, `shared/data-client.js`) and lists them in manifest.

**Acceptance Criteria Met**:
- [x] Flow apps generate state contract
- [x] Static apps have empty/minimal contract
- [x] Contract includes event definitions
- [x] Contract output to `<output_dir>/<session_id>/shared/state-contract.json`
- [x] Script outputs to `<output_dir>/<session_id>/shared/data-store.js`
- [x] Implements InstantCoffeeDataStore class
- [x] Supports get_state, set_state, persist
- [x] Listens to storage events for cross-page sync
- [x] Logs events to instant-coffee:events key
- [x] Script outputs to `<output_dir>/<session_id>/shared/data-client.js`
- [x] Provides product-type-specific helpers
- [x] Helpers emit events on state changes
- [x] Submitted data writes to records key
- [x] Generated pages include script tags
- [x] Messages sent on state changes (debounced)
- [x] Messages sent immediately on submit events
- [x] Message format includes type, data, timestamp
- [x] Messages target window.parent
- [x] State restored on page load
- [x] Cross-page navigation preserves state

### v06-B6: Multi-model Routing

**Status**: ✅ Complete
**Implementation Date**: 2026-02-03

**Files Modified/Created**:
- `packages/backend/app/config.py`
- `packages/backend/app/llm/model_catalog.py`
- `packages/backend/app/llm/client_factory.py`
- `packages/backend/app/llm/model_pool.py`
- `packages/backend/app/llm/__init__.py`
- `packages/backend/app/agents/base.py`
- `packages/backend/app/agents/classifier.py`
- `packages/backend/app/agents/orchestrator_routing/complexity.py`
- `packages/backend/app/agents/interview.py`
- `packages/backend/app/agents/sitemap.py`
- `packages/backend/app/agents/product_doc.py`
- `packages/backend/app/agents/generation.py`
- `packages/backend/app/agents/refinement.py`
- `packages/backend/app/agents/orchestrator.py`
- `packages/backend/app/services/style_reference.py`
- `packages/backend/tests/test_model_pool.py`

**Features Implemented**:
- Model role enum + routing defaults, with per-product pools and env overrides.
- Model client factory with base_url/api_key support, caching, and explicit errors.
- Model pool manager with failure tracking, TTL blacklisting, and ordered fallback.
- Response-aware fallback (timeout/connection + missing required fields in ProductDoc).
- Agent-level model routing with role tagging and session model usage tracking.
- Capability detection (vision + max_tokens) and style_refiner gating by vision support.
- Dedicated style_refiner pool integration for style reference extraction.

**Acceptance Criteria Met**:
- [x] Model roles are well-defined enum
- [x] Configuration supports multiple models per role
- [x] Product-specific overrides are supported
- [x] Configuration is environment-based
- [x] Creates client from model config
- [x] Supports custom base_url
- [x] Caches clients by config hash
- [x] Raises clear error on invalid config
- [x] Returns first available model in pool
- [x] Falls to next model on failure
- [x] Logs model selection decisions
- [x] Tracks failure counts per model
- [x] Fallback on timeout
- [x] Fallback on connection error
- [x] Fallback on missing required fields
- [x] Max 3 fallback attempts
- [x] Vision capability detected/declared
- [x] Token limits known per model (catalog metadata)
- [x] Capability checked before use

### v06-B7: Aesthetic Scoring

**Status**: ✅ Complete
**Implementation Date**: 2026-02-03

**Files Modified/Created**:
- `packages/backend/app/schemas/validation.py`
- `packages/backend/app/utils/validation.py`
- `packages/backend/app/agents/aesthetic_scorer.py`
- `packages/backend/app/agents/style_refiner.py`
- `packages/backend/app/agents/validator.py`
- `packages/backend/app/agents/prompts.py`
- `packages/backend/app/agents/__init__.py`
- `packages/backend/app/events/types.py`
- `packages/backend/app/events/models.py`
- `packages/backend/app/executor/task_executor.py`
- `packages/backend/app/schemas/__init__.py`
- `packages/backend/tests/test_aesthetic_scoring.py`
- `packages/web/src/types/events.ts`

**Features Implemented**:
- Aesthetic scoring schema (dimensions + auto-checks) with threshold logic.
- Automated checks for WCAG contrast, line-height range, and type scale hierarchy.
- Aesthetic scorer agent (validator role) with JSON parsing + fallback scoring.
- Style refiner agent (style_refiner role) with HTML-only output enforcement.
- Validator pipeline integration: score, refine up to 2 attempts, compare scores, never degrade.
- Scores emitted via new `aesthetic_score` SSE event and included in validator task results.
- Tests for schema validation, auto-checks, and rewrite comparison behavior.

**Acceptance Criteria Met**:
- [x] Score model validates ranges (1-5 per dimension)
- [x] Total score calculated correctly
- [x] Auto-checks return pass/fail status
- [x] Returns score for each dimension
- [x] Returns total score (sum of dimensions)
- [x] Lists specific issues found
- [x] Includes auto-check results
- [x] Contrast check returns pass/fail + ratio
- [x] Line-height check validates body text
- [x] Type scale check ensures hierarchy
- [x] Scores >= 18 pass without refiner
- [x] Scores < 18 trigger Style Refiner
- [x] Maximum 2 refiner iterations
- [x] Higher-scoring version selected
- [x] Never degrades score
- [x] Stops after 2 iterations
- [x] All Landing/Card/Invitation pages scored
- [x] Low scores trigger refiner
- [x] Scores logged for analysis (SSE + task results)
- [x] Generation completes with best version

### v06-B8: API: Chat Image Upload

**Status**: ✅ Complete
**Implementation Date**: 2026-02-03

**Files Modified/Created**:
- `packages/backend/app/api/chat.py`
- `packages/backend/app/agents/orchestrator.py`
- `packages/backend/app/schemas/chat.py`
- `packages/backend/app/services/image_storage.py`
- `packages/backend/app/utils/chat.py`

**Features Implemented**:
- Chat request schema now accepts `images`, `target_pages`, and `style_reference`.
- Image uploads can be base64 or data URLs; URLs are passed through.
- Image count validated to max 3 across all inputs.
- Image storage service saves uploads with metadata + session scoping.
- @Page mentions parsed and resolved against existing page slugs.
- Chat endpoint passes style reference + target pages into orchestrator call.
- Added POST `/api/chat/stream` to support streaming with images and @Page context.

**Acceptance Criteria Met**:
- [x] Images field accepts 0-3 images
- [x] Images can be base64 or URLs
- [x] target_pages is optional, defaults to empty
- [x] style_reference_mode defaults to full_mimic

### v06-F1: Data Tab UI

**Status**: ✅ Complete
**Implementation Date**: 2026-02-03

**Files Modified/Created**:
- `packages/web/src/components/custom/DataTab.tsx`
- `packages/web/src/components/custom/PreviewPanel.tsx`

**Features Implemented**:
- Added Data tab to Preview panel with State, Events, and Records sections.
- Added JSON viewer with syntax highlighting, collapsible nodes, and copy action.
- Added events list with timestamps, newest-first order, and auto-scroll.
- Added record cards with type styling and JSON export.
- Added preview-side data emitter for `instant-coffee:update` to keep data live.

**Acceptance Criteria Met**:
- [x] Component renders in Preview panel
- [x] Three sections visible by default
- [x] Each section collapsible
- [x] Empty state shown when no data
- [x] JSON formatted and readable
- [x] Copy button works
- [x] Large objects can be collapsed
- [x] Events display in reverse chronological order
- [x] Timestamps formatted human-readable
- [x] Data truncated when too long
- [x] Auto-scrolls to newest events
- [x] Records show type/date and key data
- [x] Export downloads JSON

### v06-F2: Image Upload & @Page Support

**Status**: ✅ Complete
**Implementation Date**: 2026-02-03

**Files Modified/Created**:
- `packages/web/src/components/custom/ChatInput.tsx`
- `packages/web/src/components/custom/ImageThumbnail.tsx`
- `packages/web/src/components/custom/PageMentionPopover.tsx`
- `packages/web/src/components/custom/ChatPanel.tsx`
- `packages/web/src/pages/ProjectPage.tsx`
- `packages/web/src/utils/chat.ts`
- `packages/web/src/api/client.ts`
- `packages/web/src/hooks/useChat.ts`
- `packages/web/src/types/index.ts`

**Features Implemented**:
- Added image upload via file picker and drag-and-drop on the textarea.
- Added thumbnail preview strip with remove actions and hover metadata.
- Enforced image validation (type, size <= 5MB, max 3 images).
- Added @Page mention popover with filtering and keyboard navigation.
- Parsed @Page mentions and sent `target_pages` alongside images.
- Added streaming support for image/@Page payloads via POST `/api/chat/stream`.

**Acceptance Criteria Met**:
- [x] Image button opens file picker
- [x] Drag-and-drop works on textarea
- [x] Images display as thumbnails
- [x] Remove button on each image thumbnail
- [x] Max 3 images enforced
- [x] Only images accepted; non-image rejected with message
- [x] Files > 5MB rejected with message
- [x] Dropdown appears after @ with filtering
- [x] Keyboard navigation and click-to-select work
- [x] @Page inserted at cursor position

### v06-F3: Preview Message Bridge

**Status**: ✅ Complete
**Implementation Date**: 2026-02-03

**Files Modified/Created**:
- `packages/web/src/hooks/usePreviewBridge.ts`

**Features Implemented**:
- Added `usePreviewBridge` hook for preview iframe `postMessage` handling.
- Added `PreviewMessage` type guard with payload parsing + validation.
- Added debounce logic with immediate updates for submit/checkout events.
- Added iframe lifecycle handling + cleanup and connection state tracking.

**Acceptance Criteria Met**:
- [x] Hook returns current state, events, and records.
- [x] Hook returns connection status and last update timestamp.
- [x] Messages filtered by type guard and ignored when malformed.
- [x] Listener cleanup on unmount and iframe disconnect.

### v06-F4: Page Mention Component

**Status**: ✅ Complete
**Implementation Date**: 2026-02-03

**Files Modified/Created**:
- `packages/web/src/components/custom/PageMentionPopover.tsx`
- `packages/web/src/components/custom/ChatInput.tsx`

**Features Implemented**:
- Added caret-aware popover placement with arrow pointer and overflow handling.
- Added keyboard wrap navigation and Escape to close.
- Prevented click selection from stealing textarea focus.
- Added outside-click dismissal for the mention popover.

**Acceptance Criteria Met**:
- [x] Component renders dropdown list
- [x] Pages filtered by search query
- [x] Empty state shows "No matching pages"
- [x] Each item shows page slug and title
- [x] Arrow keys navigate through list
- [x] Selection wraps at boundaries
- [x] Enter selects highlighted item
- [x] Escape closes popover without selection
- [x] Popover appears below textarea
- [x] Doesn't overflow viewport
- [x] Adjusts position if too close to bottom
- [x] Arrow points to caret position
- [x] Click selects page
- [x] Popover closes after selection
- [x] Textarea remains focused
- [x] @Page inserted correctly

### v06-O1: Data Store Scripts

**Status**: ✅ Complete
**Implementation Date**: 2026-02-03

**Files Modified/Created**:
- `packages/backend/app/services/data_protocol.py`
- `packages/backend/app/utils/product_doc.py`
- `packages/backend/app/services/export.py`
- `packages/backend/app/services/skills/contracts/ecommerce.json`
- `packages/backend/app/services/skills/contracts/booking.json`
- `packages/backend/app/services/skills/contracts/dashboard.json`

**Features Implemented**:
- Shared data protocol assets generated per session (`shared/data-store.js`, `shared/data-client.js`, `shared/state-contract.json`).
- Inline state contract injected into HTML as `window.__instantCoffeeContract` before scripts load.
- Data store exposes aliases (`window.__instantCoffeeStore`, `window.IC`) and supports `subscribe`.
- Data client provides cart/booking/form helpers with event logging and record submission helpers.
- Export manifest includes shared assets.

**Acceptance Criteria Met**:
- [x] Shared data-store scripts are generated during preview and export
- [x] Assets are written under session-scoped output directory
- [x] State contract injected into generated HTML
- [x] Flow apps include store + client scripts; static apps include store only

---

## Gap Fixes (2026-02-04)

### @Page Scope Enforcement

**Approach**:
- Applied `target_pages` to generation/regeneration paths (generate-now, confirm, regenerate, generation pipeline).
- Refinement now respects @Page: single target refines directly; multiple targets batch-refine.
- Product doc updates with @Page now set pending regeneration to the targeted slugs.

### Style Reference "model_decide"

**Approach**:
- Profile tokens remain global for baseline styling.
- Reference tokens are no longer forced global when scope is `model_decide`.
- Unscoped reference tokens are passed to generation requirements as “model decide” hints, allowing partial/global application per page.

### Expander Integration (Flow Apps)

**Approach**:
- Added an Expander agent (ModelRole.EXPANDER) that emits concise expansion notes.
- Triggered by flow product types, multi-page docs, data_flow presence, schema cart/draft keys, or large component inventory.
- Expansion notes are appended to page requirements before generation (focused on secondary pages).

### Shared Component Consistency

**Approach**:
- Seed `component_inventory` from the selected skill manifest when missing.
- Generation context now includes component inventory to encourage reuse across pages.
