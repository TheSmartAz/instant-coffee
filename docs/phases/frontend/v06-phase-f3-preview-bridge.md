# Phase F3: Preview Message Bridge

## Metadata

- **Category**: Frontend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: Low
- **Parallel Development**: ✅ Can develop in parallel
- **Dependencies**:
  - **Blocked by**: None
  - **Blocks**: None

## Goal

Create a reusable hook and utilities for handling postMessage communication between the preview iframe and parent window for the Data Tab.

## Detailed Tasks

### Task 1: Create usePreviewBridge Hook

**Description**: Build a React hook for handling postMessage from preview iframe.

**Implementation Details**:
- [ ] Create `usePreviewBridge.ts` hook
- [ ] Listen for window message events
- [ ] Filter messages by type ('instant-coffee:update')
- [ ] Parse and validate message data
- [ ] Return data and connection status

**Files to modify/create**:
- `packages/web/src/hooks/usePreviewBridge.ts` (new file)

**Acceptance Criteria**:
- [ ] Hook returns current state, events, records
- [ ] Hook returns connection status (connected/disconnected)
- [ ] Messages filtered by type
- [ ] Listener cleanup on unmount

### Task 2: Add Message Type Guards

**Description**: Create TypeScript type guards for message validation.

**Implementation Details**:
- [ ] Define PreviewMessage interface
- [ ] Create isPreviewMessage type guard
- [ ] Validate message structure
- [ ] Handle malformed messages gracefully

**Files to modify/create**:
- `packages/web/src/hooks/usePreviewBridge.ts`

**Acceptance Criteria**:
- [ ] Type guard checks message structure
- [ ] Returns false for malformed messages
- [ ] TypeScript types inferred correctly

### Task 3: Handle Iframe Lifecycle Events

**Description**: Detect when iframe loads/unloads and update connection status.

**Implementation Details**:
- [ ] Detect iframe load event
- [ ] Detect iframe unload event
- [ ] Clear data when iframe unloads
- [ ] Set connection status accordingly

**Files to modify/create**:
- `packages/web/src/hooks/usePreviewBridge.ts`

**Acceptance Criteria**:
- [ ] Connection status reflects iframe state
- [ ] Data cleared on iframe unload
- [ ] Ready to receive messages on iframe load

### Task 4: Add Debouncing for State Updates

**Description**: Debounce rapid state updates to prevent excessive re-renders.

**Implementation Details**:
- [ ] Add 100ms debounce for state updates
- [ ] Immediate updates for submit events
- [ ] Configurable debounce duration

**Files to modify/create**:
- `packages/web/src/hooks/usePreviewBridge.ts`

**Acceptance Criteria**:
- [ ] State updates debounced by default
- [ ] Submit events trigger immediate update
- [ ] No update spam from rapid changes

## Technical Specifications

### Hook Interface

```typescript
interface PreviewData {
  state: Record<string, unknown>;
  events: EventData[];
  records: RecordData[];
}

interface PreviewBridgeState {
  data: PreviewData;
  connected: boolean;
  lastUpdate: number | null;
}

interface UsePreviewBridgeOptions {
  debounceMs?: number;
  onMessage?: (data: PreviewData) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
}

function usePreviewBridge(
  iframeRef: RefObject<HTMLIFrameElement>,
  options: UsePreviewBridgeOptions = {}
): PreviewBridgeState {
  // Implementation
}
```

### Message Type

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
  created_at: string;
}
```

### Type Guard

```typescript
function isPreviewMessage(msg: unknown): msg is PreviewMessage {
  return (
    typeof msg === 'object' &&
    msg !== null &&
    'type' in msg &&
    msg.type === 'instant-coffee:update' &&
    'state' in msg &&
    'events' in msg &&
    'records' in msg &&
    'timestamp' in msg
  );
}
```

### Hook Implementation

```typescript
import { useEffect, useState, useRef, useCallback } from 'react';

