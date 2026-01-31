# Phase F3: Todo 面板

## Metadata

- **Category**: Frontend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: Medium
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: F2 (SSE 事件消费), B2 (Planner 服务)
  - **Blocks**: F5 (失败处理 UI)

## Goal

实现左侧 Todo 面板，显示 Plan 中的任务列表，随执行进度自动更新状态。

## Detailed Tasks

### Task 1: 创建 Plan 状态管理

**Description**: 管理 Plan 和 Task 的状态

**Implementation Details**:
- [ ] 创建 usePlan hook
- [ ] 实现 Task 状态更新逻辑
- [ ] 根据事件更新 Task 状态

**Files to modify/create**:
- `packages/web/src/hooks/usePlan.ts`
- `packages/web/src/types/plan.ts`

**Acceptance Criteria**:
- [ ] Plan 数据正确存储
- [ ] Task 状态随事件更新
- [ ] 进度计算正确

---

### Task 2: 创建 TodoPanel 组件

**Description**: 实现 Todo 面板容器

**Implementation Details**:
- [ ] 创建 TodoPanel 组件
- [ ] 显示 Plan goal
- [ ] 显示进度统计
- [ ] 响应式折叠

**Files to modify/create**:
- `packages/web/src/components/Todo/TodoPanel.tsx`

**Acceptance Criteria**:
- [ ] 显示 Plan 目标
- [ ] 显示完成进度
- [ ] 移动端可折叠

---

### Task 3: 创建 TodoItem 组件

**Description**: 实现单个任务项

**Implementation Details**:
- [ ] 创建 TodoItem 组件
- [ ] 实现不同状态样式
- [ ] 完成状态显示划线
- [ ] 失败状态显示红色

**Files to modify/create**:
- `packages/web/src/components/Todo/TodoItem.tsx`

**Acceptance Criteria**:
- [ ] 6 种状态正确渲染
- [ ] 完成项有划线效果
- [ ] 失败项显示红色

---

### Task 4: 集成到主布局

**Description**: 将 Todo 面板集成到主页面

**Implementation Details**:
- [ ] 修改 App 布局
- [ ] 实现左右分栏
- [ ] 添加折叠按钮

**Files to modify/create**:
- `packages/web/src/App.tsx`
- `packages/web/src/components/Layout/MainContent.tsx`

**Acceptance Criteria**:
- [ ] 左侧显示 Todo 面板
- [ ] 右侧显示执行流
- [ ] 响应式布局正确

---

## Technical Specifications

### Plan 类型定义

```typescript
// packages/web/src/types/plan.ts

export type TaskStatus =
  | 'pending'
  | 'in_progress'
  | 'done'
  | 'failed'
  | 'blocked'
  | 'skipped'
  | 'retrying';

export interface Task {
  id: string;
  title: string;
  description?: string;
  agent_type?: string;
  status: TaskStatus;
  progress: number;
  depends_on: string[];
  can_parallel: boolean;
  retry_count: number;
  error_message?: string;
}

export interface Plan {
  id: string;
  goal: string;
  tasks: Task[];
  status: 'pending' | 'in_progress' | 'done' | 'failed' | 'aborted';
}
```

### usePlan Hook

```typescript
// packages/web/src/hooks/usePlan.ts
import { useState, useCallback } from 'react';
import { Plan, Task, TaskStatus } from '../types/plan';
import { ExecutionEvent } from '../types/events';

interface UsePlanReturn {
  plan: Plan | null;
  setPlan: (plan: Plan) => void;
  updateTaskStatus: (taskId: string, status: TaskStatus, extra?: Partial<Task>) => void;
  handleEvent: (event: ExecutionEvent) => void;
  progress: { completed: number; total: number };
}

export function usePlan(): UsePlanReturn {
  const [plan, setPlanState] = useState<Plan | null>(null);

  const setPlan = useCallback((newPlan: Plan) => {
    setPlanState(newPlan);
  }, []);

  const updateTaskStatus = useCallback(
    (taskId: string, status: TaskStatus, extra?: Partial<Task>) => {
      setPlanState((prev) => {
        if (!prev) return prev;

        return {
          ...prev,
          tasks: prev.tasks.map((task) =>
            task.id === taskId
              ? { ...task, status, ...extra }
              : task
          ),
        };
      });
    },
    []
  );

  const handleEvent = useCallback(
    (event: ExecutionEvent) => {
      switch (event.type) {
        case 'plan_created':
          // Plan 创建事件包含完整的 plan 数据
          if ('plan' in event) {
            setPlan(event.plan as Plan);
          }
          break;

        case 'task_started':
          updateTaskStatus(event.task_id, 'in_progress');
          break;

        case 'task_progress':
          updateTaskStatus(event.task_id, 'in_progress', {
            progress: event.progress,
          });
          break;

        case 'task_done':
          updateTaskStatus(event.task_id, 'done', {
            progress: 100,
          });
          break;

        case 'task_failed':
          updateTaskStatus(event.task_id, 'failed', {
            error_message: event.error_message,
            retry_count: event.retry_count,
          });
          break;

        case 'task_retrying':
          updateTaskStatus(event.task_id, 'retrying', {
            retry_count: event.attempt,
          });
          break;

        case 'task_skipped':
          updateTaskStatus(event.task_id, 'skipped');
          break;

        case 'task_blocked':
          updateTaskStatus(event.task_id, 'blocked');
          break;
      }
    },
    [setPlan, updateTaskStatus]
  );

  const progress = plan
    ? {
        completed: plan.tasks.filter(
          (t) => t.status === 'done' || t.status === 'skipped'
        ).length,
        total: plan.tasks.length,
      }
    : { completed: 0, total: 0 };

  return {
    plan,
    setPlan,
    updateTaskStatus,
    handleEvent,
    progress,
  };
}
```

