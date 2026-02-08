# Phase F1: Data Tab UI

## Metadata

- **Category**: Frontend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: Medium
- **Parallel Development**: ✅ Can develop in parallel
- **Dependencies**:
  - **Blocked by**: None
  - **Blocks**: None

## Goal

Create a Data Tab in the Preview Panel that displays real-time state, events, and records from the preview iframe via postMessage.

## Detailed Tasks

### Task 1: Create Data Tab Component

**Description**: Build the DataTab component with three sections (State, Events, Records).

**Implementation Details**:
- [ ] Create `DataTab.tsx` component
- [ ] Add State section showing JSON state
- [ ] Add Events section showing event log
- [ ] Add Records section showing submitted data
- [ ] Add collapse/expand for each section

**Files to modify/create**:
- `packages/web/src/components/custom/DataTab.tsx` (new file)

**Acceptance Criteria**:
- [ ] Component renders in Preview Panel
- [ ] Three sections visible by default
- [ ] Each section collapsible
- [ ] Empty state shown when no data

### Task 2: Add JSON Syntax Highlighting

**Description**: Format state JSON with syntax highlighting for readability.

**Implementation Details**:
- [ ] Add syntax highlighting library or custom implementation
- [ ] Format JSON with proper indentation
- [ ] Add copy-to-clipboard button
- [ ] Handle large objects with collapsible nodes

**Files to modify/create**:
- `packages/web/src/components/custom/DataTab.tsx`

**Acceptance Criteria**:
- [ ] JSON is formatted and readable
- [ ] Colors highlight keys, strings, numbers
- [ ] Copy button works
- [ ] Large objects can be collapsed

### Task 3: Add Events List View

**Description**: Display events in a scrollable list with timestamps.

**Implementation Details**:
- [ ] Render events as list items
- [ ] Show timestamp, event name, data preview
- [ ] Newest events at top
- [ ] Auto-scroll on new events

**Files to modify/create**:
- `packages/web/src/components/custom/DataTab.tsx`

**Acceptance Criteria**:
- [ ] Events display in reverse chronological order
- [ ] Timestamps formatted human-readable
- [ ] Data truncated if too long
- [ ] Auto-scrolls to top on new event

### Task 4: Add Records View

**Description**: Display submitted records (orders, bookings, forms) in a card/table view.

**Implementation Details**:
- [ ] Create record card component
- [ ] Show record type, timestamp, key data
- [ ] Support different record types visually
- [ ] Add export button

**Files to modify/create**:
- `packages/web/src/components/custom/DataTab.tsx`

**Acceptance Criteria**:
- [ ] Each record shows type and date
- [ ] Different types have visual distinction
- [ ] Key data visible (order total, booking date, etc.)
- [ ] Export downloads JSON file

### Task 5: Add postMessage Listener

**Description**: Listen for messages from preview iframe with state/events/records.

**Implementation Details**:
- [ ] Add window message listener
- [ ] Filter for 'instant-coffee:update' type
- [ ] Update component state on message
- [ ] Handle iframe unload (clear data)

**Files to modify/create**:
- `packages/web/src/hooks/usePreviewBridge.ts` (new file)
- `packages/web/src/components/custom/DataTab.tsx`

**Acceptance Criteria**:
- [ ] Receives messages from iframe
- [ ] Updates UI with received data
- [ ] Clears data on iframe unload
- [ ] Filters messages by type

### Task 6: Integrate Data Tab into Preview Panel

**Description**: Add Data Tab to Preview Panel tab navigation.

**Implementation Details**:
- [ ] Add "Data" tab option
- [ ] Include DataTab component in tab content
- [ ] Sync tab state with preview visibility
- [ ] Update tab count badges

**Files to modify/create**:
- `packages/web/src/components/custom/PreviewPanel.tsx` (update)

**Acceptance Criteria**:
- [ ] Data Tab appears in tab list
- [ ] Tab switches correctly
- [ ] Data visible when preview loaded
- [ ] Tab content updates when preview changes

## Technical Specifications

### Component Structure

```tsx
// DataTab.tsx
interface DataTabProps {
  previewUrl?: string;
}

interface PreviewData {
  state: Record<string, unknown>;
  events: Array<{ name: string; data: unknown; timestamp: number }>;
  records: Array<{ type: string; payload: unknown; created_at: string }>;
}

export function DataTab({ previewUrl }: DataTabProps) {
  const [data, setData] = useState<PreviewData>({
    state: {},
    events: [],
    records: []
  });
  const [activeSection, setActiveSection] = useState<'state' | 'events' | 'records'>('state');

  // Message listener hook
  usePreviewBridge(setData);

  return (
    <div className="data-tab">
      <Tabs value={activeSection} onValueChange={setActiveSection}>
        <TabsList>
          <TabsTrigger value="state">State</TabsTrigger>
          <TabsTrigger value="events">Events ({data.events.length})</TabsTrigger>
          <TabsTrigger value="records">Records ({data.records.length})</TabsTrigger>
        </TabsList>

        <TabsContent value="state">
          <JsonViewer data={data.state} />
        </TabsContent>

        <TabsContent value="events">
          <EventList events={data.events} />
        </TabsContent>

        <TabsContent value="records">
          <RecordsList records={data.records} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
```

### Message Protocol

```typescript
interface PreviewMessage {
  type: 'instant-coffee:update';
  state: Record<string, unknown>;
  events: EventData[];
  records: RecordData[];
  timestamp: number;
}

interface EventData {
  name: string;
  data: unknown;
  timestamp: number;
}

interface RecordData {
  type: 'order_submitted' | 'booking_submitted' | 'form_submission';
  payload: unknown;
  created_at: string;  // ISO 8601
}
```

### usePreviewBridge Hook

```typescript
export function usePreviewBridge(
  onUpdate: (data: PreviewData) => void,
  enabled: boolean = true
) {
  useEffect(() => {
    if (!enabled) return;

    const handleMessage = (event: MessageEvent) => {
      if (event.data.type === 'instant-coffee:update') {
        onUpdate({
          state: event.data.state,
          events: event.data.events || [],
          records: event.data.records || []
        });
      }
    };

    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, [enabled, onUpdate]);
}
```

### JSON Viewer Component

```tsx
interface JsonViewerProps {
  data: unknown;
  expandLevel?: number;
}

function JsonViewer({ data, expandLevel = 2 }: JsonViewerProps) {
  const [expanded, setExpanded] = useState(true);

  return (
    <div className="json-viewer">
      <div className="json-header">
        <button onClick={() => setExpanded(!expanded)}>
          {expanded ? '▼' : '▶'}
        </button>
        <button onClick={() => navigator.clipboard.writeText(JSON.stringify(data, null, 2))}>
          Copy
        </button>
      </div>
      {expanded && (
        <pre className="json-content">
          <code>{JSON.stringify(data, null, 2)}</code>
        </pre>
      )}
    </div>
  );
}
```

## Testing Requirements

- [ ] Unit tests for DataTab component rendering
- [ ] Tests for JSON formatting
- [ ] Tests for event list sorting
- [ ] Tests for record display
- [ ] Integration tests for postMessage handling

## Notes & Warnings

- postMessage origin should be validated in production
- Large state objects may cause performance issues - consider virtualization
- Events list should have a max limit (e.g., 100 items) to prevent memory issues
- Records should persist even when preview URL changes (same session)
- Consider adding a "Clear Data" button for debugging
- Export should download as JSON with timestamp in filename
- Do not display internal skill IDs, style profile IDs, or guardrail metadata in the Data Tab UI
