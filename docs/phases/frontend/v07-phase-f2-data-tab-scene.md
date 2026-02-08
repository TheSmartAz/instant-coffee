# Phase F2: Data Tab Scene Classification

## Metadata

- **Category**: Frontend
- **Priority**: P0 (Important)
- **Estimated Complexity**: Medium
- **Parallel Development**: ✅ Can start immediately
- **Dependencies**:
  - **Blocked by**: None
  - **Blocks**: None (standalone enhancement)

## Goal

Update Data Tab to display events filtered by scenario type with appropriate icons and colors.

## Detailed Tasks

### Task 1: Update DataTab Component Structure

**Description**: Add scene selector and event filtering to DataTab

**Implementation Details**:
- [ ] Modify `packages/web/src/components/custom/DataTab.tsx`
- [ ] Add scene selector dropdown at top
- [ ] Filter events based on selected scene
- [ ] Show "All Events" option
- [ ] Persist selected scene in localStorage

**Files to modify**:
- `packages/web/src/components/custom/DataTab.tsx`

**Acceptance Criteria**:
- [ ] Scene selector visible
- [ ] Events filter correctly by scene
- [ ] All Events option shows everything
- [ ] Selection persists across page loads

---

### Task 2: Define Event Type Categories

**Description**: Create mapping of event types to scenes with labels and icons

**Implementation Details**:
- [ ] Create `packages/web/src/types/events.ts` updates
- [ ] Define EVENT_CATEGORIES constant
- [ ] Define EVENT_LABELS with icon/color
- [ ] Add scene colors for visual distinction

**Files to modify**:
- `packages/web/src/types/events.ts`

**Acceptance Criteria**:
- [ ] All 5 scenes have event type lists
- [ ] Each event has label, icon, color
- [ ] Types match spec section 11.3

---

### Task 3: Implement Event Filtering Logic

**Description**: Filter and categorize events in DataTab

**Implementation Details**:
- [ ] Add filterEvents(events, scene) function
- [ ] Group events by type
- [ ] Sort by timestamp descending
- [ ] Show empty state when no events

**Files to modify**:
- `packages/web/src/components/custom/DataTab.tsx`

**Acceptance Criteria**:
- [ ] Events grouped by category
- [ ] Empty state shows when no data
- [ ] Event count per type shown
- [ ] Search/filter within events (bonus)

---

### Task 4: Style Event Display

**Description**: Apply scene-specific styling to event items

**Implementation Details**:
- [ ] Update event item component styling
- [ ] Apply scene colors to borders/badges
- [ ] Add icons for event types
- [ ] Format timestamps readably
- [ ] Add expand/collapse for event details

**Files to modify**:
- `packages/web/src/components/custom/DataTab.tsx`

**Acceptance Criteria**:
- [ ] Events visually distinct by scene
- [ ] Icons make events scannable
- [ ] Timestamps formatted correctly
- [ ] Details expand on click

---

### Task 5: Update Data Store Integration

**Description**: Ensure postMessage bridge sends correct event structure

**Implementation Details**:
- [ ] Modify `packages/web/src/hooks/useDataStore.ts`
- [ ] Ensure events include scene type
- [ ] Validate event structure matches backend
- [ ] Add data sync from iframe preview

**Files to modify**:
- `packages/web/src/hooks/useDataStore.ts`

**Acceptance Criteria**:
- [ ] Events received from iframe
- [ ] Scene type included in event object
- [ ] LocalStorage persistence works
- [ ] Real-time updates via postMessage

## Technical Specifications

### Event Categories Mapping

```typescript
// types/events.ts
type EventType =
  // 通用
  | 'page_view'
  | 'click'
  // 电商
  | 'add_to_cart'
  | 'remove_from_cart'
  | 'checkout_start'
  | 'order_submitted'
  | 'payment_success'
  // 旅行
  | 'save_plan'
  | 'share_link'
  | 'add_bookmark'
  // 说明书
  | 'search'
  | 'reading_progress'
  // 看板
  | 'task_created'
  | 'task_moved'
  | 'task_completed'
  // Landing
  | 'lead_submitted'
  | 'cta_click';

const EVENT_CATEGORIES: Record<string, EventType[]> = {
  ecommerce: ['add_to_cart', 'remove_from_cart', 'checkout_start', 'order_submitted', 'payment_success'],
  travel: ['save_plan', 'share_link', 'add_bookmark'],
  manual: ['page_view', 'search', 'reading_progress'],
  kanban: ['task_created', 'task_moved', 'task_completed'],
  landing: ['lead_submitted', 'cta_click']
};

const EVENT_LABELS: Record<EventType, { label: string; icon: string; color: string }> = {
  add_to_cart: { label: '加入购物车', icon: '🛒', color: 'blue' },
  order_submitted: { label: '订单提交', icon: '📦', color: 'green' },
  task_created: { label: '任务创建', icon: '✅', color: 'purple' },
  lead_submitted: { label: '线索提交', icon: '📧', color: 'orange' },
  // ... all other events
};
```

### DataTab Component Structure

```typescript
// components/custom/DataTab.tsx
interface DataTabProps {
  sessionId: string;
}

interface EventItem {
  id: string;
  type: EventType;
  timestamp: string;
  payload: Record<string, any>;
  page?: string;
}

function DataTab({ sessionId }: DataTabProps) {
  const [selectedScene, setSelectedScene] = useState<string>('all');
  const [events, setEvents] = useState<EventItem[]>([]);

  const filteredEvents = useMemo(() => {
    if (selectedScene === 'all') return events;
    const sceneEventTypes = EVENT_CATEGORIES[selectedScene] || [];
    return events.filter(e => sceneEventTypes.includes(e.type));
  }, [events, selectedScene]);

  const groupedEvents = useMemo(() => {
    const groups: Record<string, EventItem[]> = {};
    for (const event of filteredEvents) {
      if (!groups[event.type]) groups[event.type] = [];
      groups[event.type].push(event);
    }
    return groups;
  }, [filteredEvents]);

  return (
    <div className="data-tab">
      <SceneSelector
        selected={selectedScene}
        onChange={setSelectedScene}
      />
      <div className="event-list">
        {Object.entries(groupedEvents).map(([type, typeEvents]) => (
          <EventGroup
            key={type}
            type={type}
            events={typeEvents}
            label={EVENT_LABELS[type as EventType]}
          />
        ))}
      </div>
    </div>
  );
}
```

### Scene Colors

```typescript
const SCENE_COLORS: Record<string, string> = {
  ecommerce: '#3B82F6',    // blue
  travel: '#10B981',       // green
  manual: '#8B5CF6',        // purple
  kanban: '#F59E0B',       // amber
  landing: '#EC4899'        // pink
};
```

## Testing Requirements

- [ ] Unit test: Event category filtering
- [ ] Unit test: EVENT_LABELS completeness
- [ ] Integration test: DataTab with sample events
- [ ] Test postMessage bridge event receiving
- [ ] Test scene selector persistence

## Notes & Warnings

- Events should be limited to last 100 per session (for performance)
- Consider pagination for large event lists
- Scene auto-detection from product_doc (bonus)
- Export events to JSON (bonus feature)
