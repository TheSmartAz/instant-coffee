# Phase B8: Files API (Code Tab Backend)

## Metadata

- **Category**: Backend
- **Priority**: P1 (Important)
- **Estimated Complexity**: Medium
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: B2 (Page Service), B1 (ProductDoc Service)
  - **Blocks**: F3

## Goal

Implement the Files API that provides a virtual file tree and file content for the Code Tab, representing the project structure as it would be exported.

## Detailed Tasks

### Task 1: Create Virtual File Tree Service

**Description**: Implement service to generate virtual file tree from session data.

**Implementation Details**:
- [ ] Create FileTreeService class
- [ ] Generate tree from:
  - `index.html` (from index page)
  - `pages/{slug}.html` (from other pages)
  - `assets/site.css` (from global_style)
  - `product-doc.md` (from ProductDoc)
- [ ] Calculate file sizes from content length
- [ ] Return nested tree structure

**Files to modify/create**:
- `packages/backend/app/services/file_tree.py` (new)

**Acceptance Criteria**:
- [ ] Tree includes all expected files
- [ ] Directory structure matches export format
- [ ] File sizes accurate

---

### Task 2: Implement GET /api/sessions/{id}/files

**Description**: Create endpoint to return file tree for session.

**Implementation Details**:
- [ ] Create endpoint returning tree structure
- [ ] Include file metadata (name, path, type, size)
- [ ] Include directory structure with children
- [ ] Handle sessions with no pages (return minimal tree)
- [ ] Handle sessions with no ProductDoc (omit product-doc.md)

**Files to modify/create**:
- `packages/backend/app/api/files.py` (new)
- `packages/backend/app/api/__init__.py`

**Acceptance Criteria**:
- [ ] Endpoint returns correct tree structure
- [ ] Response matches spec schema
- [ ] Empty/partial sessions handled gracefully

---

### Task 3: Implement GET /api/sessions/{id}/files/{path}

**Description**: Create endpoint to return file content.

**Implementation Details**:
- [ ] Parse path parameter (URL-encoded)
- [ ] Generate content based on path:
  - `index.html` → index page current version HTML
  - `pages/{slug}.html` → corresponding page HTML
  - `assets/site.css` → generated CSS from global_style
  - `product-doc.md` → ProductDoc.content
- [ ] Determine language from file extension
- [ ] Return 404 for non-existent paths

**Files to modify/create**:
- `packages/backend/app/api/files.py`
- `packages/backend/app/services/file_tree.py`

**Acceptance Criteria**:
- [ ] File content returned correctly
- [ ] Language field set appropriately
- [ ] 404 for invalid paths

---

### Task 4: Implement CSS Generation for site.css

**Description**: Generate the shared CSS file content.

**Implementation Details**:
- [ ] Use GlobalStyle to generate CSS variables
- [ ] Include mobile base styles
- [ ] Include navigation styles
- [ ] Include hide-scrollbar utility
- [ ] Format CSS nicely (readable)

**Files to modify/create**:
- `packages/backend/app/services/file_tree.py`
- `packages/backend/app/utils/style.py`

**Acceptance Criteria**:
- [ ] CSS is valid and well-formatted
- [ ] All GlobalStyle values used
- [ ] Consistent with inline styles in pages

---

### Task 5: Add Response Schemas

**Description**: Define Pydantic schemas for Files API responses.

**Implementation Details**:
- [ ] Create FileTreeNode schema (name, path, type, size, children)
- [ ] Create FileTreeResponse schema (tree array)
- [ ] Create FileContentResponse schema (path, content, language, size)
- [ ] Document in OpenAPI

**Files to modify/create**:
- `packages/backend/app/schemas/files.py` (new)
- `packages/backend/app/api/files.py`

**Acceptance Criteria**:
- [ ] Schemas match spec
- [ ] OpenAPI docs generated
- [ ] Validation works

---

## Technical Specifications

### FileTreeService Interface

```python
class FileTreeService:
    def __init__(
        self,
        page_service: PageService,
        page_version_service: PageVersionService,
        product_doc_service: ProductDocService
    ):
        pass

    async def get_tree(self, session_id: UUID) -> List[FileTreeNode]:
        """Generate virtual file tree for session."""
        pass

    async def get_file_content(
        self,
        session_id: UUID,
        path: str
    ) -> FileContent | None:
        """Get content of virtual file by path."""
        pass
```

