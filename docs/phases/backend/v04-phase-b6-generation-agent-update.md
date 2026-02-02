# Phase B6: GenerationAgent Update for Multi-Page

## Metadata

- **Category**: Backend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: Medium
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: B2 (Page Service), B4 (Sitemap Agent)
  - **Blocks**: B7, B8

## Goal

Extend the GenerationAgent to support multi-page generation with shared navigation, global styles, and ProductDoc context.

## Detailed Tasks

### Task 1: Update GenerationAgent Input Interface

**Description**: Add new parameters for multi-page generation context.

**Implementation Details**:
- [ ] Add `page_spec: SitemapPage` parameter (title, slug, purpose, sections)
- [ ] Add `global_style: GlobalStyle` parameter (colors, fonts, spacing)
- [ ] Add `nav: List[NavItem]` parameter (navigation structure)
- [ ] Add `product_doc: ProductDoc` parameter (full context)
- [ ] Add `all_pages: List[str]` parameter (list of all page slugs for linking)
- [ ] Keep backward compatibility for single-page mode

**Files to modify/create**:
- `packages/backend/app/agents/generation.py`

**Acceptance Criteria**:
- [ ] New parameters accepted and used
- [ ] Single-page mode still works
- [ ] Type hints updated

---

### Task 2: Update Generation Prompt for Page Context

**Description**: Modify prompts to include page-specific requirements.

**Implementation Details**:
- [ ] Include page purpose and sections in prompt
- [ ] Include ProductDoc context (design direction, constraints)
- [ ] Include global_style CSS variables
- [ ] Include navigation HTML template
- [ ] Specify page-specific content requirements
- [ ] Maintain mobile-first constraints

**Files to modify/create**:
- `packages/backend/app/agents/prompts.py`

**Acceptance Criteria**:
- [ ] Generated page matches page_spec
- [ ] Sections included as specified
- [ ] Design follows global_style

---

### Task 3: Implement Navigation HTML Generation

**Description**: Generate consistent navigation HTML for all pages.

**Implementation Details**:
- [ ] Create nav HTML template with links to all pages
- [ ] Mark current page as active
- [ ] Use proper link paths:
  - index → `index.html` or `./`
  - others → `pages/{slug}.html`
- [ ] Style nav with global_style colors
- [ ] Make nav mobile-friendly (hamburger menu or horizontal scroll)

**Files to modify/create**:
- `packages/backend/app/agents/generation.py`
- `packages/backend/app/utils/html.py`

**Acceptance Criteria**:
- [ ] Navigation present on all pages
- [ ] Active page highlighted
- [ ] Links work correctly

---

### Task 4: Implement Global Style CSS Generation

**Description**: Generate CSS from GlobalStyle that can be shared or inlined.

**Implementation Details**:
- [ ] Convert GlobalStyle to CSS variables:
  ```css
  :root {
    --primary-color: #xxx;
    --font-family: xxx;
    /* etc. */
  }
  ```
- [ ] Include base mobile styles
- [ ] Include hide-scrollbar styles
- [ ] Support both inline and external CSS modes

**Files to modify/create**:
- `packages/backend/app/utils/style.py`
- `packages/backend/app/agents/generation.py`

**Acceptance Criteria**:
- [ ] CSS variables correctly generated
- [ ] Mobile base styles included
- [ ] Works for preview (inline) and export (external)

---

### Task 5: Update Output to Save PageVersion

**Description**: Modify generation output to create PageVersion records.

**Implementation Details**:
- [ ] After HTML generation, call PageVersionService.create()
- [ ] Use page_id from pre-created Page record
- [ ] Include generation description in version
- [ ] Emit page_version_created event
- [ ] Emit page_preview_ready event

**Files to modify/create**:
- `packages/backend/app/agents/generation.py`

**Acceptance Criteria**:
- [ ] PageVersion created for each generated page
- [ ] Version number increments correctly
- [ ] Events emitted

---

### Task 6: Handle Internal Linking

**Description**: Ensure proper internal links between pages.