export function usePreviewBridge(
  iframeRef: RefObject<HTMLIFrameElement>,
  options: UsePreviewBridgeOptions = {}
): PreviewBridgeState {
  const { debounceMs = 100, onMessage, onConnect, onDisconnect } = options;

  const [data, setData] = useState<PreviewData>({
    state: {},
    events: [],
    records: []
  });
  const [connected, setConnected] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<number | null>(null);

  const debounceTimerRef = useRef<number>();
  const pendingDataRef = useRef<PreviewData | null>(null);

  const updateData = useCallback((newData: PreviewData, immediate = false) => {
    if (immediate) {
      setData(newData);
      setLastUpdate(Date.now());
      onMessage?.(newData);
    } else {
      pendingDataRef.current = newData;
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
      debounceTimerRef.current = window.setTimeout(() => {
        if (pendingDataRef.current) {
          setData(pendingDataRef.current);
          setLastUpdate(Date.now());
          onMessage?.(pendingDataRef.current);
          pendingDataRef.current = null;
        }
      }, debounceMs);
    }
  }, [debounceMs, onMessage]);

  useEffect(() => {
    const iframe = iframeRef.current;
    if (!iframe) return;

    // Handle iframe load
    const handleLoad = () => {
      setConnected(true);
      onConnect?.();
    };

    // Handle iframe unload
    const handleUnload = () => {
      setConnected(false);
      setData({ state: {}, events: [], records: [] });
      setLastUpdate(null);
      onDisconnect?.();
    };

    // Handle postMessage
    const handleMessage = (event: MessageEvent) => {
      // Validate origin in production
      if (process.env.NODE_ENV === 'production' && event.origin !== window.location.origin) {
        return;
      }

      if (!isPreviewMessage(event.data)) {
        return;
      }

      // Check if this is a submit event (immediate update)
      const hasSubmitEvent = event.data.events.some(e =>
        e.name.includes('submit') || e.name.includes('checkout')
      );

      updateData({
        state: event.data.state,
        events: event.data.events,
        records: event.data.records
      }, hasSubmitEvent);
    };

    iframe.addEventListener('load', handleLoad);
    iframe.addEventListener('unload', handleUnload);
    window.addEventListener('message', handleMessage);

    return () => {
      iframe.removeEventListener('load', handleLoad);
      iframe.removeEventListener('unload', handleUnload);
      window.removeEventListener('message', handleMessage);
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, [iframeRef, updateData, onConnect, onDisconnect]);

  return {
    data,
    connected,
    lastUpdate
  };
}
```

### Usage Example

```tsx
import { usePreviewBridge } from '@/hooks/usePreviewBridge';

function PreviewPanel() {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const { data, connected, lastUpdate } = usePreviewBridge(iframeRef, {
    debounceMs: 100,
    onConnect: () => console.log('Preview connected'),
    onDisconnect: () => console.log('Preview disconnected')
  });

  return (
    <div className="preview-panel">
      <div className="status">
        {connected ? (
          <span className="status-connected">● Live</span>
        ) : (
          <span className="status-disconnected">○ Offline</span>
        )}
        {lastUpdate && (
          <span className="last-update">
            Updated {new Date(lastUpdate).toLocaleTimeString()}
          </span>
        )}
      </div>

      <iframe ref={iframeRef} src={previewUrl} />

      <DataTab data={data} />
    </div>
  );
}
```

## Testing Requirements

- [ ] Unit tests for usePreviewBridge hook
- [ ] Tests for message type guard
- [ ] Tests for debouncing behavior
- [ ] Tests for iframe lifecycle handling
- [ ] Integration tests with iframe postMessage

## Notes & Warnings

- In production, always validate message origin
- Debouncing prevents UI freeze from rapid updates
- Submit events should bypass debounce for immediate feedback
- Clear data on iframe unload to show stale state
- Consider adding a "simulator" mode for development without real iframe
- The iframe must use window.parent.postMessage() for communication
- Message target origin should be specific in production
