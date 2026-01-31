# Phase F4: Task 卡片视图

## Metadata

- **Category**: Frontend
- **Priority**: P1 (Important)
- **Estimated Complexity**: Medium
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: F2 (SSE 事件消费), B3 (并行执行引擎)
  - **Blocks**: None

## Goal

实现 Task 卡片视图，展示每个 Task 的详细执行过程，包括 Agent 活动、工具调用、进度等信息。

## Detailed Tasks

### Task 1: 创建 TaskCard 组件

**Description**: 实现单个 Task 的卡片容器

**Implementation Details**:
- [ ] 创建 TaskCard 组件
- [ ] 显示 Task 标题和状态
- [ ] 显示执行进度条
- [ ] 实现展开/折叠功能

**Files to modify/create**:
- `packages/web/src/components/TaskCard/TaskCard.tsx`

**Acceptance Criteria**:
- [ ] 卡片显示 Task 基本信息
- [ ] 进度条实时更新
- [ ] 可以展开查看详情

---

### Task 2: 创建 AgentActivity 组件

**Description**: 显示 Agent 执行活动

**Implementation Details**:
- [ ] 创建 AgentActivity 组件
- [ ] 显示 Agent 类型和状态
- [ ] 显示当前执行消息
- [ ] 支持多 Agent 并行显示

**Files to modify/create**:
- `packages/web/src/components/TaskCard/AgentActivity.tsx`

**Acceptance Criteria**:
- [ ] 显示 Agent 类型图标
- [ ] 实时显示执行消息
- [ ] 多 Agent 时正确布局

---

### Task 3: 创建 ToolCallLog 组件

**Description**: 显示工具调用日志

**Implementation Details**:
- [ ] 创建 ToolCallLog 组件
- [ ] 显示工具名称和参数
- [ ] 显示工具返回结果
- [ ] 支持折叠长内容

**Files to modify/create**:
- `packages/web/src/components/TaskCard/ToolCallLog.tsx`

**Acceptance Criteria**:
- [ ] 工具调用清晰展示
- [ ] 参数和结果可折叠
- [ ] 错误结果高亮显示

---

### Task 4: 创建 TaskCardList 组件

**Description**: 管理多个 Task 卡片的列表

**Implementation Details**:
- [ ] 创建 TaskCardList 组件
- [ ] 按执行顺序排列卡片
- [ ] 高亮当前执行的 Task
- [ ] 实现虚拟滚动优化

**Files to modify/create**:
- `packages/web/src/components/TaskCard/TaskCardList.tsx`

**Acceptance Criteria**:
- [ ] 卡片按正确顺序显示
- [ ] 当前执行 Task 突出显示
- [ ] 大量 Task 时性能良好

---

## Technical Specifications

### TaskCard 组件

```tsx
// packages/web/src/components/TaskCard/TaskCard.tsx
import { useState } from 'react';
import { Task } from '../../types/plan';
import { ExecutionEvent } from '../../types/events';
import { AgentActivity } from './AgentActivity';
import { ToolCallLog } from './ToolCallLog';
import { StatusIcon } from '../EventFlow/StatusIcon';
import { ChevronDown, ChevronRight, Clock, CheckCircle2 } from 'lucide-react';
import clsx from 'clsx';

interface TaskCardProps {
  task: Task;
  events: ExecutionEvent[];
  isActive: boolean;
}

export function TaskCard({ task, events, isActive }: TaskCardProps) {
  const [isExpanded, setIsExpanded] = useState(isActive);

  // 过滤属于此 Task 的事件
  const taskEvents = events.filter(
    (e) => 'task_id' in e && e.task_id === task.id
  );

  // 获取 Agent 事件
  const agentEvents = taskEvents.filter((e) =>
    e.type.startsWith('agent_')
  );

  // 获取工具调用事件
  const toolEvents = taskEvents.filter((e) =>
    e.type.startsWith('tool_')
  );

  const getStatusColor = () => {
    switch (task.status) {
      case 'done':
        return 'border-green-300 bg-green-50';
      case 'failed':
        return 'border-red-300 bg-red-50';
      case 'in_progress':
        return 'border-blue-300 bg-blue-50';
      case 'blocked':
        return 'border-orange-300 bg-orange-50';
      default:
        return 'border-gray-200 bg-white';
    }
  };

  return (
    <div
      className={clsx(
        'rounded-lg border-2 transition-all duration-300',
        getStatusColor(),
        isActive && 'ring-2 ring-amber-400 ring-offset-2'
      )}
    >
      {/* Header */}
      <div
        className="flex items-center gap-3 p-4 cursor-pointer"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <StatusIcon
          status={
            task.status === 'done'
              ? 'done'
              : task.status === 'failed'
              ? 'failed'
              : task.status === 'in_progress'
              ? 'in_progress'
              : 'pending'
          }
        />

        <div className="flex-1 min-w-0">
          <div className="font-medium text-gray-800 truncate">
            {task.title}
          </div>
          {task.agent_type && (
            <div className="text-xs text-gray-500 mt-0.5">
              Agent: {task.agent_type}
            </div>
          )}
        </div>

        {/* Progress */}
        {task.status === 'in_progress' && (
          <div className="flex items-center gap-2">
            <div className="w-20 h-1.5 bg-gray-200 rounded-full overflow-hidden">
              <div
                className="h-full bg-blue-500 transition-all duration-300"
                style={{ width: `${task.progress}%` }}
              />
            </div>
            <span className="text-xs text-gray-500">{task.progress}%</span>
          </div>
        )}

        {isExpanded ? (
          <ChevronDown className="w-5 h-5 text-gray-400" />
        ) : (
          <ChevronRight className="w-5 h-5 text-gray-400" />
        )}
      </div>

      {/* Expanded Content */}
      {isExpanded && (
        <div className="border-t border-gray-200 p-4 space-y-4">
          {/* Description */}
          {task.description && (
            <div className="text-sm text-gray-600">
              {task.description}
            </div>
          )}

          {/* Agent Activities */}
          {agentEvents.length > 0 && (
            <div className="space-y-2">
              <div className="text-xs font-medium text-gray-500 uppercase">
                Agent 活动
              </div>
              {agentEvents.map((event, index) => (
                <AgentActivity
                  key={`${event.timestamp}-${index}`}
                  event={event}
                />
              ))}
            </div>
          )}

          {/* Tool Calls */}
          {toolEvents.length > 0 && (
            <div className="space-y-2">
              <div className="text-xs font-medium text-gray-500 uppercase">
                工具调用
              </div>
              {toolEvents.map((event, index) => (
                <ToolCallLog
                  key={`${event.timestamp}-${index}`}
                  event={event}
                />
              ))}
            </div>
          )}

          {/* Error Message */}
          {task.status === 'failed' && task.error_message && (
            <div className="p-3 bg-red-100 rounded-md">
              <div className="text-xs font-medium text-red-800 mb-1">
                错误信息
              </div>
              <div className="text-sm text-red-700">
                {task.error_message}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
```

