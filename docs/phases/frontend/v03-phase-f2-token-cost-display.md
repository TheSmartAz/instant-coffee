# Phase F2: Token Cost Display

## Metadata

- **Category**: Frontend
- **Priority**: P1 (Important)
- **Estimated Complexity**: Low
- **Parallel Development**: ✅ Can develop in parallel
- **Dependencies**:
  - **Blocked by**: None
  - **Blocks**: None

## Goal

Add token usage and cost display to the frontend, showing breakdown by agent type and total session cost.

## Detailed Tasks

### Task 1: Add Token Usage to Types

**Description**: Extend type definitions for token usage data.

**Implementation Details**:
- [ ] Add TokenUsage interface to types
- [ ] Include input_tokens, output_tokens, total_tokens, cost_usd
- [ ] Add to event types if needed

**Files to modify**:
- `packages/web/src/types/index.ts`
- `packages/web/src/types/events.ts`

**Acceptance Criteria**:
- [ ] Token usage types are defined
- [ ] Types match backend response format

### Task 2: Create TokenDisplay Component

**Description**: Component to display token usage and cost.

**Implementation Details**:
- [ ] Create TokenDisplay component
- [ ] Show total tokens used
- [ ] Show total cost in USD
- [ ] Break down by agent type (interview, generation, refinement)
- [ ] Use appropriate formatting

**Files to create**:
- `packages/web/src/components/TokenDisplay.tsx`

**Acceptance Criteria**:
- [ ] Total tokens are displayed
- [ ] Cost is shown with proper formatting
- [ ] Breakdown by agent is visible

### Task 3: Add Token Display to Session Summary

**Description**: Integrate token display into session completion view.

**Implementation Details**:
- [ ] Add TokenDisplay to session completion
- [ ] Show after generation completes
- [ ] Make it collapsible for cleaner UI

**Files to modify**:
- `packages/web/src/pages/ExecutionPage.tsx`

**Acceptance Criteria**:
- [ ] Token display appears at session end
- [ ] Can be collapsed if needed
- [ ] Updates as session progresses

### Task 4: Add Token Usage to Agent Cards

**Description**: Show per-agent token usage in task cards.

**Implementation Details**:
- [ ] Add token usage to TaskCard component
- [ ] Show input/output token breakdown
- [ ] Use progress bar for visualization

**Files to modify**:
- `packages/web/src/components/TaskCard/TaskCard.tsx`

**Acceptance Criteria**:
- [ ] Each task card shows its token usage
- [ ] Visual representation is clear

## Technical Specifications

### Token Usage Type

```typescript
interface TokenUsage {
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  cost_usd: number;
}

interface AgentTokenUsage {
  agent_type: "interview" | "generation" | "refinement";
  usage: TokenUsage;
}

interface SessionTokenSummary {
  total: TokenUsage;
  by_agent: Record<string, TokenUsage>;
}
```

### TokenDisplay Component

```tsx
interface TokenDisplayProps {
  usage: SessionTokenSummary;
  showDetails?: boolean;
}

export function TokenDisplay({ usage, showDetails = false }: TokenDisplayProps) {
  return (
    <div className="token-display">
      <div className="token-summary">
        <span className="token-total">{usage.total.total_tokens.toLocaleString()} tokens</span>
        <span className="token-cost">${usage.total.cost_usd.toFixed(4)}</span>
      </div>
      {showDetails && (
        <div className="token-breakdown">
          {Object.entries(usage.by_agent).map(([agent, agentUsage]) => (
            <div key={agent} className="agent-tokens">
              <span className="agent-name">{agent}</span>
              <span className="agent-tokens">{agentUsage.total_tokens}</span>
              <span className="agent-cost">${agentUsage.cost_usd.toFixed(4)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

### Display Format

```
┌─────────────────────────────────────┐
│ Token Usage                         │
├─────────────────────────────────────┤
│ Total: 12,345 tokens                │
│ Cost: $0.0234                       │
│                                     │
│ ▼ Breakdown                         │
│   Interview:  1,234 tokens ($0.001) │
│   Generation: 10,000 tokens ($0.02) │
│   Refinement: 1,111 tokens ($0.002) │
└─────────────────────────────────────┘
```

## Testing Requirements

- [ ] Component renders with token data
- [ ] Zero tokens displays correctly
- [ ] Cost formatting handles small values
- [ ] Collapsed/expanded states work
- [ ] Integration with session data works

## Notes & Warnings

1. **Cost Formatting**: Use at least 4 decimal places for small costs
2. **Privacy**: Token usage is not sensitive; safe to display
3. **Real-time Updates**: Token usage may update during session
4. **Threshold**: Consider hiding token display for very small costs
5. **Currency**: Always show USD as per backend calculation
