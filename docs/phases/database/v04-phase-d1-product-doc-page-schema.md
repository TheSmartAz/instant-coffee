# Phase D1: ProductDoc & Page Schema

## Metadata

- **Category**: Database
- **Priority**: P0 (Critical)
- **Estimated Complexity**: Medium
- **Parallel Development**: ✅ Can develop in parallel
- **Dependencies**:
  - **Blocked by**: None
  - **Blocks**: B1, B2, B3, B4, B5, B6

## Goal

Define and implement the database schema for ProductDoc, Page, and PageVersion tables to support multi-page generation with Product Doc as the source of truth.

## Detailed Tasks

### Task 1: Create ProductDoc Model

**Description**: Define the ProductDoc SQLAlchemy model that stores the project's source of truth document.

**Implementation Details**:
- [ ] Create ProductDoc model with UUID primary key
- [ ] Add session_id foreign key with unique constraint (one ProductDoc per session)
- [ ] Add content field (TEXT) for Markdown content
- [ ] Add structured field (JSON) for structured data
- [ ] Add status enum field (draft / confirmed / outdated)
- [ ] Add created_at and updated_at timestamps
- [ ] Add relationship to Session model

**Files to modify/create**:
- `packages/backend/app/db/models.py`

**Acceptance Criteria**:
- [ ] ProductDoc model defined with all required fields
- [ ] Unique constraint on session_id works correctly
- [ ] Status enum properly restricts values to draft/confirmed/outdated

---

### Task 2: Create Page Model

**Description**: Define the Page SQLAlchemy model that represents individual pages in a multi-page project.

**Implementation Details**:
- [ ] Create Page model with UUID primary key
- [ ] Add session_id foreign key
- [ ] Add title (string) and slug (string, max 40, pattern [a-z0-9-])
- [ ] Add description field (string)
- [ ] Add order_index (int) for page ordering
- [ ] Add current_version_id foreign key (nullable) to PageVersion
- [ ] Add created_at and updated_at timestamps
- [ ] Add unique constraint on (session_id, slug)
- [ ] Add relationship to Session and PageVersion models

**Files to modify/create**:
- `packages/backend/app/db/models.py`

**Acceptance Criteria**:
- [ ] Page model defined with all required fields
- [ ] Unique constraint on (session_id, slug) enforced
- [ ] Slug validation pattern enforced at model or service level

---

### Task 3: Create PageVersion Model

**Description**: Define the PageVersion SQLAlchemy model for version history of individual pages.

**Implementation Details**:
- [ ] Create PageVersion model with auto-increment integer primary key
- [ ] Add page_id foreign key to Page
- [ ] Add version field (int)
- [ ] Add html field (TEXT) for page content
- [ ] Add description field (string) for version notes
- [ ] Add created_at timestamp
- [ ] Add unique constraint on (page_id, version)
- [ ] Add relationship to Page model

**Files to modify/create**:
- `packages/backend/app/db/models.py`

**Acceptance Criteria**:
- [ ] PageVersion model defined with all required fields
- [ ] Unique constraint on (page_id, version) enforced
- [ ] Version numbering works correctly

---

### Task 4: Create Migration Script

**Description**: Create Alembic migration to add the new tables to the database.

**Implementation Details**:
- [ ] Create new Alembic migration file
- [ ] Add CREATE TABLE for product_docs
- [ ] Add CREATE TABLE for pages
- [ ] Add CREATE TABLE for page_versions
- [ ] Add foreign key constraints
- [ ] Add unique constraints
- [ ] Add indexes for common queries (session_id lookups)
- [ ] Test migration up and down

**Files to modify/create**:
- `packages/backend/app/db/migrations/versions/xxx_add_product_doc_page_tables.py`

**Acceptance Criteria**:
- [ ] Migration creates all three tables correctly
- [ ] Migration is reversible (downgrade works)
- [ ] Indexes created for performance

---

### Task 5: Data Migration Script for Existing Sessions

**Description**: Create a script to migrate existing sessions to the new schema.

**Implementation Details**:
- [ ] For each existing Session:
  - [ ] Create ProductDoc (status=confirmed, content from interview context or empty)
  - [ ] Create default Page (title="首页", slug="index", order_index=0)
  - [ ] Convert latest Version to PageVersion v1
  - [ ] Set Page.current_version_id to new PageVersion
- [ ] Handle edge cases (sessions with no versions)
- [ ] Make script idempotent (can run multiple times safely)

**Files to modify/create**:
- `packages/backend/app/db/migrations/data_migration_v04.py`

**Acceptance Criteria**:
- [ ] Existing sessions have ProductDoc created
- [ ] Existing sessions have default "index" page
- [ ] Existing versions converted to PageVersion
- [ ] Script is idempotent

---

## Technical Specifications

### ProductDoc Table Schema

```sql
CREATE TABLE product_docs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL UNIQUE REFERENCES sessions(id) ON DELETE CASCADE,
    content TEXT NOT NULL DEFAULT '',
    structured JSONB NOT NULL DEFAULT '{}',
    status VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'confirmed', 'outdated')),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_product_docs_session_id ON product_docs(session_id);
```

### ProductDoc Structured JSON Schema

```json
{
  "project_name": "string",
  "description": "string",
  "target_audience": "string",
  "goals": ["string"],
  "features": [
    {
      "name": "string",
      "description": "string",
      "priority": "must|should|nice"
    }
  ],
  "design_direction": {
    "style": "string",
    "color_preference": "string",
    "tone": "string",
    "reference_sites": ["string"]
  },
  "pages": [
    {
      "title": "string",
      "slug": "string",
      "purpose": "string",
      "sections": ["string"],
      "required": true
    }
  ],
  "constraints": ["string"]
}
```

### Page Table Schema

```sql
CREATE TABLE pages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    title VARCHAR(100) NOT NULL,
    slug VARCHAR(40) NOT NULL CHECK (slug ~ '^[a-z0-9-]+$'),
    description TEXT NOT NULL DEFAULT '',
    order_index INTEGER NOT NULL DEFAULT 0,
    current_version_id INTEGER REFERENCES page_versions(id) ON DELETE SET NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_id, slug)
);

CREATE INDEX idx_pages_session_id ON pages(session_id);
CREATE INDEX idx_pages_slug ON pages(session_id, slug);
```

### PageVersion Table Schema

```sql
CREATE TABLE page_versions (
    id SERIAL PRIMARY KEY,
    page_id UUID NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    html TEXT NOT NULL,
    description VARCHAR(500),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(page_id, version)
);

CREATE INDEX idx_page_versions_page_id ON page_versions(page_id);
```

## Testing Requirements

- [ ] Unit tests for ProductDoc model CRUD operations
- [ ] Unit tests for Page model CRUD operations
- [ ] Unit tests for PageVersion model CRUD operations
- [ ] Unit tests for unique constraints (should raise on duplicate)
- [ ] Integration test for cascade delete (Session delete cascades to all related)
- [ ] Migration test (up and down)
- [ ] Data migration test with sample existing sessions

## Notes & Warnings

- **SQLite Compatibility**: If using SQLite, JSONB becomes JSON and gen_random_uuid() needs Python-side UUID generation
- **Circular Reference**: Page.current_version_id references PageVersion, but PageVersion.page_id references Page. Handle carefully with deferred FK or post-insert updates
- **Status Enum**: Consider using Python Enum class mapped to database values for type safety
- **Slug Validation**: Pattern `^[a-z0-9-]+$` should be validated both at DB level (CHECK constraint) and service level (before insert)