### TodoPanel 组件

```tsx
// packages/web/src/components/Todo/TodoPanel.tsx
import { useState } from 'react';
import { Plan } from '../../types/plan';
import { TodoItem } from './TodoItem';
import { ChevronLeft, ChevronRight, ListTodo } from 'lucide-react';
import clsx from 'clsx';

interface TodoPanelProps {
  plan: Plan | null;
  progress: { completed: number; total: number };
  onTaskAction?: (taskId: string, action: 'retry' | 'skip') => void;
}

export function TodoPanel({ plan, progress, onTaskAction }: TodoPanelProps) {
  const [isCollapsed, setIsCollapsed] = useState(false);

  if (!plan) {
    return (
      <div
        className={clsx(
          'border-r border-gray-200 bg-white transition-all duration-300',
          isCollapsed ? 'w-12' : 'w-64'
        )}
      >
        <div className="p-4 text-gray-400 text-sm">
          {isCollapsed ? (
            <ListTodo className="w-5 h-5" />
          ) : (
            '等待生成计划...'
          )}
        </div>
      </div>
    );
  }

  return (
    <div
      className={clsx(
        'border-r border-gray-200 bg-white transition-all duration-300 flex flex-col',
        isCollapsed ? 'w-12' : 'w-64'
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b border-gray-100">
        {!isCollapsed && (
          <div className="flex items-center gap-2">
            <ListTodo className="w-4 h-4 text-amber-600" />
            <span className="font-medium text-sm">Plan</span>
          </div>
        )}
        <button
          onClick={() => setIsCollapsed(!isCollapsed)}
          className="p-1 hover:bg-gray-100 rounded"
        >
          {isCollapsed ? (
            <ChevronRight className="w-4 h-4" />
          ) : (
            <ChevronLeft className="w-4 h-4" />
          )}
        </button>
      </div>

      {!isCollapsed && (
        <>
          {/* Goal */}
          <div className="p-3 border-b border-gray-100">
            <div className="text-xs text-gray-500 mb-1">目标</div>
            <div className="text-sm font-medium text-gray-800 line-clamp-2">
              {plan.goal}
            </div>
          </div>

          {/* Task List */}
          <div className="flex-1 overflow-y-auto p-2 space-y-1">
            {plan.tasks.map((task) => (
              <TodoItem
                key={task.id}
                task={task}
                onAction={onTaskAction}
              />
            ))}
          </div>

          {/* Progress */}
          <div className="p-3 border-t border-gray-100">
            <div className="flex items-center justify-between text-xs text-gray-500">
              <span>进度</span>
              <span>
                {progress.completed}/{progress.total}
              </span>
            </div>
            <div className="mt-1 h-1.5 bg-gray-200 rounded-full overflow-hidden">
              <div
                className="h-full bg-amber-500 transition-all duration-300"
                style={{
                  width: `${
                    progress.total > 0
                      ? (progress.completed / progress.total) * 100
                      : 0
                  }%`,
                }}
              />
            </div>
          </div>
        </>
      )}
    </div>
  );
}
```

### TodoItem 组件

