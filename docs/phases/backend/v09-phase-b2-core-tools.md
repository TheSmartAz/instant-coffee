# Phase B2: Core Tools (8 Generation Tools)

## Metadata

- **Category**: Backend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: High
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: v09-B1 (Tool Foundation)
  - **Blocks**: v09-B5 (Agentic Loop Core)

## Goal

Implement the 8 core generation tools that wrap existing business logic into the `BaseTool` interface: `analyze_brief`, `create_design_system`, `generate_page`, `edit_page`, `read_page`, `list_pages`, `validate_html`, `extract_style`.

## Detailed Tasks

### Task 1: analyze_brief Tool

**Description**: Detect product type, scenario, and default data model from user request.

**Implementation Details**:
- [ ] Pydantic params: `{ user_request: str, conversation_summary: Optional[str] }`
- [ ] Call `ScenarioDetector.detect()` to identify product type and scenario
- [ ] Return product type, scenario classification, suggested page list, default data model
- [ ] Reuse `app/services/scenario_detector.py` and `app/schemas/scenario.py`

**Files to modify/create**:
- `packages/backend/app/tools/brief.py`

---

### Task 2: create_design_system Tool

**Description**: Generate shared CSS design system via LLM.

**Implementation Details**:
- [ ] Pydantic params: `{ product_type: str, style_tokens: Optional[dict], brand_colors: Optional[list[str]] }`
- [ ] Use LLM (via `ctx.llm_client`) to generate `design-system.css`
- [ ] CSS contains: variables (colors, spacing, typography), component classes, mobile utilities
- [ ] Save to `{output_dir}/{session_id}/design-system.css`
- [ ] Return CSS content in `artifacts`

**Files to modify/create**:
- `packages/backend/app/tools/design_system.py`

---

### Task 3: generate_page Tool

**Description**: Generate standalone HTML page using LLM.

**Implementation Details**:
- [ ] Pydantic params: `{ slug: str, title: str, description: str, design_system_css: Optional[str], data_model: Optional[dict] }`
- [ ] HTML includes `<link rel="stylesheet" href="design-system.css">`, page-specific `<style>`, page-specific `<script>`
- [ ] Mobile-first: viewport meta, max-width 430px, hidden scrollbar, 44px touch targets
- [ ] Save to `{output_dir}/{session_id}/pages/{slug}.html`
- [ ] Reuse prompt logic from `app/agents/generation.py` and `app/agents/prompts.py`
- [ ] Create page version record via existing `PageVersionService`

**Files to modify/create**:
- `packages/backend/app/tools/generate_page.py`

---

### Task 4: edit_page Tool

**Description**: Apply targeted edits to existing page HTML via LLM.

**Implementation Details**:
- [ ] Pydantic params: `{ slug: str, edit_instructions: str, current_html: Optional[str] }`
- [ ] If `current_html` not provided, read from disk
- [ ] Reuse prompt logic from `app/agents/refinement.py`
- [ ] Create new page version record

**Files to modify/create**:
- `packages/backend/app/tools/edit_page.py`

---

### Task 5: read_page & list_pages Tools

**Description**: File system tools for reading and listing pages.

**Implementation Details**:
- [ ] `read_page`: Pydantic params `{ slug: str }`, reads HTML from `{output_dir}/{session_id}/pages/{slug}.html`
- [ ] `list_pages`: No params, lists all `.html` files, returns `{ slug, title, size_bytes, modified_at }`
- [ ] Reuse `app/services/file_tree.py`

**Files to modify/create**:
- `packages/backend/app/tools/read_page.py`
- `packages/backend/app/tools/list_pages.py`

---

### Task 6: validate_html & extract_style Tools

**Description**: Validation and style extraction tools.

**Implementation Details**:
- [ ] `validate_html`: Pydantic params `{ slug: str, html: Optional[str] }`, runs mobile compliance checks from `app/utils/html.py`
- [ ] `extract_style`: Pydantic params `{ image_url: str }`, extracts style tokens via `app/services/style_extractor.py`

**Files to modify/create**:
- `packages/backend/app/tools/validate.py`
- `packages/backend/app/tools/style_extract.py`

---

### Task 7: Unit Tests

**Description**: Test core tools with mocked dependencies.

**Implementation Details**:
- [ ] `test_tools_brief.py`: `analyze_brief` with mocked `ScenarioDetector`
- [ ] `test_tools_generate.py`: `generate_page` with mocked LLM, file output verification
- [ ] `test_tools_edit.py`: `edit_page` with mocked LLM, diff verification

**Files to modify/create**:
- `packages/backend/tests/test_tools_brief.py`
- `packages/backend/tests/test_tools_generate.py`
- `packages/backend/tests/test_tools_edit.py`

**Acceptance Criteria**:
- [ ] All 8 tools implement `BaseTool` and register with `ToolRegistry`
- [ ] `generate_page` produces valid mobile-optimized HTML
- [ ] `edit_page` preserves unmodified sections of the page
- [ ] `validate_html` catches common mobile compliance issues
- [ ] Tools reuse existing services where noted (no duplication)

## Technical Specifications

### Design System Approach

- `create_design_system` generates `design-system.css` with CSS variables, component classes, mobile utilities
- `generate_page` produces standalone HTML that `<link>`s the design system
- For preview, CSS is inlined into the HTML (reuse existing `build_global_style_css()` pattern)
- Consistency across pages comes from shared CSS + LLM having design system in context

### HTML Generation Approach

- Each page is a single HTML file with `<link rel="stylesheet" href="design-system.css">`
- Page-specific CSS in `<style>` block, page-specific JS in `<script>` block
- Mobile-first: viewport meta, max-width 430px, hidden scrollbar, 44px touch targets
- Saved to `{output_dir}/{session_id}/pages/{slug}.html`

## Testing Requirements

- [ ] Unit tests for each tool with mocked LLM and services
- [ ] File output verification for `generate_page` and `create_design_system`
- [ ] All tests use mocked LLM (no real API calls)

## Notes & Warnings

- Tools should reuse existing prompt logic from `app/agents/generation.py` and `app/agents/refinement.py` — extract the prompts, don't duplicate them
- `generate_page` and `edit_page` both need to create version records via `PageVersionService`
- The design system CSS file is shared across all pages in a session
