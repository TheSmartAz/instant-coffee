# Phase v10-D1: Cross-Session Memory Schema + Analytics Tables

## Metadata

- **Category**: Database
- **Priority**: P0
- **Estimated Complexity**: Medium
- **Parallel Development**: ✅ Can develop in parallel
- **Dependencies**:
  - **Blocked by**: None
  - **Blocks**: v10-B8 (Cross-Session Memory Backend), v10-B11 (Analytics Service)

## Goal

Add database schema support for cross-session user preferences and analytics tracking.

## Detailed Tasks

### Task 1: User Preferences Table

**Description**: Extend the database schema to store user preferences across sessions.

**Implementation Details**:
- [ ] Add `user_preferences` table with fields: session_id, color_scheme, font_family, layout_mode, favorite_components, created_at, updated_at
- [ ] Add preference_columns to sessions table or create separate table
- [ ] Update SQLAlchemy models in packages/backend/app/db/models.py

**Files to modify/create**:
- `packages/backend/app/db/models.py`

**Acceptance Criteria**:
- [ ] User preferences can be stored and retrieved
- [ ] Schema is backward compatible with existing data

---

### Task 2: Page Analytics Table

**Description**: Create table for tracking page analytics (PV, UV, device info, etc.)

**Implementation Details**:
- [ ] Create `page_analytics` table with fields: id, session_id, page_slug, timestamp, visitor_id, device_type, screen_size, referrer, country
- [ ] Create `page_events` table for interaction data: id, session_id, page_slug, event_type, event_data, timestamp
- [ ] Add appropriate indexes for query performance

**Files to modify/create**:
- `packages/backend/app/db/models.py`

**Acceptance Criteria**:
- [ ] Analytics events can be stored
- [ ] Queries for dashboard are performant (indexed)

---

### Task 3: Deploy History Table

**Description**: Track deployment history for version association.

**Implementation Details**:
- [ ] Create `deployments` table: id, session_id, version_id, provider, deploy_url, status, created_at
- [ ] Link to sessions and versions via foreign keys

**Files to modify/create**:
- `packages/backend/app/db/models.py`

**Acceptance Criteria**:
- [ ] Deployment history can be queried by session
- [ ] Version rollback can trigger deployment rollback

## Technical Specifications

### Table Schemas

```python
# User Preferences
class UserPreference(BaseModel):
    session_id: str
    user_id: Optional[str] = None  # Anonymous if not logged in
    color_scheme: Optional[str] = "light"
    font_family: Optional[str] = "Inter"
    layout_mode: Optional[str] = "single"
    favorite_components: list[str] = []
    created_at: datetime
    updated_at: datetime

# Page Analytics
class PageAnalytics(BaseModel):
    id: int
    session_id: str
    page_slug: str
    timestamp: datetime
    visitor_id: str  # Anonymous UUID
    device_type: str  # mobile/desktop/tablet
    screen_width: int
    screen_height: int
    referrer: Optional[str]
    country: Optional[str]

# Deployments
class Deployment(BaseModel):
    id: int
    session_id: str
    version_id: Optional[int]
    provider: str  # netlify/vercel
    deploy_url: str
    status: str  # pending/ready/failed
    created_at: datetime
```

## Testing Requirements

- [ ] Unit tests for model creation
- [ ] Migration script tests

## Notes & Warnings

- Ensure backward compatibility - existing sessions should continue working
- Analytics table may grow large - consider partitioning strategy
