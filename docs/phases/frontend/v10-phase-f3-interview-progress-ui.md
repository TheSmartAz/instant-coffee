# Phase v10-F3: Interview Progress Indicator UI

## Metadata

- **Category**: Frontend
- **Priority**: P1
- **Estimated Complexity**: Low
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: v10-B7 (Interview Progress Backend)
  - **Blocks**: None (UI enhancement)

## Goal

Display interview progress in InterviewWidget for better UX.

## Detailed Tasks

### Task 1: Update InterviewWidget

**Description**: Add progress indicator to interview UI.

**Implementation Details**:
- [ ] Read round_number from event
- [ ] Read estimated_total_rounds from event
- [ ] Display progress bar

**Files to modify**:
- `packages/web/src/components/custom/InterviewWidget.tsx`

**UI Example**:
```
第 2 步 / 共 3 步: 视觉风格
━━━━━━━━━━━━━━━━━━━━━━●
```

**Acceptance Criteria**:
- [ ] Progress displayed correctly
- [ ] User knows current phase

## Technical Specifications

### Event Data

```typescript
interface QuestionAskedEvent {
  round_number?: number;
  estimated_total_rounds?: number;
}
```

### UI Structure

```tsx
{round_number && estimated_total_rounds && (
  <div className="progress-indicator">
    <span>第 {round_number} 步 / 共 {estimated_total_rounds} 步</span>
    <ProgressBar value={round_number / estimated_total_rounds} />
  </div>
)}
```

## Testing Requirements

- [ ] Test progress display
- [ ] Test with missing data (optional fields)

## Notes & Warning

- Backend is v10-B7
- Make fields optional for backward compatibility
