# Phase B2: Page & PageVersion Service

## Metadata

- **Category**: Backend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: Medium
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: D1 (ProductDoc & Page Schema)
  - **Blocks**: B5, B6, B7, F2, F3

## Goal

Implement PageService and PageVersionService to handle multi-page management, version control, and rollback functionality.

## Detailed Tasks

### Task 1: Create PageService Class

**Description**: Implement the core service for Page CRUD operations.

**Implementation Details**:
- [ ] Create PageService class with database session dependency
- [ ] Implement `list_by_session(session_id: UUID) -> List[Page]` (ordered by order_index)
- [ ] Implement `get_by_id(page_id: UUID) -> Page | None`
- [ ] Implement `get_by_slug(session_id: UUID, slug: str) -> Page | None`
- [ ] Implement `create(session_id: UUID, title: str, slug: str, description: str, order_index: int) -> Page`
- [ ] Implement `create_batch(session_id: UUID, pages: List[PageCreate]) -> List[Page]`
- [ ] Implement `update(page_id: UUID, ...) -> Page`
- [ ] Implement `delete(page_id: UUID) -> bool`
- [ ] Add slug validation (pattern: `^[a-z0-9-]+$`, max 40 chars)

**Files to modify/create**:
- `packages/backend/app/services/page.py` (new)

**Acceptance Criteria**:
- [ ] All CRUD methods work correctly
- [ ] Slug validation enforced
- [ ] Batch creation works atomically

---

### Task 2: Create PageVersionService Class

**Description**: Implement version management for pages.

**Implementation Details**:
- [ ] Create PageVersionService class
- [ ] Implement `list_by_page(page_id: UUID) -> List[PageVersion]` (ordered by version desc)
- [ ] Implement `get_current(page_id: UUID) -> PageVersion | None`
- [ ] Implement `get_by_id(version_id: int) -> PageVersion | None`
- [ ] Implement `create(page_id: UUID, html: str, description: str | None) -> PageVersion`
  - Auto-increment version number
  - Update Page.current_version_id
- [ ] Implement `rollback(page_id: UUID, version_id: int) -> PageVersion`
  - Set Page.current_version_id to target version
  - Return the rolled-back version

**Files to modify/create**:
- `packages/backend/app/services/page_version.py` (new)

**Acceptance Criteria**:
- [ ] Version numbers auto-increment correctly
- [ ] Rollback updates current_version_id
- [ ] Version history preserved on rollback

---

### Task 3: Implement Pages API Endpoints

**Description**: Create API endpoints for page management.

**Implementation Details**:
- [ ] `GET /api/sessions/{id}/pages` - List pages for session
- [ ] `GET /api/pages/{page_id}` - Get page details
- [ ] `GET /api/pages/{page_id}/versions` - Get page version history
- [ ] `GET /api/pages/{page_id}/preview` - Get current HTML (self-contained)
- [ ] `POST /api/pages/{page_id}/rollback` - Rollback to specific version
- [ ] Add request/response schemas
- [ ] Add proper error handling (404, 400)

**Files to modify/create**:
- `packages/backend/app/api/pages.py` (new)
- `packages/backend/app/api/__init__.py` (register router)
- `packages/backend/app/schemas/page.py` (new)

**Acceptance Criteria**:
- [ ] All endpoints work correctly
- [ ] Proper status codes returned
- [ ] Response schemas match spec

---

### Task 4: Add Page Events

**Description**: Implement SSE events for page lifecycle.

**Implementation Details**:
- [ ] Add `page_created` event type
- [ ] Add `page_version_created` event type
- [ ] Add `page_preview_ready` event type
- [ ] Emit events from service methods
- [ ] Include session_id, page_id, slug in all events

**Files to modify/create**:
- `packages/backend/app/events/models.py`
- `packages/backend/app/services/page.py`
- `packages/backend/app/services/page_version.py`

**Acceptance Criteria**:
- [ ] Events emitted correctly
- [ ] Events contain all required fields
- [ ] Frontend can track page generation progress

---

### Task 5: Implement Preview HTML Generation

