# Phase v10-B11: Analytics Service

## Metadata

- **Category**: Backend
- **Priority**: P0
- **Estimated Complexity**: High
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: v10-D1 (Analytics Schema)
  - **Blocks**: v10-F6 (Data Tab Dashboard)

## Goal

Create analytics service for tracking page views and interactions.

## Detailed Tasks

### Task 1: Create AnalyticsService

**Description**: Service for storing and querying analytics.

**Implementation Details**:
- [ ] Create packages/backend/app/services/analytics.py
- [ ] Implement track_page_view()
- [ ] Implement track_event()
- [ ] Implement get_analytics()

**Files to create**:
- `packages/backend/app/services/analytics.py`

**Acceptance Criteria**:
- [ ] Events stored correctly

---

### Task 2: Create analytics API

**Description**: Endpoints for analytics data.

**Implementation Details**:
- [ ] POST /api/analytics/track - for tracking
- [ ] GET /api/analytics/:session_id - for dashboard data
- [ ] Implement aggregation queries

**Files to create**:
- `packages/backend/app/api/analytics.py`

**Acceptance Criteria**:
- [ ] Data queryable for dashboard

---

### Task 3: Generate tracking script

**Description**: Create lightweight tracking script for embedding.

**Implementation Details**:
- [ ] Create script template < 2KB
- [ ] Track: PV, UV, device, screen, referrer
- [ ] Send to /api/analytics/track

**Files to create**:
- `packages/backend/app/services/analytics.py` (template)
- Or separate file for template

**Acceptance Criteria**:
- [ ] Script < 2KB
- [ ] Tracks all required metrics

## Technical Specifications

### Tracking Script Requirements

| Metric | Collection Method |
|--------|-------------------|
| PV | Page load event |
| UV | Anonymous UUID in localStorage |
| Device | navigator.userAgent parsing |
| Screen | window.screen dimensions |
| Referrer | document.referrer |
| Scroll depth | scroll event tracking |

### API Endpoints

```
POST /api/analytics/track
  Body: { event_type, page_slug, visitor_id, device_info, ... }

GET /api/analytics/:session_id
  Query: { start_date, end_date, metrics }
  Response: { trends: [], pie_chart: [], realtime: [] }
```

## Testing Requirements

- [ ] Test event storage
- [ ] Test dashboard queries
- [ ] Test script size

## Notes & Warnings

- Feature flag: USE_ANALYTICS
- Default off - privacy concern
- Consider data retention policy
