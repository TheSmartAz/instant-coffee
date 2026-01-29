# Phase F4: Stats Command Implementation

## Metadata

- **Category**: Frontend (CLI)
- **Priority**: P1 (Important)
- **Estimated Complexity**: Low
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: F1 (CLI Framework), B3 (Token Tracking)
  - **Blocks**: None

## Goal

Build the stats command to display token usage statistics with formatted tables, cost calculations, and breakdowns by time period and agent type.

## Detailed Tasks

### Task 1: Implement Stats Command

**Description**: Create command to display overall token statistics.

**Implementation Details**:
- [ ] Create stats command
- [ ] Fetch statistics from API
- [ ] Display today's usage
- [ ] Display this week's usage
- [ ] Display total usage
- [ ] Show breakdown by agent type
- [ ] Format costs with appropriate decimal places

**Files to modify/create**:
- `packages/cli/src/commands/stats.ts`

**Acceptance Criteria**:
- [ ] Statistics are displayed in clear format
- [ ] Costs are shown in USD with 4-5 decimals
- [ ] Breakdown by agent type is visible
- [ ] Numbers are formatted with thousand separators

---

### Task 2: Implement Session Stats View

**Description**: Add support for per-session statistics.

**Implementation Details**:
- [ ] Accept session ID as optional argument
- [ ] Fetch session-specific statistics
- [ ] Display total tokens and cost for session
- [ ] Show breakdown by agent type
- [ ] Display timeline of API calls
- [ ] Show average tokens per call

**Files to modify/create**:
- `packages/cli/src/commands/stats/session.ts`

**Acceptance Criteria**:
- [ ] Session stats display correctly
- [ ] Timeline shows all API calls
- [ ] Agent breakdown is accurate
- [ ] Handles non-existent sessions

---

### Task 3: Create Stats Formatter

**Description**: Build utility for formatting statistics output.

**Implementation Details**:
- [ ] Create formatters for numbers (1,234)
- [ ] Create formatters for costs ($0.0031)
- [ ] Create formatters for percentages (23.4%)
- [ ] Build table layout helpers
- [ ] Add color coding for different metrics

**Files to modify/create**:
- `packages/cli/src/utils/stats-formatter.ts`

**Acceptance Criteria**:
- [ ] Numbers are formatted consistently
- [ ] Costs display with proper precision
- [ ] Tables are aligned and readable
- [ ] Colors enhance readability

## Technical Specifications

### Stats Command Output

```bash
$ instant-coffee stats

📊 Token 使用统计
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

今日消耗:
  Tokens: 3,456
  成本: $0.0086
  API 调用: 12 次

本周消耗:
  Tokens: 12,345
  成本: $0.0309
  API 调用: 45 次

总计消耗:
  Tokens: 45,678
  成本: $0.1142
  API 调用: 156 次
  会话数: 23

按 Agent 类型统计:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Agent       | Tokens    | 成本      | 占比
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Interview   | 15,234    | $0.0381  | 33.4%
Generation  | 25,123    | $0.0628  | 55.0%
Refinement  | 5,321     | $0.0133  | 11.6%
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Session Stats Output

```bash
$ instant-coffee stats abc123

会话 abc123 的 Token 消耗
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

会话信息:
  标题: 活动报名页面
  创建时间: 2025-01-30 14:15
  总消耗: 1,234 tokens ($0.0031)
  API 调用: 5 次
  平均每次: 247 tokens

按 Agent 类型:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Agent       | Tokens | 调用次数 | 平均
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Interview   | 456    | 2       | 228
Generation  | 678    | 1       | 678
Refinement  | 100    | 2       | 50
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

调用时间线:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[14:15:22] Interview   | 128 tokens | $0.00032
[14:16:01] Interview   | 328 tokens | $0.00082
[14:16:45] Generation  | 678 tokens | $0.00170
[14:23:12] Refinement  | 50 tokens  | $0.00013
[14:24:05] Refinement  | 50 tokens  | $0.00013
```

### Number Formatting Functions

```typescript
function formatNumber(n: number): string {
  return n.toLocaleString('en-US');
}

function formatCost(cost: number): string {
  return `$${cost.toFixed(5)}`;
}

function formatPercentage(value: number, total: number): string {
  return `${((value / total) * 100).toFixed(1)}%`;
}
```

## Testing Requirements

- [ ] Test overall stats display
- [ ] Test per-session stats
- [ ] Test number formatting
- [ ] Test cost calculations
- [ ] Test percentage calculations
- [ ] Test empty data handling
- [ ] Test large numbers formatting

## Notes & Warnings

- **Cost Precision**: Use 4-5 decimal places for small costs (e.g., $0.00032)
- **Number Formatting**: Use thousand separators (1,234 not 1234)
- **Percentages**: Round to 1 decimal place (33.4% not 33.37%)
- **Empty Data**: Handle cases with no usage data gracefully
- **Timeline**: Display times in local timezone
- **Table Alignment**: Ensure columns are properly aligned
