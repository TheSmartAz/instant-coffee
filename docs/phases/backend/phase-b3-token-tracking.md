# Phase B3: Token Tracking & Stats Service

## Metadata

- **Category**: Backend
- **Priority**: P1 (Important)
- **Estimated Complexity**: Low
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: D1 (Core Schema)
  - **Blocks**: F4 (Stats Command)

## Goal

Build token consumption tracking and statistics service. Records every AI API call's token usage and provides aggregated statistics for cost transparency.

## Detailed Tasks

### Task 1: Create Token Tracker Service

**Description**: Build the TokenTrackerService for recording and querying token usage.

**Implementation Details**:
- [ ] Create TokenTrackerService class
- [ ] Implement record_usage() to log API calls
- [ ] Implement calculate_cost() with Claude pricing (input: $3, output: $15 per million)
- [ ] Add get_session_stats() for per-session statistics
- [ ] Add get_today_stats() for daily statistics
- [ ] Add get_week_stats() for weekly statistics
- [ ] Add get_total_stats() for all-time statistics

**Files to modify/create**:
- `packages/backend/app/services/token_tracker.py`

**Acceptance Criteria**:
- [ ] Token usage is accurately recorded for each API call
- [ ] Cost calculation uses correct Claude Sonnet 4 pricing
- [ ] Statistics are correctly aggregated by time period
- [ ] Can query by session, date range, or agent type

---

### Task 2: Integrate Token Tracking with Agents

**Description**: Add token tracking hooks to all agent API calls.

**Implementation Details**:
- [ ] Modify BaseAgent to call TokenTrackerService after API calls
- [ ] Extract token counts from Claude API responses
- [ ] Pass session_id and agent_type to tracker
- [ ] Handle API call failures (don't record failed calls)

**Files to modify/create**:
- `packages/backend/app/agents/base.py` (modify existing)

**Acceptance Criteria**:
- [ ] Every successful API call is tracked
- [ ] Failed API calls are not recorded
- [ ] Token counts match Claude API response
- [ ] Correct agent_type is recorded

---

### Task 3: Create Stats API Endpoints

**Description**: Build REST API endpoints for statistics queries.

**Implementation Details**:
- [ ] Implement GET /api/stats (overall statistics)
- [ ] Implement GET /api/stats/today (today's statistics)
- [ ] Implement GET /api/stats/week (this week's statistics)
- [ ] Implement GET /api/stats/session/{id} (per-session statistics)
- [ ] Return formatted data with tokens and costs

**Files to modify/create**:
- `packages/backend/app/api/stats.py`

**Acceptance Criteria**:
- [ ] All endpoints return correct aggregated data
- [ ] Costs are calculated accurately
- [ ] Response includes breakdown by agent type
- [ ] Handles empty data gracefully

## Technical Specifications

### Token Cost Calculation

```python
# Claude Sonnet 4 Pricing (2025-01)
INPUT_COST_PER_MILLION = 3.0   # $3 per million input tokens
OUTPUT_COST_PER_MILLION = 15.0  # $15 per million output tokens

def calculate_cost(input_tokens: int, output_tokens: int) -> float:
    """Calculate USD cost for token usage"""
    input_cost = (input_tokens / 1_000_000) * INPUT_COST_PER_MILLION
    output_cost = (output_tokens / 1_000_000) * OUTPUT_COST_PER_MILLION
    return input_cost + output_cost
```

### API Response Format

#### GET /api/stats
```json
{
  "today": {
    "tokens": 3456,
    "cost_usd": 0.0086,
    "calls": 12
  },
  "week": {
    "tokens": 12345,
    "cost_usd": 0.0309,
    "calls": 45
  },
  "total": {
    "tokens": 45678,
    "cost_usd": 0.1142,
    "calls": 156,
    "sessions": 23
  },
  "by_agent": {
    "interview": { "tokens": 15234, "cost_usd": 0.0381 },
    "generation": { "tokens": 25123, "cost_usd": 0.0628 },
    "refinement": { "tokens": 5321, "cost_usd": 0.0133 }
  }
}
```

#### GET /api/stats/session/{id}
```json
{
  "session_id": "abc123",
  "total_tokens": 1234,
  "cost_usd": 0.0031,
  "calls": 5,
  "by_agent": {
    "interview": { "tokens": 456, "calls": 2 },
    "generation": { "tokens": 678, "calls": 1 },
    "refinement": { "tokens": 100, "calls": 2 }
  },
  "timeline": [
    {
      "timestamp": "2025-01-30T14:15:00Z",
      "agent_type": "interview",
      "tokens": 128
    }
  ]
}
```

## Testing Requirements

- [ ] Test token recording for each agent type
- [ ] Test cost calculation accuracy
- [ ] Test statistics aggregation (today, week, total)
- [ ] Test per-session statistics
- [ ] Test empty data handling
- [ ] Test concurrent token recording

## Notes & Warnings

- **Pricing**: Keep pricing constants updated with Claude API changes
- **Precision**: Use float for cost_usd, maintain 4-5 decimal places
- **Failed Calls**: Do NOT record failed API attempts
- **Timezone**: All timestamps should be UTC
- **Performance**: Add indexes on timestamp for fast aggregation queries