### File Tree Structure

```python
def build_tree(session_id: UUID) -> List[FileTreeNode]:
    """Build virtual file tree."""
    tree = []

    # index.html
    tree.append(FileTreeNode(
        name="index.html",
        path="index.html",
        type="file",
        size=len(index_html)
    ))

    # pages/ directory
    if other_pages:
        pages_dir = FileTreeNode(
            name="pages",
            path="pages",
            type="directory",
            children=[
                FileTreeNode(
                    name=f"{page.slug}.html",
                    path=f"pages/{page.slug}.html",
                    type="file",
                    size=len(page_html)
                )
                for page in other_pages
            ]
        )
        tree.append(pages_dir)

    # assets/ directory
    assets_dir = FileTreeNode(
        name="assets",
        path="assets",
        type="directory",
        children=[
            FileTreeNode(
                name="site.css",
                path="assets/site.css",
                type="file",
                size=len(site_css)
            )
        ]
    )
    tree.append(assets_dir)

    # product-doc.md
    if product_doc:
        tree.append(FileTreeNode(
            name="product-doc.md",
            path="product-doc.md",
            type="file",
            size=len(product_doc.content)
        ))

    return tree
```

### API Response Schemas

```python
class FileTreeNode(BaseModel):
    name: str
    path: str
    type: Literal["file", "directory"]
    size: int | None = None  # Only for files
    children: List["FileTreeNode"] | None = None  # Only for directories

class FileTreeResponse(BaseModel):
    tree: List[FileTreeNode]

class FileContentResponse(BaseModel):
    path: str
    content: str
    language: str  # html, css, javascript, markdown
    size: int
```

### Language Detection

```python
def get_language(path: str) -> str:
    """Determine language from file path."""
    if path.endswith(".html"):
        return "html"
    elif path.endswith(".css"):
        return "css"
    elif path.endswith(".js"):
        return "javascript"
    elif path.endswith(".md"):
        return "markdown"
    else:
        return "plaintext"
```

### Generated site.css Template

```css
/* Site-wide Design System */
/* Generated from global_style */

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

/* Reset & Base */
* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

html, body {
  font-family: var(--font-family), -apple-system, BlinkMacSystemFont, sans-serif;
  font-size: var(--font-size-base);
  line-height: 1.5;
  color: #333;
  background: #fff;
}

body {
  max-width: 430px;
  margin: 0 auto;
  min-height: 100vh;
}

/* Scrollbar Hide Utility */
.hide-scrollbar::-webkit-scrollbar {
  display: none;
}
.hide-scrollbar {
  -ms-overflow-style: none;
  scrollbar-width: none;
}

/* Navigation */
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

.nav-link {
  color: white;
  text-decoration: none;
  white-space: nowrap;
  padding: 8px 16px;
  border-radius: var(--border-radius);
  transition: background 0.2s;
}

.nav-link:hover {
  background: rgba(255, 255, 255, 0.1);
}

.nav-link.active {
  background: rgba(255, 255, 255, 0.2);
}

/* Buttons */
button, .btn {
  min-height: var(--button-height);
  padding: 0 24px;
  border-radius: var(--border-radius);
  font-size: var(--font-size-base);
  cursor: pointer;
  border: none;
  background: var(--primary-color);
  color: white;
}

button:hover, .btn:hover {
  opacity: 0.9;
}

/* Typography */
h1, h2, h3 {
  font-size: var(--font-size-heading);
  line-height: 1.2;
  margin-bottom: calc(var(--spacing-unit) * 2);
}

p {
  margin-bottom: var(--spacing-unit);
}
```

## Testing Requirements

- [ ] Unit tests for tree generation
- [ ] Unit tests for file content generation
- [ ] Unit tests for CSS generation
- [ ] Integration tests for both endpoints
- [ ] Test with empty session
- [ ] Test with single page
- [ ] Test with multiple pages

## Notes & Warnings

- **Virtual Files**: These files don't exist on disk; generated on-demand from DB
- **Caching**: Consider caching generated content (invalidate on page update)
- **Path Encoding**: Handle URL encoding for paths with special characters
- **Size Accuracy**: Size should match actual content byte length
- **CSS Consistency**: site.css must match what's inlined in preview HTML
