# Phase B1: ProductDoc Service

## Metadata

- **Category**: Backend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: Medium
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: D1 (ProductDoc & Page Schema)
  - **Blocks**: B3, B5, B7, F1

## Goal

Implement the ProductDocService to handle CRUD operations for ProductDoc, including status management and structured data handling.

## Detailed Tasks

### Task 1: Create ProductDocService Class

**Description**: Implement the core service class for ProductDoc operations.

**Implementation Details**:
- [ ] Create ProductDocService class with database session dependency
- [ ] Implement `get_by_session_id(session_id: UUID) -> ProductDoc | None`
- [ ] Implement `create(session_id: UUID, content: str, structured: dict, status: str) -> ProductDoc`
- [ ] Implement `update(doc_id: UUID, content: str, structured: dict) -> ProductDoc`
- [ ] Implement `update_status(doc_id: UUID, status: str) -> ProductDoc`
- [ ] Add validation for status transitions (draft → confirmed, confirmed → outdated)

**Files to modify/create**:
- `packages/backend/app/services/product_doc.py` (new)

**Acceptance Criteria**:
- [ ] All CRUD methods work correctly
- [ ] Invalid status transitions are rejected
- [ ] Proper error handling for not found cases

---

### Task 2: Implement Structured Data Validation

**Description**: Add Pydantic models for validating ProductDoc structured data.

**Implementation Details**:
- [ ] Create ProductDocStructured Pydantic model
- [ ] Create ProductDocFeature model (name, description, priority)
- [ ] Create DesignDirection model (style, color_preference, tone, reference_sites)
- [ ] Create ProductDocPage model (title, slug, purpose, sections, required)
- [ ] Add validation in service layer before save
- [ ] Handle partial updates (merge existing with new data)

**Files to modify/create**:
- `packages/backend/app/schemas/product_doc.py` (new)
- `packages/backend/app/services/product_doc.py`

**Acceptance Criteria**:
- [ ] Invalid structured data raises validation error
- [ ] Partial updates merge correctly
- [ ] All nested models validate properly

---

### Task 3: Implement ProductDoc API Endpoint

**Description**: Create the GET endpoint for retrieving ProductDoc.

**Implementation Details**:
- [ ] Create `GET /api/sessions/{id}/product-doc` endpoint
- [ ] Return 404 if ProductDoc doesn't exist
- [ ] Return full ProductDoc with content, structured, status
- [ ] Add response schema for API documentation

**Files to modify/create**:
- `packages/backend/app/api/product_doc.py` (new)
- `packages/backend/app/api/__init__.py` (register router)

**Acceptance Criteria**:
- [ ] Endpoint returns ProductDoc correctly
- [ ] 404 returned when not found
- [ ] Response matches spec schema

---

### Task 4: Add ProductDoc Events

**Description**: Implement SSE events for ProductDoc lifecycle.

**Implementation Details**:
- [ ] Add `product_doc_generated` event type
- [ ] Add `product_doc_updated` event type
- [ ] Add `product_doc_confirmed` event type
- [ ] Add `product_doc_outdated` event type
- [ ] Emit events from service methods
- [ ] Include session_id and doc_id in all events

**Files to modify/create**:
- `packages/backend/app/events/models.py`
- `packages/backend/app/services/product_doc.py`

**Acceptance Criteria**:
- [ ] Events emitted on create/update/status change
- [ ] Events contain required fields (session_id, doc_id)
- [ ] Frontend can subscribe to these events

---

## Technical Specifications

### ProductDocService Interface

```python
class ProductDocService:
    def __init__(self, db: Session):
        self.db = db

    async def get_by_session_id(self, session_id: UUID) -> ProductDoc | None:
        """Get ProductDoc by session ID, returns None if not found."""
        pass

    async def create(
        self,
        session_id: UUID,
        content: str,
        structured: dict,
        status: str = "draft"
    ) -> ProductDoc:
        """Create new ProductDoc for session."""
        pass

    async def update(
        self,
        doc_id: UUID,
        content: str | None = None,
        structured: dict | None = None
    ) -> ProductDoc:
        """Update ProductDoc content and/or structured data."""
        pass

    async def update_status(
        self,
        doc_id: UUID,
        status: str
    ) -> ProductDoc:
        """Update ProductDoc status with validation."""
        pass

    async def confirm(self, doc_id: UUID) -> ProductDoc:
        """Confirm ProductDoc (status: draft → confirmed)."""
        pass

    async def mark_outdated(self, doc_id: UUID) -> ProductDoc:
        """Mark ProductDoc as outdated (status: confirmed → outdated)."""
        pass
```

### API Response Schema

```python
class ProductDocResponse(BaseModel):
    id: UUID
    session_id: UUID
    content: str
    structured: dict
    status: str  # draft | confirmed | outdated
    created_at: datetime
    updated_at: datetime
```

### Event Payloads

```python
# product_doc_generated
{
    "type": "product_doc_generated",
    "session_id": "uuid",
    "doc_id": "uuid",
    "status": "draft"
}

# product_doc_updated
{
    "type": "product_doc_updated",
    "session_id": "uuid",
    "doc_id": "uuid",
    "change_summary": "string"  # optional
}

# product_doc_confirmed
{
    "type": "product_doc_confirmed",
    "session_id": "uuid",
    "doc_id": "uuid"
}

# product_doc_outdated
{
    "type": "product_doc_outdated",
    "session_id": "uuid",
    "doc_id": "uuid"
}
```

## Testing Requirements

- [ ] Unit tests for ProductDocService CRUD methods
- [ ] Unit tests for status transition validation
- [ ] Unit tests for structured data validation
- [ ] Integration tests for API endpoint
- [ ] Event emission tests

## Notes & Warnings

- **One ProductDoc Per Session**: Service should enforce this constraint even though DB has unique constraint
- **Status Transitions**: Only allow: draft → confirmed, confirmed → outdated. Reconfirming outdated should reset to confirmed
- **Event Emission**: Ensure events are emitted after successful DB commit, not before
- **Structured Data Merge**: When updating, merge new structured data with existing rather than replace entirely
