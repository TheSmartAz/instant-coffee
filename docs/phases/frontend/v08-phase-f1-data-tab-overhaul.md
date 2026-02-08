# Phase F1: Data Tab Frontend Overhaul

## Metadata

- **Category**: Frontend
- **Priority**: P0
- **Estimated Complexity**: High
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: v08-B7 (App Data API)
  - **Blocks**: None

## Goal

Promote Data Tab to a top-level tab in WorkbenchPanel (alongside Preview, Code, Product Doc), rewrite it with Table view and Dashboard view, and create the `useAppData` hook that fetches structured data from the backend API instead of reading raw JSON from iframe postMessage.

## Detailed Tasks

### Task 1: Promote Data Tab to Top-Level Tab

**Description**: Move Data Tab from inside PreviewPanel to a sibling tab in WorkbenchPanel.

**Implementation Details**:
- [ ] Modify `packages/web/src/components/custom/WorkbenchPanel.tsx`:
  - Add "Data" as 4th tab: `[Preview] [Code] [Product Doc] [Data]`
  - Render `DataTab` component when Data tab is active
- [ ] Modify `packages/web/src/components/custom/PreviewPanel.tsx`:
  - Remove internal Data toggle/view
  - PreviewPanel only shows preview content

**Files to modify/create**:
- `packages/web/src/components/custom/WorkbenchPanel.tsx`
- `packages/web/src/components/custom/PreviewPanel.tsx`

**Acceptance Criteria**:
- [ ] Data tab visible as top-level tab
- [ ] PreviewPanel no longer contains Data toggle
- [ ] Tab switching works correctly

---

### Task 2: Create `useAppData` Hook

**Description**: Implement the data fetching hook for app data API.

**Implementation Details**:
- [ ] Create `packages/web/src/hooks/useAppData.ts`
- [ ] Implement:
  - `tables` — list of tables with column definitions (from `GET /api/sessions/{id}/data/tables`)
  - `activeTable` — currently selected table name
  - `records` — paginated records for active table
  - `stats` — aggregation stats for active table
  - `isLoading` — loading state
  - `selectTable(name)` — switch active table
  - `refreshTable()` — re-fetch current table data
  - `pagination` — `{ page, pageSize, total }`
- [ ] Auto-refresh when receiving postMessage from iframe (data_changed event)
- [ ] Handle errors gracefully (show empty state with error message)

**Files to modify/create**:
- `packages/web/src/hooks/useAppData.ts`

**Acceptance Criteria**:
- [ ] Hook fetches tables list on mount
- [ ] Table selection triggers record fetch
- [ ] Pagination works (page navigation)
- [ ] Auto-refresh on iframe data_changed message
- [ ] Loading and error states handled

---

### Task 3: Rewrite DataTab with Table View

**Description**: Implement the Table view for structured data display.

**Implementation Details**:
- [ ] Rewrite `packages/web/src/components/custom/DataTab.tsx`
- [ ] Add view toggle: `[Table View] [Dashboard View]`
- [ ] Table View:
  - Table selector (tabs/buttons for each entity table)
  - Data grid with columns from table schema
  - Pagination controls (`< 1 2 3 >` with total count)
  - Handle JSONB columns (array/object) with expandable display
- [ ] Use `useAppData` hook for data

**Files to modify/create**:
- `packages/web/src/components/custom/DataTab.tsx`

**Acceptance Criteria**:
- [ ] Table selector shows all available tables
- [ ] Data grid displays records with correct columns
- [ ] Pagination navigates through records
- [ ] JSONB fields displayed readably
- [ ] Empty state when no data

---

### Task 4: Implement Dashboard View

**Description**: Add Dashboard view with summary cards and basic charts.

**Implementation Details**:
- [ ] In DataTab, when Dashboard view is active:
  - Summary cards: record count per table, numeric field sums
  - Status distribution (if applicable): simple bar/pie visualization
  - Use stats endpoint data
- [ ] Keep it simple — use CSS-based charts or minimal chart library
- [ ] Dashboard auto-refreshes with table data

**Files to modify/create**:
- `packages/web/src/components/custom/DataTab.tsx`

**Acceptance Criteria**:
- [ ] Summary cards show counts and sums
- [ ] Distribution visualization renders
- [ ] Dashboard updates when data changes
- [ ] Graceful display when stats unavailable

