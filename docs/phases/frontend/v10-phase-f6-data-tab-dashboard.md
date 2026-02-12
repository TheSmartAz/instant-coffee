# Phase v10-F6: Data Tab Dashboard

## Metadata

- **Category**: Frontend
- **Priority**: P0
- **Estimated Complexity**: High
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: v10-B11 (Analytics Backend)
  - **Blocks**: None (final feature)

## Goal

Build analytics dashboard with charts for page performance.

## Detailed Tasks

### Task 1: Install charting library

**Description**: Add recharts for data visualization.

**Implementation Details**:
- [ ] Run `npm install recharts`
- [ ] Verify installation

**Files to modify**:
- `packages/web/package.json`

**Acceptance Criteria**:
- [ ] Library installed

---

### Task 2: Create Dashboard components

**Description**: Build chart components for analytics.

**Implementation Details**:
- [ ] TrendChart - line chart for PV/UV over time
- [ ] DevicePieChart - pie chart for device distribution
- [ ] TopPagesTable - ranking of popular pages
- [ ] RealtimeFeed - live visitor activity

**Files to create**:
- `packages/web/src/components/analytics/TrendChart.tsx`
- `packages/web/src/components/analytics/DevicePieChart.tsx`
- `packages/web/src/components/analytics/TopPagesTable.tsx`
- `packages/web/src/components/analytics/RealtimeFeed.tsx`

**Acceptance Criteria**:
- [ ] All charts render

---

### Task 3: Integrate with DataTab

**Description**: Connect charts to analytics API.

**Implementation Details**:
- [ ] Fetch data from /api/analytics/:session_id
- [ ] Pass to chart components
- [ ] Add loading/error states

**Files to modify**:
- `packages/web/src/components/custom/WorkbenchPanel.tsx` (DataTab section)

**Acceptance Criteria**:
- [ ] Data displays correctly

---

### Task 4: Add export functionality

**Description**: Allow exporting analytics data.

**Implementation Details**:
- [ ] Export to CSV
- [ ] Export to JSON

**Files to modify**:
- `packages/web/src/components/analytics/`

**Acceptance Criteria**:
- [ ] Export works

## Technical Specifications

### Dashboard Layout

```
┌─────────────────────────────────────────────┐
│ Analytics Dashboard                    [Export ▼]
├─────────────────────────────────────────────┤
│  [Today ▼] [Last 7 Days ▼] [Last 30 Days ▼]
├─────────────────────────────────────────────┤
│  PV/UV Trend                               │
│  ┌─────────────────────────────────────┐    │
│  │     📈 Line Chart                   │    │
│  └─────────────────────────────────────┘    │
├──────────────────────┬──────────────────────┤
│ Device Distribution  │  Top Pages           │
│  ┌──────────────┐    │  ┌────────────┐      │
│  │   Pie Chart  │    │  │ Table      │      │
│  └──────────────┘    │  └────────────┘      │
└──────────────────────┴──────────────────────┘
```

### API Response Format

```json
{
  "trends": [
    { "date": "2026-02-01", "pv": 100, "uv": 50 },
    { "date": "2026-02-02", "pv": 150, "uv": 75 }
  ],
  "devices": [
    { "type": "mobile", "count": 1000 },
    { "type": "desktop", "count": 300 }
  ],
  "top_pages": [
    { "page": "/home", "pv": 500 },
    { "page": "/about", "pv": 200 }
  ]
}
```

## Testing Requirements

- [ ] Test charts render
- [ ] Test data fetching
- [ ] Test export

## Notes & Warning

- Feature flag: USE_ANALYTICS
- Backend is v10-B11
- Handle empty states gracefully