```tsx
// packages/web/src/components/Todo/TodoItem.tsx
import { Task, TaskStatus } from '../../types/plan';
import {
  Circle,
  CheckCircle2,
  XCircle,
  Loader2,
  PauseCircle,
  SkipForward,
  RefreshCw,
} from 'lucide-react';
import clsx from 'clsx';

interface TodoItemProps {
  task: Task;
  onAction?: (taskId: string, action: 'retry' | 'skip') => void;
}

const statusConfig: Record<
  TaskStatus,
  {
    icon: React.ComponentType<{ className?: string }>;
    textClass: string;
    bgClass: string;
  }
> = {
  pending: {
    icon: Circle,
    textClass: 'text-gray-600',
    bgClass: '',
  },
  in_progress: {
    icon: Loader2,
    textClass: 'text-blue-600 font-medium',
    bgClass: 'bg-blue-50',
  },
  done: {
    icon: CheckCircle2,
    textClass: 'text-gray-400 line-through',
    bgClass: '',
  },
  failed: {
    icon: XCircle,
    textClass: 'text-red-600',
    bgClass: 'bg-red-50',
  },
  blocked: {
    icon: PauseCircle,
    textClass: 'text-orange-600',
    bgClass: 'bg-orange-50',
  },
  skipped: {
    icon: SkipForward,
    textClass: 'text-gray-400 line-through',
    bgClass: '',
  },
  retrying: {
    icon: RefreshCw,
    textClass: 'text-yellow-600',
    bgClass: 'bg-yellow-50',
  },
};

export function TodoItem({ task, onAction }: TodoItemProps) {
  const config = statusConfig[task.status];
  const Icon = config.icon;
  const isAnimated = task.status === 'in_progress' || task.status === 'retrying';

  return (
    <div
      className={clsx(
        'flex items-start gap-2 p-2 rounded-md transition-colors',
        config.bgClass
      )}
    >
      <Icon
        className={clsx(
          'w-4 h-4 mt-0.5 flex-shrink-0',
          config.textClass,
          isAnimated && 'animate-spin'
        )}
      />
      <div className="flex-1 min-w-0">
        <div className={clsx('text-sm truncate', config.textClass)}>
          {task.title}
        </div>

        {/* 进度条 (仅进行中显示) */}
        {task.status === 'in_progress' && task.progress > 0 && (
          <div className="mt-1 h-1 bg-blue-200 rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-500 transition-all duration-300"
              style={{ width: `${task.progress}%` }}
            />
          </div>
        )}

        {/* 错误信息 (仅失败显示) */}
        {task.status === 'failed' && task.error_message && (
          <div className="mt-1 text-xs text-red-500 truncate">
            {task.error_message}
          </div>
        )}

        {/* 重试次数 */}
        {task.status === 'retrying' && (
          <div className="mt-1 text-xs text-yellow-600">
            重试中 ({task.retry_count}/3)
          </div>
        )}

        {/* 操作按钮 (仅失败显示) */}
        {task.status === 'failed' && onAction && (
          <div className="mt-2 flex gap-2">
            <button
              onClick={() => onAction(task.id, 'retry')}
              className="text-xs px-2 py-1 bg-blue-100 text-blue-600 rounded hover:bg-blue-200"
            >
              重试
            </button>
            <button
              onClick={() => onAction(task.id, 'skip')}
              className="text-xs px-2 py-1 bg-gray-100 text-gray-600 rounded hover:bg-gray-200"
            >
              跳过
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
```

### 更新主布局

```tsx
// packages/web/src/App.tsx (更新)
import { useState } from 'react';
import { Header } from './components/Layout/Header';
import { InputArea } from './components/Layout/InputArea';
import { TodoPanel } from './components/Todo/TodoPanel';
import { EventList } from './components/EventFlow/EventList';
import { useSSE } from './hooks/useSSE';
import { usePlan } from './hooks/usePlan';
import { API_ENDPOINTS } from './api/config';

function App() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const { plan, handleEvent, progress } = usePlan();

  const { events, connect } = useSSE({
    url: sessionId ? `${API_ENDPOINTS.chatStream}?session_id=${sessionId}` : '',
    onEvent: handleEvent,
    onDone: () => setIsLoading(false),
  });

  const handleSend = async (message: string) => {
    setIsLoading(true);
    // TODO: 创建会话并开始执行
    // 1. POST /api/plan 创建计划
    // 2. 获取 session_id
    // 3. 连接 SSE
  };

  const handleTaskAction = async (taskId: string, action: 'retry' | 'skip') => {
    // TODO: 调用任务控制 API
  };

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      <Header />
      <div className="flex flex-1 overflow-hidden">
        <TodoPanel
          plan={plan}
          progress={progress}
          onTaskAction={handleTaskAction}
        />
        <main className="flex-1 flex flex-col overflow-hidden">
          <EventList events={events} />
        </main>
      </div>
      <InputArea onSend={handleSend} isLoading={isLoading} />
    </div>
  );
}

export default App;
```

## Testing Requirements

- [ ] usePlan hook 状态更新测试
- [ ] TodoPanel 渲染测试
- [ ] TodoItem 各状态渲染测试
- [ ] 进度计算测试
- [ ] 响应式折叠测试
- [ ] 任务操作按钮测试

## Notes & Warnings

- Todo 面板在移动端默认折叠
- 任务列表可能很长，需要滚动
- 状态更新需要平滑过渡动画
- 考虑添加任务搜索/筛选功能