---

### Task 5: Update Event Types

**Description**: Add new event types to frontend type definitions.

**Implementation Details**:
- [ ] Update `packages/web/src/types/events.ts`:
  - Add run lifecycle events: `run_created`, `run_started`, `run_waiting_input`, `run_resumed`, `run_completed`, `run_failed`, `run_cancelled`
  - Add verify events: `verify_start`, `verify_pass`, `verify_fail`
  - Add policy events: `tool_policy_blocked`, `tool_policy_warn`
- [ ] Update `packages/web/src/hooks/useSSE.ts`:
  - Dedup key should prefer `run_id + seq` when available

**Files to modify/create**:
- `packages/web/src/types/events.ts`
- `packages/web/src/hooks/useSSE.ts`

**Acceptance Criteria**:
- [ ] All new event types defined in TypeScript
- [ ] SSE hook handles new events without errors
- [ ] Dedup works with run_id + seq

---

### Task 6: Data Source Migration

**Description**: Switch Data Tab from postMessage-based raw JSON to API-based structured data.

**Implementation Details**:
- [ ] Remove direct postMessage data reading from DataTab
- [ ] Use `useAppData` hook exclusively for data
- [ ] Keep postMessage listener only for refresh triggers
- [ ] Update `usePreviewBridge` if needed to remove data forwarding

**Files to modify/create**:
- `packages/web/src/components/custom/DataTab.tsx`
- `packages/web/src/hooks/usePreviewBridge.ts` (if needed)

**Acceptance Criteria**:
- [ ] DataTab reads from API, not postMessage
- [ ] postMessage only triggers refresh
- [ ] No regression in preview functionality

## Technical Specifications

### WorkbenchPanel Tab Structure

```
[Preview] [Code] [Product Doc] [Data]
```

### useAppData Hook Interface

```typescript
interface UseAppDataReturn {
  tables: TableInfo[];        // {name: string, columns: ColumnInfo[]}
  activeTable: string | null;
  records: Record<string, any>[];
  stats: TableStats | null;
  isLoading: boolean;
  selectTable: (name: string) => void;
  refreshTable: () => void;
  pagination: {
    page: number;
    pageSize: number;
    total: number;
  };
}
```

### Data Tab Layout

```
┌──────────────────────────────────────────┐
│ [Table View] [Dashboard View]  toggle     │
├──────────────────────────────────────────┤
│ Table View:                               │
│  [Order] [MenuItem] [Customer]  selector  │
│  ┌──┬──────────┬────────┬──────────┐     │
│  │id│ items    │ total  │ status   │     │
│  ├──┼──────────┼────────┼──────────┤     │
│  │1 │ [...]    │ 128.00 │ pending  │     │
│  └──┴──────────┴────────┴──────────┘     │
│  [< 1 2 3 >]  共 45 条                    │
│                                           │
│ Dashboard View:                           │
│  ┌──────────┐ ┌──────────┐               │
│  │ Orders   │ │ Revenue  │               │
│  │   45     │ │ ¥3,280   │               │
│  └──────────┘ └──────────┘               │
└──────────────────────────────────────────┘
```

### New Event Types (TypeScript)

```typescript
type RunEventType =
  | 'run_created' | 'run_started' | 'run_waiting_input'
  | 'run_resumed' | 'run_completed' | 'run_failed' | 'run_cancelled';

type VerifyEventType = 'verify_start' | 'verify_pass' | 'verify_fail';

type PolicyEventType = 'tool_policy_blocked' | 'tool_policy_warn';
```

## Testing Requirements

- [ ] Unit test: useAppData hook fetches tables
- [ ] Unit test: useAppData pagination
- [ ] Unit test: useAppData auto-refresh on postMessage
- [ ] Unit test: DataTab renders table view
- [ ] Unit test: DataTab renders dashboard view
- [ ] Unit test: WorkbenchPanel shows 4 tabs
- [ ] Unit test: new event types parsed correctly
- [ ] E2E test: generate app → data appears in Data Tab

## Notes & Warnings

- Keep Dashboard view simple — avoid heavy chart libraries
- JSONB columns may contain deeply nested data — limit display depth
- postMessage listener must be cleaned up on unmount to prevent memory leaks
- Pagination page size should be reasonable (25-50 records)
