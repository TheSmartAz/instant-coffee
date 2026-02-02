# Phase v05-F4: 事件恢复与 SSE 合并 - 前端事件流持久化

## Metadata

- **Category**: Frontend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: High
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: v05-B4, v05-F3
  - **Blocks**: None

## Goal

实现前端事件恢复功能，页面加载时拉取历史事件并与实时 SSE 合并，支持 Interview 组件和事件列表的恢复。

## Detailed Tasks

### Task 1: 历史事件加载

**Description**: 页面加载时拉取历史结构化事件

**Implementation Details**:
- [ ] 在 useChat 或 useSSE 中添加历史事件加载
- [ ] 调用 GET /api/sessions/{session_id}/events
- [ ] 获取按 seq 排序的事件列表
- [ ] 存储到事件状态中
- [ ] 处理加载状态和错误

**Files to modify/create**:
- `packages/web/src/hooks/useChat.ts`
- `packages/web/src/hooks/useSSE.ts` (新建或扩展)

**Acceptance Criteria**:
- [ ] 历史事件在页面加载时自动获取
- [ ] 事件按正确顺序排列
- [ ] 加载状态正确显示

---

### Task 2: SSE 与历史事件合并

**Description**: 实时 SSE 事件与历史事件的合并逻辑

**Implementation Details**:
- [ ] 实现事件合并逻辑
- [ ] 历史事件 + 实时事件 = 完整事件流
- [ ] 根据 seq 或时间戳排序
- [ ] 去重处理 (同一事件不重复)
- [ ] Delta 事件仅实时展示，不持久化

**Files to modify/create**:
- `packages/web/src/hooks/useSSE.ts`

**Acceptance Criteria**:
- [ ] 历史和实时事件正确合并
- [ ] 事件顺序正确
- [ ] 无重复事件

---

### Task 3: Interview 组件恢复

**Description**: 从历史事件恢复 Interview 组件状态

**Implementation Details**:
- [ ] 解析历史事件中的 interview_question 和 interview_answer
- [ ] 重建 Interview 问答列表
- [ ] 恢复当前问题状态
- [ ] 支持历史问答的查看
- [ ] InterviewWidget 显示历史问答

**Files to modify/create**:
- `packages/web/src/hooks/useChat.ts`
- `packages/web/src/components/custom/InterviewWidget.tsx`

**Acceptance Criteria**:
- [ ] 刷新后 Interview 问答可见
- [ ] 当前问题状态正确
- [ ] 历史问答可查看

---

### Task 4: EventList 恢复

**Description**: 从历史事件恢复事件列表展示

**Implementation Details**:
- [ ] EventList 组件加载历史事件
- [ ] 展示 agent_start, agent_complete, tool_call 等事件
- [ ] 合并实时事件显示
- [ ] 支持事件展开/折叠
- [ ] 事件可按时间过滤

**Files to modify/create**:
- `packages/web/src/components/EventFlow/EventList.tsx`
- `packages/web/src/hooks/useSSE.ts`

**Acceptance Criteria**:
- [ ] 刷新后事件列表可见
- [ ] 历史和实时事件都显示
- [ ] 事件顺序正确

---

### Task 5: 事件类型扩展

**Description**: 扩展事件类型定义支持新增事件

**Implementation Details**:
- [ ] 添加 SessionEvent 基础类型
- [ ] 扩展现有事件类型
- [ ] 添加 seq 和 source 字段
- [ ] 支持版本相关事件 (version_created, snapshot_created)

**Files to modify/create**:
- `packages/web/src/types/events.ts`

**Acceptance Criteria**:
- [ ] 新事件类型正确定义
- [ ] seq 和 source 字段存在
- [ ] 类型检查通过

---

### Task 6: Delta 仅实时展示

**Description**: 确保 Delta 事件仅用于实时展示

**Implementation Details**:
- [ ] Delta 事件不入库，不加入历史
- [ ] Delta 仅在 SSE 实时流中显示
- [ ] 刷新后 Delta 不恢复 (由完整消息替代)
- [ ] 事件恢复逻辑忽略 Delta

**Files to modify/create**:
- `packages/web/src/hooks/useSSE.ts`
- `packages/web/src/components/EventFlow/EventList.tsx`

**Acceptance Criteria**:
- [ ] Delta 实时显示正常
- [ ] 刷新后 Delta 不显示
- [ ] 完整消息正确显示

## Technical Specifications

### 事件合并逻辑

```typescript
interface EventMergeState {
  historicalEvents: SessionEvent[];  // from API
  realtimeEvents: ServerEvent[];     // from SSE
  mergedEvents: MergedEvent[];
}

function mergeEvents(
  historical: SessionEvent[],
  realtime: ServerEvent[]
): MergedEvent[] {
  // 1. 历史事件已按 seq 排序
  // 2. 实时事件按时间追加
  // 3. 去重: 同 seq 或同 id 的事件取其一
  // 4. Delta 事件仅实时，不加入历史
  return [...historical, ...realtime.filter(e => e.type !== 'delta')];
}
```

### useSSE Hook

```typescript
const useSSE = (sessionId: string) => {
  const [historicalEvents, setHistoricalEvents] = useState<SessionEvent[]>([]);
  const [realtimeEvents, setRealtimeEvents] = useState<ServerEvent[]>([]);
  const [connected, setConnected] = useState(false);

  // 加载历史事件
  useEffect(() => {
    loadHistoricalEvents(sessionId).then(setHistoricalEvents);
  }, [sessionId]);

  // 连接 SSE
  useEffect(() => {
    const es = connectSSE(sessionId);
    es.onMessage((event) => {
      setRealtimeEvents(prev => [...prev, event]);
    });
    return () => es.disconnect();
  }, [sessionId]);

  // 合并事件
  const mergedEvents = useMemo(() =>
    mergeEvents(historicalEvents, realtimeEvents),
    [historicalEvents, realtimeEvents]
  );

  return { mergedEvents, connected };
};
```

### 事件类型

```typescript
interface SessionEvent {
  id: number;
  session_id: string;
  seq: number;
  type: string;
  payload: unknown;
  source: 'session' | 'plan' | 'task';
  created_at: string;
}

// 需要恢复的事件类型
type RecoverableEventType =
  | 'interview_question'
  | 'interview_answer'
  | 'agent_start'
  | 'agent_complete'
  | 'tool_call'
  | 'tool_result'
  | 'plan_created'
  | 'task_started'
  | 'task_completed'
  | 'task_failed'
  | 'version_created'
  | 'snapshot_created';
```

## Testing Requirements

- [ ] 单元测试: 事件合并逻辑
- [ ] 集成测试: 历史事件加载
- [ ] 集成测试: SSE 连接
- [ ] E2E 测试: 刷新后 Interview 恢复
- [ ] E2E 测试: 刷新后 EventList 恢复

## Notes & Warnings

1. **Delta 不持久化**: Delta 仅实时展示，刷新后由完整消息替代
2. **Seq 顺序**: 合并事件时按 seq 或时间戳排序
3. **性能考虑**: 大量历史事件可能影响性能，考虑分页或虚拟滚动
4. **Interview 状态**: 确保 Interview 当前问题状态正确恢复
5. **事件去重**: 避免历史和实时事件重复