### AgentActivity 组件

```tsx
// packages/web/src/components/TaskCard/AgentActivity.tsx
import { ExecutionEvent } from '../../types/events';
import { Bot, Loader2, CheckCircle2, XCircle } from 'lucide-react';
import clsx from 'clsx';

interface AgentActivityProps {
  event: ExecutionEvent;
}

export function AgentActivity({ event }: AgentActivityProps) {
  if (event.type === 'agent_start') {
    return (
      <div className="flex items-center gap-2 p-2 bg-blue-50 rounded">
        <Loader2 className="w-4 h-4 text-blue-600 animate-spin" />
        <span className="text-sm text-blue-700">
          {event.agent_type} Agent 启动
        </span>
        {event.agent_instance && (
          <span className="text-xs text-blue-500">
            (实例 #{event.agent_instance})
          </span>
        )}
      </div>
    );
  }

  if (event.type === 'agent_progress') {
    return (
      <div className="flex items-start gap-2 p-2 bg-gray-50 rounded">
        <Bot className="w-4 h-4 text-gray-500 mt-0.5" />
        <div className="flex-1">
          <div className="text-sm text-gray-700">{event.message}</div>
          {event.progress !== undefined && (
            <div className="mt-1 flex items-center gap-2">
              <div className="flex-1 h-1 bg-gray-200 rounded-full overflow-hidden">
                <div
                  className="h-full bg-blue-500"
                  style={{ width: `${event.progress}%` }}
                />
              </div>
              <span className="text-xs text-gray-500">
                {event.progress}%
              </span>
            </div>
          )}
        </div>
      </div>
    );
  }

  if (event.type === 'agent_end') {
    const isSuccess = event.status === 'success';
    return (
      <div
        className={clsx(
          'flex items-center gap-2 p-2 rounded',
          isSuccess ? 'bg-green-50' : 'bg-red-50'
        )}
      >
        {isSuccess ? (
          <CheckCircle2 className="w-4 h-4 text-green-600" />
        ) : (
          <XCircle className="w-4 h-4 text-red-600" />
        )}
        <span
          className={clsx(
            'text-sm',
            isSuccess ? 'text-green-700' : 'text-red-700'
          )}
        >
          {event.summary || (isSuccess ? '执行完成' : '执行失败')}
        </span>
      </div>
    );
  }

  return null;
}
```

### ToolCallLog 组件

