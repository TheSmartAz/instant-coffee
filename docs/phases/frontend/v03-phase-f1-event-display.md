# Phase F1: Event Display Enhancement

## Metadata

- **Category**: Frontend
- **Priority**: P1 (Important)
- **Estimated Complexity**: Medium
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: B8 (Tool Event Integration)
  - **Blocks**: None

## Goal

Update the frontend to properly display agent events, tool calls, and tool results with appropriate formatting for both streaming (real-time) and phase-based (summary) display modes.

## Detailed Tasks

### Task 1: Add Tool Call Display Components

**Description**: Create components to display tool calls in the event flow.

**Implementation Details**:
- [ ] Create ToolCallEvent component
- [ ] Display tool name and input parameters
- [ ] Style to distinguish from other events
- [ ] Add icon for tool call indication

**Files to create/modify**:
- `packages/web/src/components/EventFlow/ToolCallEvent.tsx`

**Acceptance Criteria**:
- [ ] Tool calls are clearly visible
- [ ] Input parameters are formatted nicely
- [ ] Tool icon is displayed

### Task 2: Add Tool Result Display Components

**Description**: Create components to display tool results.

**Implementation Details**:
- [ ] Create ToolResultEvent component
- [ ] Display success/failure status
- [ ] Show output or error message
- [ ] Use color coding for status

**Files to create/modify**:
- `packages/web/src/components/EventFlow/ToolResultEvent.tsx`

**Acceptance Criteria**:
- [ ] Success/failure is clearly indicated
- [ ] Output is formatted for readability
- [ ] Errors are highlighted

### Task 3: Update EventItem for Tool Events

**Description**: Extend EventItem component to handle tool events.

**Implementation Details**:
- [ ] Add tool_call event type handling
- [ ] Add tool_result event type handling
- [ ] Render appropriate components for each type

**Files to modify**:
- `packages/web/src/components/EventFlow/EventItem.tsx`

**Acceptance Criteria**:
- [ ] All event types render correctly
- [ ] Unknown events don't crash the UI

### Task 4: Add Streaming vs Phase Display Toggle

**Description**: Allow users to switch between real-time and phase-based display.

**Implementation Details**:
- [ ] Add display mode state (streaming/phase)
- [ ] Create toggle switch in UI
- [ ] Filter events based on mode
- [ ] Phase mode: show only agent_start and agent_end
- [ ] Streaming mode: show all events including progress

**Files to modify**:
- `packages/web/src/components/EventFlow/EventList.tsx`
- `packages/web/src/hooks/useSSE.ts`

**Acceptance Criteria**:
- [ ] Toggle switch works
- [ ] Phase mode shows less detail
- [ ] Streaming mode shows all events

## Technical Specifications

### Tool Call Event Format

```typescript
interface ToolCallEvent {
  type: "tool_call";
  agent_id: string;
  agent_type: string;
  tool_name: string;
  tool_input: Record<string, unknown>;
  timestamp: string;
}
```

### Tool Result Event Format

```typescript
interface ToolResultEvent {
  type: "tool_result";
  agent_id: string;
  agent_type: string;
  tool_name: string;
  success: boolean;
  tool_output?: unknown;
  error?: string;
  timestamp: string;
}
```

### Display Modes

```typescript
type DisplayMode = "streaming" | "phase";

// Phase mode: Show only
// - Agent start/end
// - Task status changes
// - Final results

// Streaming mode: Show everything
// - All phase mode events
// - Agent progress updates
// - Tool calls and results
// - Individual step updates
```

### Component Structure

```tsx
// ToolCallEvent.tsx
export function ToolCallEvent({ event }: { event: ToolCallEvent }) {
  return (
    <div className="tool-call-event">
      <Icon name="wrench" />
      <span className="tool-name">{event.tool_name}</span>
      <pre className="tool-input">{JSON.stringify(event.tool_input, null, 2)}</pre>
    </div>
  );
}

// ToolResultEvent.tsx
export function ToolResultEvent({ event }: { event: ToolResultEvent }) {
  return (
    <div className={`tool-result-event ${event.success ? "success" : "error"}`}>
      <Icon name={event.success ? "check" : "x"} />
      <span className="tool-name">{event.tool_name}</span>
      {event.success ? (
        <pre className="tool-output">{JSON.stringify(event.tool_output, null, 2)}</pre>
      ) : (
        <div className="tool-error">{event.error}</div>
      )}
    </div>
  );
}
```

## Testing Requirements

- [ ] Component renders for tool_call events
- [ ] Component renders for tool_result events
- [ ] Success/failure states display correctly
- [ ] Display mode toggle works
- [ ] Events are filtered correctly in each mode
- [ ] Long tool output is handled gracefully

## Notes & Warnings

1. **Output Size**: Tool output could be large; consider truncation or collapsible sections
2. **Timestamps**: Display relative time for better UX
3. **Collapsible Events**: Tool events could be collapsible to reduce clutter
4. **Animation**: Add subtle animations for new events
5. **Performance**: Consider virtualization if many events are displayed
