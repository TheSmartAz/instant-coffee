# Phase B10: Export Service Update

## Metadata

- **Category**: Backend
- **Priority**: P1 (Important)
- **Estimated Complexity**: Medium
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: B2 (Page Service), B8 (Files API)
  - **Blocks**: None

## Goal

Extend the ExportService to support multi-page export with shared CSS, proper directory structure, Product Doc export, and export manifest.

## Detailed Tasks

### Task 1: Update Export Directory Structure

**Description**: Implement the new export directory layout.

**Implementation Details**:
- [ ] Export index page as `index.html` in root
- [ ] Export other pages to `pages/{slug}.html`
- [ ] Export shared CSS to `assets/site.css`
- [ ] Export Product Doc to `product-doc.md`
- [ ] Generate `export_manifest.json`

**Files to modify/create**:
- `packages/backend/app/services/export.py`

**Acceptance Criteria**:
- [ ] Directory structure matches spec
- [ ] All files in correct locations
- [ ] Paths are platform-independent

---

### Task 2: Generate Shared site.css

**Description**: Create the shared CSS file from global_style.

**Implementation Details**:
- [ ] Extract global_style from session (via Sitemap or cache)
- [ ] Generate CSS content using style utility
- [ ] Write to `assets/site.css`
- [ ] Ensure CSS matches preview styling

**Files to modify/create**:
- `packages/backend/app/services/export.py`
- `packages/backend/app/utils/style.py`

**Acceptance Criteria**:
- [ ] site.css generated correctly
- [ ] Styling consistent with preview
- [ ] CSS is well-formatted

---

### Task 3: Update HTML for External CSS

**Description**: Modify exported HTML to link external CSS instead of inline.