```tsx
// packages/web/src/components/TaskCard/ToolCallLog.tsx
import { useState } from 'react';
import { ExecutionEvent } from '../../types/events';
import { Wrench, ChevronDown, ChevronRight, Check, X } from 'lucide-react';
import clsx from 'clsx';

interface ToolCallLogProps {
  event: ExecutionEvent;
}

export function ToolCallLog({ event }: ToolCallLogProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  if (event.type === 'tool_call') {
    return (
      <div className="border border-gray-200 rounded">
        <div
          className="flex items-center gap-2 p-2 cursor-pointer hover:bg-gray-50"
          onClick={() => setIsExpanded(!isExpanded)}
        >
          <Wrench className="w-4 h-4 text-purple-600" />
          <span className="text-sm font-medium text-gray-700">
            {event.tool_name}
          </span>
          <span className="text-xs text-gray-400">调用中...</span>
          {event.tool_input && (
            isExpanded ? (
              <ChevronDown className="w-4 h-4 text-gray-400 ml-auto" />
            ) : (
              <ChevronRight className="w-4 h-4 text-gray-400 ml-auto" />
            )
          )}
        </div>
        {isExpanded && event.tool_input && (
          <div className="border-t border-gray-200 p-2 bg-gray-50">
            <div className="text-xs text-gray-500 mb-1">输入参数:</div>
            <pre className="text-xs text-gray-700 whitespace-pre-wrap overflow-x-auto">
              {JSON.stringify(event.tool_input, null, 2)}
            </pre>
          </div>
        )}
      </div>
    );
  }

  if (event.type === 'tool_result') {
    const isSuccess = event.success;
    return (
      <div
        className={clsx(
          'border rounded',
          isSuccess ? 'border-green-200' : 'border-red-200'
        )}
      >
        <div
          className={clsx(
            'flex items-center gap-2 p-2 cursor-pointer',
            isSuccess ? 'hover:bg-green-50' : 'hover:bg-red-50'
          )}
          onClick={() => setIsExpanded(!isExpanded)}
        >
          {isSuccess ? (
            <Check className="w-4 h-4 text-green-600" />
          ) : (
            <X className="w-4 h-4 text-red-600" />
          )}
          <span className="text-sm font-medium text-gray-700">
            {event.tool_name}
          </span>
          <span
            className={clsx(
              'text-xs',
              isSuccess ? 'text-green-600' : 'text-red-600'
            )}
          >
            {isSuccess ? '成功' : '失败'}
          </span>
          {(event.tool_output || event.error) && (
            isExpanded ? (
              <ChevronDown className="w-4 h-4 text-gray-400 ml-auto" />
            ) : (
              <ChevronRight className="w-4 h-4 text-gray-400 ml-auto" />
            )
          )}
        </div>
        {isExpanded && (
          <div
            className={clsx(
              'border-t p-2',
              isSuccess
                ? 'border-green-200 bg-green-50'
                : 'border-red-200 bg-red-50'
            )}
          >
            {isSuccess && event.tool_output && (
              <>
                <div className="text-xs text-gray-500 mb-1">返回结果:</div>
                <pre className="text-xs text-gray-700 whitespace-pre-wrap overflow-x-auto max-h-40">
                  {JSON.stringify(event.tool_output, null, 2)}
                </pre>
              </>
            )}
            {!isSuccess && event.error && (
              <>
                <div className="text-xs text-red-600 mb-1">错误信息:</div>
                <pre className="text-xs text-red-700 whitespace-pre-wrap">
                  {event.error}
                </pre>
              </>
            )}
          </div>
        )}
      </div>
    );
  }

  return null;
}
```

### TaskCardList 组件

```tsx
// packages/web/src/components/TaskCard/TaskCardList.tsx
import { useMemo } from 'react';
import { Task } from '../../types/plan';
import { ExecutionEvent } from '../../types/events';
import { TaskCard } from './TaskCard';

interface TaskCardListProps {
  tasks: Task[];
  events: ExecutionEvent[];
}

export function TaskCardList({ tasks, events }: TaskCardListProps) {
  // 按状态排序: in_progress > pending > blocked > done/failed/skipped
  const sortedTasks = useMemo(() => {
    const statusOrder: Record<string, number> = {
      in_progress: 0,
      pending: 1,
      blocked: 2,
      retrying: 3,
      done: 4,
      failed: 5,
      skipped: 6,
    };

    return [...tasks].sort(
      (a, b) => (statusOrder[a.status] ?? 99) - (statusOrder[b.status] ?? 99)
    );
  }, [tasks]);

  // 找出当前活跃的 Task
  const activeTasks = useMemo(
    () =>
      new Set(
        tasks
          .filter((t) => t.status === 'in_progress' || t.status === 'retrying')
          .map((t) => t.id)
      ),
    [tasks]
  );

  if (tasks.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-gray-400">
        暂无任务
      </div>
    );
  }

  return (
    <div className="space-y-3 p-4">
      {sortedTasks.map((task) => (
        <TaskCard
          key={task.id}
          task={task}
          events={events}
          isActive={activeTasks.has(task.id)}
        />
      ))}
    </div>
  );
}
```

## Testing Requirements

- [ ] TaskCard 渲染测试
- [ ] AgentActivity 各状态测试
- [ ] ToolCallLog 展开/折叠测试
- [ ] TaskCardList 排序测试
- [ ] 事件过滤正确性测试
- [ ] 性能测试 (大量事件)

## Notes & Warnings

- Task 卡片需要支持实时更新
- 工具调用日志可能很长，需要限制显示
- 多 Agent 并行时需要清晰区分
- 考虑添加搜索/筛选功能