**Implementation Details**:
- [ ] Parse generated HTML for internal links
- [ ] Validate link targets exist in page list
- [ ] Correct link format:
  - index → `index.html`
  - others → `pages/{slug}.html`
- [ ] Handle anchor links within same page
- [ ] Warn on broken links

**Files to modify/create**:
- `packages/backend/app/agents/generation.py`
- `packages/backend/app/utils/html.py`

**Acceptance Criteria**:
- [ ] Internal links use correct paths
- [ ] Broken links detected and warned
- [ ] Navigation links all work

---

## Technical Specifications

### Updated GenerationAgent Interface

```python
class GenerationAgent(BaseAgent):
    async def generate(
        self,
        session_id: UUID,
        page_id: UUID,  # Pre-created Page record
        page_spec: SitemapPage,
        global_style: GlobalStyle,
        nav: List[NavItem],
        product_doc: ProductDoc,
        all_pages: List[str],  # All page slugs
        history: List[Message] = []
    ) -> GenerationResult:
        """Generate HTML for a single page."""
        pass

@dataclass
class GenerationResult:
    html: str  # Generated HTML
    page_id: UUID
    version: int  # Created version number
    tokens_used: int
```

### Updated Generation Prompt

```python
GENERATION_SYSTEM_MULTIPAGE = """You are generating a mobile-first HTML page as part of a multi-page website.

=== Page Specification ===
Title: {page_title}
Slug: {page_slug}
Purpose: {page_purpose}
Sections to include: {sections_list}

=== Design System ===
{global_style_css}

=== Navigation ===
Pages in this site:
{nav_list}

Current page: {current_slug}

=== Product Requirements ===
{product_doc_context}

=== Constraints ===
- Mobile viewport: max-width 430px
- Buttons: minimum 44px height
- Fonts: body 16px, headings 24-32px
- Include navigation bar linking to all pages
- Mark current page as active in nav
- Use CSS variables from design system
- Single-file HTML with inline CSS and JS
- No external dependencies (fonts, images must be inline or placeholder)

Output: Complete HTML document for this page."""
```

### Navigation HTML Template

```html
<nav class="site-nav">
  <div class="nav-container">
    {nav_items}
  </div>
</nav>

<style>
.site-nav {
  position: sticky;
  top: 0;
  background: var(--primary-color);
  padding: 12px 16px;
  z-index: 100;
}
.nav-container {
  display: flex;
  gap: 16px;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}
.nav-container::-webkit-scrollbar { display: none; }
.nav-link {
  color: white;
  text-decoration: none;
  white-space: nowrap;
  padding: 8px 16px;
  border-radius: 20px;
}
.nav-link.active {
  background: rgba(255,255,255,0.2);
}
</style>
```

### Global Style CSS Template

```css
:root {
  --primary-color: {primary_color};
  --secondary-color: {secondary_color};
  --font-family: {font_family};
  --font-size-base: {font_size_base};
  --font-size-heading: {font_size_heading};
  --button-height: {button_height};
  --spacing-unit: {spacing_unit};
  --border-radius: {border_radius};
}

* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  font-family: var(--font-family);
  font-size: var(--font-size-base);
  line-height: 1.5;
  max-width: 430px;
  margin: 0 auto;
}

.hide-scrollbar::-webkit-scrollbar {
  display: none;
}

.hide-scrollbar {
  -ms-overflow-style: none;
  scrollbar-width: none;
}
```

## Testing Requirements

- [ ] Unit tests for navigation HTML generation
- [ ] Unit tests for global style CSS generation
- [ ] Unit tests for internal link handling
- [ ] Integration test for full page generation
- [ ] Test multi-page consistency (nav, styles)
- [ ] Test single-page backward compatibility

## Notes & Warnings

- **Backward Compatibility**: Existing single-page calls should still work
- **Link Paths**: Be careful with relative vs absolute paths; preview and export may differ
- **CSS Inline vs External**: For preview, inline CSS; for export, external site.css
- **Token Limits**: Full ProductDoc context can be large; consider summarization
- **Page Order**: Navigation should respect order_index from sitemap