**Description**: Generate self-contained HTML for preview that includes inline CSS.

**Implementation Details**:
- [ ] Create utility to inline global_style CSS into HTML
- [ ] Ensure preview_html is fully self-contained (no external dependencies)
- [ ] Handle missing CSS gracefully
- [ ] Add preview_url support if needed

**Files to modify/create**:
- `packages/backend/app/services/page_version.py`
- `packages/backend/app/utils/html.py` (new)

**Acceptance Criteria**:
- [ ] Preview HTML renders correctly without external resources
- [ ] CSS is properly inlined
- [ ] Preview matches exported version styling

---

## Technical Specifications

### PageService Interface

```python
class PageService:
    def __init__(self, db: Session):
        self.db = db

    async def list_by_session(self, session_id: UUID) -> List[Page]:
        """List all pages for session, ordered by order_index."""
        pass

    async def get_by_id(self, page_id: UUID) -> Page | None:
        """Get page by ID."""
        pass

    async def get_by_slug(self, session_id: UUID, slug: str) -> Page | None:
        """Get page by session ID and slug."""
        pass

    async def create(
        self,
        session_id: UUID,
        title: str,
        slug: str,
        description: str = "",
        order_index: int = 0
    ) -> Page:
        """Create new page."""
        pass

    async def create_batch(
        self,
        session_id: UUID,
        pages: List[PageCreate]
    ) -> List[Page]:
        """Create multiple pages atomically."""
        pass
```

### PageVersionService Interface

```python
class PageVersionService:
    def __init__(self, db: Session):
        self.db = db

    async def list_by_page(self, page_id: UUID) -> List[PageVersion]:
        """List versions for page, newest first."""
        pass

    async def get_current(self, page_id: UUID) -> PageVersion | None:
        """Get current version for page."""
        pass

    async def create(
        self,
        page_id: UUID,
        html: str,
        description: str | None = None
    ) -> PageVersion:
        """Create new version, auto-increment version number."""
        pass

    async def rollback(
        self,
        page_id: UUID,
        version_id: int
    ) -> PageVersion:
        """Rollback page to specific version."""
        pass
```

### API Response Schemas

```python
class PageResponse(BaseModel):
    id: UUID
    session_id: UUID
    title: str
    slug: str
    description: str
    order_index: int
    current_version_id: int | None
    created_at: datetime
    updated_at: datetime

class PageVersionResponse(BaseModel):
    id: int
    page_id: UUID
    version: int
    description: str | None
    created_at: datetime

class PagePreviewResponse(BaseModel):
    page_id: UUID
    slug: str
    html: str
    version: int

class RollbackRequest(BaseModel):
    version_id: int

class RollbackResponse(BaseModel):
    page_id: UUID
    rolled_back_to_version: int
    new_current_version_id: int
```

### Event Payloads

```python
# page_created
{
    "type": "page_created",
    "session_id": "uuid",
    "page_id": "uuid",
    "slug": "string",
    "title": "string"
}

# page_version_created
{
    "type": "page_version_created",
    "session_id": "uuid",
    "page_id": "uuid",
    "slug": "string",
    "version": 1
}

# page_preview_ready
{
    "type": "page_preview_ready",
    "session_id": "uuid",
    "page_id": "uuid",
    "slug": "string",
    "preview_url": "string | null"
}
```

## Testing Requirements

- [ ] Unit tests for PageService CRUD
- [ ] Unit tests for PageVersionService version management
- [ ] Unit tests for slug validation
- [ ] Unit tests for batch creation
- [ ] Unit tests for rollback functionality
- [ ] Integration tests for API endpoints
- [ ] Event emission tests

## Notes & Warnings

- **Slug Uniqueness**: Enforce unique (session_id, slug) at both service and DB level
- **Version Auto-Increment**: Calculate next version from MAX(version) for page + 1
- **Rollback Semantics**: Rollback doesn't create new version, just updates current_version_id pointer
- **Cascade Delete**: Deleting a page should cascade delete all its versions
- **Preview HTML**: Must be self-contained - inline all CSS, no external dependencies