**Implementation Details**:
- [ ] Replace inline `<style>` with `<link rel="stylesheet" href="...">`
- [ ] For index.html: `href="assets/site.css"`
- [ ] For pages/*.html: `href="../assets/site.css"`
- [ ] Keep page-specific inline styles if any

**Files to modify/create**:
- `packages/backend/app/services/export.py`
- `packages/backend/app/utils/html.py`

**Acceptance Criteria**:
- [ ] CSS properly linked
- [ ] Relative paths correct for each page location
- [ ] Pages render correctly

---

### Task 4: Fix Internal Links for Export

**Description**: Ensure internal links work in exported structure.

**Implementation Details**:
- [ ] Parse HTML for internal links
- [ ] Update link paths:
  - From index: `pages/{slug}.html`
  - From pages: `../{slug}.html` for index, `./{slug}.html` for other pages
- [ ] Handle navigation links specially
- [ ] Validate all links point to existing pages

**Files to modify/create**:
- `packages/backend/app/services/export.py`
- `packages/backend/app/utils/html.py`

**Acceptance Criteria**:
- [ ] All internal links work
- [ ] Navigation links correct
- [ ] No broken links

---

### Task 5: Generate Export Manifest

**Description**: Create export_manifest.json documenting export state.

**Implementation Details**:
- [ ] Include export timestamp
- [ ] List all pages with status (success/failed)
- [ ] Include file paths and sizes
- [ ] Include ProductDoc status
- [ ] Include global_style summary

**Files to modify/create**:
- `packages/backend/app/services/export.py`

**Acceptance Criteria**:
- [ ] Manifest is valid JSON
- [ ] All pages listed with status
- [ ] Failed pages documented

---

### Task 6: Handle Partial Export (Failed Pages)

**Description**: Export succeeds even if some pages failed generation.

**Implementation Details**:
- [ ] Export all successfully generated pages
- [ ] Skip failed pages (no HTML available)
- [ ] Mark failed pages in manifest
- [ ] Log warnings for failed pages
- [ ] Don't fail entire export for individual page failures

**Files to modify/create**:
- `packages/backend/app/services/export.py`

**Acceptance Criteria**:
- [ ] Successful pages exported
- [ ] Failed pages noted in manifest
- [ ] Export completes despite failures

---

### Task 7: Export Product Doc

**Description**: Include Product Doc Markdown in export.

**Implementation Details**:
- [ ] Get ProductDoc.content from service
- [ ] Write to `product-doc.md` in export root
- [ ] Skip if no ProductDoc exists

**Files to modify/create**:
- `packages/backend/app/services/export.py`

**Acceptance Criteria**:
- [ ] Product Doc exported when exists
- [ ] Content is proper Markdown
- [ ] Graceful handling when missing

---

## Technical Specifications

### Export Directory Structure

```
{export_dir}/
├── index.html
├── pages/
│   ├── services.html
│   ├── about.html
│   └── contact.html
├── assets/
│   └── site.css
├── product-doc.md
└── export_manifest.json
```

### Export Manifest Schema

```json
{
  "version": "1.0",
  "exported_at": "2026-02-01T12:00:00Z",
  "session_id": "uuid",
  "product_doc": {
    "status": "confirmed",
    "included": true
  },
  "pages": [
    {
      "slug": "index",
      "title": "首页",
      "path": "index.html",
      "status": "success",
      "size": 12480,
      "version": 3
    },
    {
      "slug": "services",
      "title": "服务",
      "path": "pages/services.html",
      "status": "success",
      "size": 8320,
      "version": 1
    },
    {
      "slug": "blog",
      "title": "博客",
      "path": "pages/blog.html",
      "status": "failed",
      "error": "Generation timeout"
    }
  ],
  "assets": [
    {
      "path": "assets/site.css",
      "size": 2048
    }
  ],
  "global_style": {
    "primary_color": "#1E88E5",
    "font_family": "Noto Sans"
  }
}
```

### Updated ExportService Interface

```python
@dataclass
class ExportResult:
    export_dir: Path
    manifest: dict
    success: bool
    errors: List[str]

class ExportService:
    async def export_session(
        self,
        session_id: UUID,
        output_dir: Path | None = None
    ) -> ExportResult:
        """Export session to directory."""
        pass

    async def export_page(
        self,
        page: Page,
        output_path: Path,
        css_path: str  # Relative path to site.css
    ) -> bool:
        """Export single page with external CSS link."""
        pass

    def generate_manifest(
        self,
        session_id: UUID,
        pages: List[PageExportInfo],
        product_doc_status: str | None
    ) -> dict:
        """Generate export manifest."""
        pass
```

### HTML Transformation for Export

```python
def transform_for_export(
    html: str,
    page_slug: str,
    css_path: str,
    all_pages: List[str]
) -> str:
    """Transform preview HTML for export."""

    # 1. Replace inline styles with external CSS link
    html = re.sub(
        r'<style>.*?</style>',
        f'<link rel="stylesheet" href="{css_path}">',
        html,
        flags=re.DOTALL
    )

    # 2. Update internal links
    for target_slug in all_pages:
        if target_slug == "index":
            if page_slug == "index":
                new_href = "index.html"
            else:
                new_href = "../index.html"
        else:
            if page_slug == "index":
                new_href = f"pages/{target_slug}.html"
            else:
                new_href = f"{target_slug}.html"

        html = html.replace(
            f'href="{target_slug}.html"',
            f'href="{new_href}"'
        )

    return html
```

### Link Path Calculation

| Current Page | Target | Link Path |
|--------------|--------|-----------|
| index | index | `index.html` |
| index | services | `pages/services.html` |
| services | index | `../index.html` |
| services | about | `about.html` |

## Testing Requirements

- [ ] Unit tests for directory structure creation
- [ ] Unit tests for CSS externalization
- [ ] Unit tests for link transformation
- [ ] Unit tests for manifest generation
- [ ] Integration test for full export
- [ ] Test partial export with failed pages
- [ ] Test export with no ProductDoc

## Notes & Warnings

- **Atomic Export**: Consider writing to temp dir first, then move on success
- **Existing Files**: Clear or merge with existing export directory
- **Path Separators**: Use `pathlib` for cross-platform path handling
- **Link Validation**: Warn but don't fail on broken links to missing pages
- **CSS Deduplication**: Ensure inline CSS removal doesn't break page-specific styles
