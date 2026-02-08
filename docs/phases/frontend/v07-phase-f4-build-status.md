# Phase F4: Build Status UI

## Metadata

- **Category**: Frontend
- **Priority**: P0 (Important)
- **Estimated Complexity**: Low
- **Parallel Development**: ✅ Can start immediately
- **Dependencies**:
  - **Blocked by**: B8 (API Endpoints)
  - **Blocks**: None

## Goal

Implement build status indicators and progress display in the Preview Panel during React SSG builds.

## Detailed Tasks

### Task 1: Create BuildStatusIndicator Component

**Description**: Build visual indicator for build state

**Implementation Details**:
- [ ] Create `packages/web/src/components/custom/BuildStatusIndicator.tsx`
- [ ] Support states: idle, pending, building, success, failed
- [ ] Add animated spinner for building state
- [ ] Show status text
- [ ] Add retry button for failed state

**Files to create**:
- `packages/web/src/components/custom/BuildStatusIndicator.tsx`

**Acceptance Criteria**:
- [ ] All states visually distinct
- [ ] Spinner animates during build
- [ ] Retry button works for failed
- [ ] Click opens details (optional)

---

### Task 2: Implement Build Progress Bar

**Description**: Create detailed progress display with steps

**Implementation Details**:
- [ ] Add progress property to BuildStatusIndicator
- [ ] Show current step (e.g., "Installing dependencies", "Building...")
- [ ] Display percentage (0-100)
- [ ] Show elapsed time
- [ ] Cancel build button

**Files to modify**:
- `packages/web/src/components/custom/BuildStatusIndicator.tsx`

**Acceptance Criteria**:
- [ ] Progress updates in real-time
- [ ] Current step labeled clearly
- [ ] Time elapsed shown
- [ ] Cancel button stops build

---

### Task 3: Integrate with Preview Panel

**Description**: Add build status to PreviewPanel UI

**Implementation Details**:
- [ ] Modify `packages/web/src/components/custom/PreviewPanel.tsx`
- [ ] Add BuildStatusIndicator at top
- [ ] Show status in header bar
- [ ] Disable preview iframe during build
- [ ] Show placeholder during pending

**Files to modify**:
- `packages/web/src/components/custom/PreviewPanel.tsx`

**Acceptance Criteria**:
- [ ] Status visible in PreviewPanel
- [ ] Iframe disabled during build
- [ ] Placeholder shows build progress
- [ ] Preview reloads after success

---

### Task 4: Implement SSE Event Handling

**Description**: Handle build-related SSE events

**Implementation Details**:
- [ ] Update `packages/web/src/hooks/useSSE.ts`
- [ ] Listen for build events: build_start, build_progress, build_complete, build_failed
- [ ] Parse payload for progress percent and message
- [ ] Update React state
- [ ] Handle errors gracefully

**Files to modify**:
- `packages/web/src/hooks/useSSE.ts`

**Acceptance Criteria**:
- [ ] All build events handled
- [ ] Progress state updates correctly
- [ ] Error states display message
- [ ] Connection loss handled

---

### Task 5: Add Pages List Display

**Description**: Show generated pages after successful build

**Implementation Details**:
- [ ] After build_complete, show page list
- [ ] Make each page clickable
- [ ] Show preview for each page
- [ ] Add page selector dropdown
- [ ] Show page count

**Files to modify**:
- `packages/web/src/components/custom/BuildStatusIndicator.tsx`

**Acceptance Criteria**:
- [ ] Pages list appears after build
- [ ] Clicking page shows preview
- [ ] Dropdown for page selection
- [ ] Count displayed

## Technical Specifications

### Build Status Types

```typescript
// types/build.ts
type BuildStatusType = 'idle' | 'pending' | 'building' | 'success' | 'failed';

interface BuildProgress {
  step?: string;
  percent?: number;
  message?: string;
  started_at?: string;
}

interface BuildResult {
  status: BuildStatusType;
  pages?: string[];
  error?: string;
  dist_path?: string;
  progress?: BuildProgress;
}

interface BuildEventPayload {
  status: BuildStatusType;
  pages?: string[];
  error?: string;
  step?: string;
  percent?: number;
  message?: string;
}
```

### BuildStatusIndicator Component

```typescript
// components/custom/BuildStatusIndicator.tsx
interface BuildStatusIndicatorProps {
  status: BuildStatusType;
  progress?: BuildProgress;
  pages?: string[];
  error?: string;
  onRetry?: () => void;
  onCancel?: () => void;
  onPageSelect?: (page: string) => void;
  selectedPage?: string;
}

function BuildStatusIndicator({
  status,
  progress,
  pages,
  error,
  onRetry,
  onCancel,
  onPageSelect,
  selectedPage
}: BuildStatusIndicatorProps) {
  const statusConfig = {
    idle: { icon: '⏸️', color: 'gray', label: '就绪' },
    pending: { icon: '⏳', color: 'yellow', label: '等待中' },
    building: { icon: '🔨', color: 'blue', label: '构建中' },
    success: { icon: '✅', color: 'green', label: '完成' },
    failed: { icon: '❌', color: 'red', label: '失败' }
  };

  const config = statusConfig[status];

  return (
    <div className={`build-status ${status}`}>
      <div className="status-header">
        <span className="icon">{config.icon}</span>
        <span className="label">{config.label}</span>
        {status === 'building' && (
          <button className="cancel-btn" onClick={onCancel}>取消</button>
        )}
      </div>

      {status === 'building' && progress && (
        <div className="build-progress">
          <div className="progress-bar">
            <div
              className="progress-fill"
              style={{ width: `${progress.percent || 0}%` }}
            />
          </div>
          <span className="step">{progress.step || progress.message}</span>
          <span className="percent">{progress.percent || 0}%</span>
        </div>
      )}

      {status === 'failed' && error && (
        <div className="error-message">
          <pre>{error}</pre>
          <button onClick={onRetry}>重试</button>
        </div>
      )}

      {status === 'success' && pages && (
        <div className="pages-list">
          <span className="count">{pages.length} 个页面</span>
          <select onChange={(e) => onPageSelect?.(e.target.value)}>
            <option value="">选择页面</option>
            {pages.map(page => (
              <option key={page} value={page}>{page}</option>
            ))}
          </select>
        </div>
      )}
    </div>
  );
}
```

### SSE Event Handlers

```typescript
// hooks/useSSE.ts
useSSE(sessionId, (event) => {
  switch (event.type) {
    case 'build_start':
      setBuildStatus({ status: 'building', progress: { step: '开始构建' } });
      break;
    case 'build_progress':
      setBuildStatus({
        status: 'building',
        progress: {
          step: event.payload.step,
          percent: event.payload.percent,
          message: event.payload.message
        }
      });
      break;
    case 'build_complete':
      setBuildStatus({
        status: 'success',
        pages: event.payload.pages
      });
      break;
    case 'build_failed':
      setBuildStatus({
        status: 'failed',
        error: event.payload.error
      });
      break;
  }
});
```

## Testing Requirements

- [ ] Unit test: Status indicator renders correctly
- [ ] Unit test: Progress bar calculation
- [ ] Integration test: SSE event handling
- [ ] Test all status transitions
- [ ] Test retry functionality

## Notes & Warnings

- Progress percent may not be linear (npm install, then build)
- Large builds may take time - show elapsed time
- Cancel should stop the build process
- Preview iframe needs refresh after build
