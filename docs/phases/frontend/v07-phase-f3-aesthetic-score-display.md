# Phase F3: Aesthetic Score Display

## Metadata

- **Category**: Frontend
- **Priority**: P1 (Optional but Important)
- **Estimated Complexity**: Medium
- **Parallel Development**: ✅ Can start immediately
- **Dependencies**:
  - **Blocked by**: B7 (Backend Aesthetic Scoring)
  - **Blocks**: None (display-only)

## Goal

Implement UI component to display aesthetic scoring results with visual indicators and actionable suggestions.

## Detailed Tasks

### Task 1: Create AestheticScoreDisplay Component

**Description**: Build the main display component for score results

**Implementation Details**:
- [ ] Create `packages/web/src/components/custom/AestheticScoreCard.tsx`
- [ ] Display overall score (0-100) prominently
- [ ] Show 6 dimension scores with progress bars
- [ ] Display pass/fail status
- [ ] Include suggestion list

**Files to create**:
- `packages/web/src/components/custom/AestheticScoreCard.tsx`

**Acceptance Criteria**:
- [ ] Overall score visible with color coding
- [ ] All 6 dimensions shown
- [ ] Pass/fail badge correct
- [ ] Suggestions expandable

---

### Task 2: Define Score Visualization

**Description**: Create visual elements for score representation

**Implementation Details**:
- [ ] Create ProgressBar component with color
- [ ] Create ScoreGauge component (circular)
- [ ] Create DimensionBadge component
- [ ] Apply color scale: green (>85), yellow (>70), red (<70)
- [ ] Animate scores on load

**Files to create**:
- `packages/web/src/components/ui/AestheticScore.tsx`

**Acceptance Criteria**:
- [ ] Visual design matches spec
- [ ] Colors reflect score levels
- [ ] Animations smooth
- [ ] Responsive layout

---

### Task 3: Implement Suggestions Display

**Description**: Show optimization suggestions with severity and actions

**Implementation Details**:
- [ ] Create SuggestionItem component
- [ ] Color-code by severity: info (blue), warning (yellow), critical (red)
- [ ] Show auto-fixable flag
- [ ] Add "Apply Fix" button for auto-fixable
- [ ] Expandable for details

**Files to modify**:
- `packages/web/src/components/custom/AestheticScoreCard.tsx`

**Acceptance Criteria**:
- [ ] Suggestions readable and actionable
- [ ] Severity colors applied
- [ ] Auto-fix button works
- [ ] Critical items highlighted

---

### Task 4: Integrate with Preview Panel

**Description**: Add score display to PreviewPanel

**Implementation Details**:
- [ ] Modify `packages/web/src/components/custom/PreviewPanel.tsx`
- [ ] Add collapsible "Aesthetic Score" section
- [ ] Show score after build completes
- [ ] Persist visibility in localStorage
- [ ] Handle disabled state gracefully

**Files to modify**:
- `packages/web/src/components/custom/PreviewPanel.tsx`

**Acceptance Criteria**:
- [ ] Score visible in PreviewPanel
- [ ] Collapsible works
- [ ] Loading state while scoring
- [ ] Empty state when not scored

---

### Task 5: Add Score Event Handling

**Description**: Handle SSE events for aesthetic score updates

**Implementation Details**:
- [ ] Update `packages/web/src/hooks/useSSE.ts`
- [ ] Listen for 'aesthetic_score' event
- [ ] Parse payload into score structure
- [ ] Update React state
- [ ] Trigger re-render

**Files to modify**:
- `packages/web/src/hooks/useSSE.ts`

**Acceptance Criteria**:
- [ ] SSE events received correctly
- [ ] State updated with new scores
- [ ] Error handling for malformed events
- [ ] Debounced updates (if many events)

## Technical Specifications

### Aesthetic Score Interface

```typescript
// types/aesthetic.ts
interface AestheticScore {
  overall: number;              // 0-100
  dimensions: {
    visualHierarchy: number;
    colorHarmony: number;
    spacingConsistency: number;
    alignment: number;
    readability: number;
    mobileAdaptation: number;
  };
  suggestions: AestheticSuggestion[];
  passThreshold: boolean;
}

interface AestheticSuggestion {
  dimension: string;
  severity: 'info' | 'warning' | 'critical';
  message: string;
  location?: string;
  autoFixable: boolean;
}

interface AestheticScoreDisplay {
  showInPreview: boolean;
  expandedByDefault: boolean;
  showSuggestions: boolean;
  allowAutoFix: boolean;
}
```

### Score Color Scale

```typescript
const SCORE_COLORS = {
  excellent: '#22C55E',  // >= 85
  good: '#84CC16',        // 70-84
  fair: '#F59E0B',        // 60-69
  poor: '#EF4444',        // < 60
};

const SEVERITY_COLORS = {
  info: '#3B82F6',
  warning: '#F59E0B',
  critical: '#EF4444',
};
```

### AestheticScoreCard Component

```typescript
// components/custom/AestheticScoreCard.tsx
interface AestheticScoreCardProps {
  score: AestheticScore;
  expanded?: boolean;
  onApplyFix?: (suggestion: AestheticSuggestion) => void;
}

function AestheticScoreCard({ score, expanded = false, onApplyFix }: AestheticScoreCardProps) {
  return (
    <div className="aesthetic-score-card">
      <div className="score-header">
        <div className="overall-score">
          <ScoreGauge value={score.overall} />
          <span className="pass-badge">
            {score.passThreshold ? '✅ 通过' : '⚠️ 建议优化'}
          </span>
        </div>
      </div>

      <div className="dimensions">
        {Object.entries(score.dimensions).map(([dim, value]) => (
          <div key={dim} className="dimension">
            <span className="dim-label">{formatDimensionName(dim)}</span>
            <ProgressBar value={value} color={getScoreColor(value)} />
            <span className="dim-value">{value}</span>
          </div>
        ))}
      </div>

      <div className="suggestions">
        {score.suggestions.map((suggestion, i) => (
          <SuggestionItem
            key={i}
            suggestion={suggestion}
            onApplyFix={onApplyFix}
          />
        ))}
      </div>
    </div>
  );
}
```

## Testing Requirements

- [ ] Unit test: ScoreCard renders with all elements
- [ ] Unit test: Color scaling logic
- [ ] Integration test: SSE event handling
- [ ] Test with various score values
- [ ] Test auto-fix button state

## Notes & Warnings

- Feature is optional - gracefully handle when disabled
- ScoreCard should be collapsible to save space
- Auto-fix should show confirmation before applying
- Consider animation for score reveal
