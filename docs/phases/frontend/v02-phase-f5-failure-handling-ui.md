# Phase F5: 失败处理 UI

## Metadata

- **Category**: Frontend
- **Priority**: P1 (Important)
- **Estimated Complexity**: Medium
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: F3 (Todo 面板), B4 (任务控制 API)
  - **Blocks**: None

## Goal

实现任务失败时的用户交互界面，支持重试、跳过、修改需求后重试、终止执行等操作。

## Detailed Tasks

### Task 1: 创建 FailureDialog 组件

**Description**: 实现失败提示对话框

**Implementation Details**:
- [ ] 创建 FailureDialog 组件
- [ ] 显示错误信息和类型
- [ ] 显示受影响的下游任务
- [ ] 提供操作按钮

**Files to modify/create**:
- `packages/web/src/components/Failure/FailureDialog.tsx`

**Acceptance Criteria**:
- [ ] 清晰显示错误信息
- [ ] 显示被阻塞的任务列表
- [ ] 操作按钮可点击

---

### Task 2: 创建 RetryOptions 组件

**Description**: 实现重试选项界面

**Implementation Details**:
- [ ] 创建 RetryOptions 组件
- [ ] 显示重试次数和历史
- [ ] 支持直接重试
- [ ] 支持修改需求后重试

**Files to modify/create**:
- `packages/web/src/components/Failure/RetryOptions.tsx`

**Acceptance Criteria**:
- [ ] 显示已重试次数
- [ ] 可以直接重试
- [ ] 可以编辑需求后重试

---

### Task 3: 创建 ModifyTaskForm 组件

**Description**: 实现修改任务需求的表单

**Implementation Details**:
- [ ] 创建 ModifyTaskForm 组件
- [ ] 显示原始需求
- [ ] 提供编辑区域
- [ ] 支持提交修改

**Files to modify/create**:
- `packages/web/src/components/Failure/ModifyTaskForm.tsx`

**Acceptance Criteria**:
- [ ] 显示原始任务描述
- [ ] 可以编辑描述
- [ ] 提交后触发重试

---

### Task 4: 创建 AbortConfirmation 组件

**Description**: 实现终止执行确认对话框

**Implementation Details**:
- [ ] 创建 AbortConfirmation 组件
- [ ] 显示已完成和待执行任务
- [ ] 确认终止操作
- [ ] 显示终止后的状态

**Files to modify/create**:
- `packages/web/src/components/Failure/AbortConfirmation.tsx`

**Acceptance Criteria**:
- [ ] 显示执行状态摘要
- [ ] 需要二次确认
- [ ] 终止后显示结果

---

### Task 5: 集成失败处理 API

**Description**: 连接后端任务控制 API

**Implementation Details**:
- [ ] 创建 useTaskControl hook
- [ ] 实现 retry API 调用
- [ ] 实现 skip API 调用
- [ ] 实现 abort API 调用
- [ ] 实现 modify API 调用

**Files to modify/create**:
- `packages/web/src/hooks/useTaskControl.ts`
- `packages/web/src/api/taskControl.ts`

**Acceptance Criteria**:
- [ ] API 调用正确
- [ ] 错误处理完善
- [ ] 状态更新及时

---

## Technical Specifications

### FailureDialog 组件

```tsx
// packages/web/src/components/Failure/FailureDialog.tsx
import { useState } from 'react';
import { Task } from '../../types/plan';
import { RetryOptions } from './RetryOptions';
import { ModifyTaskForm } from './ModifyTaskForm';
import { AbortConfirmation } from './AbortConfirmation';
import { AlertTriangle, X } from 'lucide-react';

interface FailureDialogProps {
  task: Task;
  blockedTasks: Task[];
  onRetry: () => Promise<void>;
  onSkip: () => Promise<void>;
  onModify: (newDescription: string) => Promise<void>;
  onAbort: () => Promise<void>;
  onClose: () => void;
}

type DialogView = 'main' | 'modify' | 'abort';

export function FailureDialog({
  task,
  blockedTasks,
  onRetry,
  onSkip,
  onModify,
  onAbort,
  onClose,
}: FailureDialogProps) {
  const [view, setView] = useState<DialogView>('main');
  const [isLoading, setIsLoading] = useState(false);

  const handleAction = async (action: () => Promise<void>) => {
    setIsLoading(true);
    try {
      await action();
      onClose();
    } catch (error) {
      console.error('Action failed:', error);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-200">
          <div className="flex items-center gap-2 text-red-600">
            <AlertTriangle className="w-5 h-5" />
            <span className="font-medium">任务执行失败</span>
          </div>
          <button
            onClick={onClose}
            className="p-1 hover:bg-gray-100 rounded"
          >
            <X className="w-5 h-5 text-gray-400" />
          </button>
        </div>

        {/* Content */}
        <div className="p-4">
          {view === 'main' && (
            <>
              {/* Task Info */}
              <div className="mb-4">
                <div className="text-sm font-medium text-gray-800">
                  {task.title}
                </div>
                <div className="mt-2 p-3 bg-red-50 rounded-md">
                  <div className="text-xs text-red-600 mb-1">错误信息</div>
                  <div className="text-sm text-red-700">
                    {task.error_message || '未知错误'}
                  </div>
                </div>
              </div>

              {/* Blocked Tasks */}
              {blockedTasks.length > 0 && (
                <div className="mb-4">
                  <div className="text-xs text-gray-500 mb-2">
                    以下任务被阻塞 ({blockedTasks.length})
                  </div>
                  <div className="space-y-1">
                    {blockedTasks.slice(0, 3).map((t) => (
                      <div
                        key={t.id}
                        className="text-sm text-orange-600 bg-orange-50 px-2 py-1 rounded"
                      >
                        {t.title}
                      </div>
                    ))}
                    {blockedTasks.length > 3 && (
                      <div className="text-xs text-gray-400">
                        还有 {blockedTasks.length - 3} 个任务...
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Retry Info */}
              <RetryOptions
                retryCount={task.retry_count}
                maxRetries={3}
              />

              {/* Actions */}
              <div className="mt-4 space-y-2">
                <button
                  onClick={() => handleAction(onRetry)}
                  disabled={isLoading}
                  className="w-full py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-blue-400"
                >
                  重试
                </button>
                <button
                  onClick={() => setView('modify')}
                  disabled={isLoading}
                  className="w-full py-2 bg-amber-600 text-white rounded-md hover:bg-amber-700 disabled:bg-amber-400"
                >
                  修改需求后重试
                </button>
                <div className="flex gap-2">
                  <button
                    onClick={() => handleAction(onSkip)}
                    disabled={isLoading}
                    className="flex-1 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300 disabled:bg-gray-100"
                  >
                    跳过此任务
                  </button>
                  <button
                    onClick={() => setView('abort')}
                    disabled={isLoading}
                    className="flex-1 py-2 bg-red-100 text-red-600 rounded-md hover:bg-red-200 disabled:bg-red-50"
                  >
                    终止执行
                  </button>
                </div>
              </div>
            </>
          )}

          {view === 'modify' && (
            <ModifyTaskForm
              task={task}
              onSubmit={(desc) => handleAction(() => onModify(desc))}
              onCancel={() => setView('main')}
              isLoading={isLoading}
            />
          )}

          {view === 'abort' && (
            <AbortConfirmation
              onConfirm={() => handleAction(onAbort)}
              onCancel={() => setView('main')}
              isLoading={isLoading}
            />
          )}
        </div>
      </div>
    </div>
  );
}
```

### RetryOptions 组件

```tsx
// packages/web/src/components/Failure/RetryOptions.tsx
import { RefreshCw } from 'lucide-react';

interface RetryOptionsProps {
  retryCount: number;
  maxRetries: number;
}

export function RetryOptions({ retryCount, maxRetries }: RetryOptionsProps) {
  return (
    <div className="flex items-center gap-2 p-2 bg-gray-50 rounded-md">
      <RefreshCw className="w-4 h-4 text-gray-500" />
      <span className="text-sm text-gray-600">
        已自动重试 {retryCount}/{maxRetries} 次
      </span>
    </div>
  );
}
```

### ModifyTaskForm 组件

```tsx
// packages/web/src/components/Failure/ModifyTaskForm.tsx
import { useState } from 'react';
import { Task } from '../../types/plan';
import { ArrowLeft, Send } from 'lucide-react';

interface ModifyTaskFormProps {
  task: Task;
  onSubmit: (description: string) => void;
  onCancel: () => void;
  isLoading: boolean;
}

export function ModifyTaskForm({
  task,
  onSubmit,
  onCancel,
  isLoading,
}: ModifyTaskFormProps) {
  const [description, setDescription] = useState(task.description || '');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (description.trim()) {
      onSubmit(description.trim());
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <div className="mb-4">
        <button
          type="button"
          onClick={onCancel}
          className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
        >
          <ArrowLeft className="w-4 h-4" />
          返回
        </button>
      </div>

      <div className="mb-4">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          修改任务描述
        </label>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={4}
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-amber-500"
          placeholder="输入新的任务描述..."
        />
      </div>

      <div className="text-xs text-gray-500 mb-4">
        提示: 尝试更清晰地描述需求，或简化任务范围
      </div>

      <button
        type="submit"
        disabled={isLoading || !description.trim()}
        className="w-full flex items-center justify-center gap-2 py-2 bg-amber-600 text-white rounded-md hover:bg-amber-700 disabled:bg-amber-400"
      >
        <Send className="w-4 h-4" />
        提交并重试
      </button>
    </form>
  );
}
```

### AbortConfirmation 组件

```tsx
// packages/web/src/components/Failure/AbortConfirmation.tsx
import { AlertTriangle, ArrowLeft } from 'lucide-react';

interface AbortConfirmationProps {
  onConfirm: () => void;
  onCancel: () => void;
  isLoading: boolean;
}

export function AbortConfirmation({
  onConfirm,
  onCancel,
  isLoading,
}: AbortConfirmationProps) {
  return (
    <div>
      <div className="mb-4">
        <button
          type="button"
          onClick={onCancel}
          className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
        >
          <ArrowLeft className="w-4 h-4" />
          返回
        </button>
      </div>

      <div className="text-center py-4">
        <AlertTriangle className="w-12 h-12 text-red-500 mx-auto mb-4" />
        <div className="text-lg font-medium text-gray-800 mb-2">
          确定要终止执行吗？
        </div>
        <div className="text-sm text-gray-500 mb-4">
          已完成的任务结果将被保留，未完成的任务将被取消。
        </div>
      </div>

      <div className="flex gap-2">
        <button
          onClick={onCancel}
          disabled={isLoading}
          className="flex-1 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300"
        >
          取消
        </button>
        <button
          onClick={onConfirm}
          disabled={isLoading}
          className="flex-1 py-2 bg-red-600 text-white rounded-md hover:bg-red-700"
        >
          确认终止
        </button>
      </div>
    </div>
  );
}
```

### useTaskControl Hook

```typescript
// packages/web/src/hooks/useTaskControl.ts
import { useState, useCallback } from 'react';
import { API_ENDPOINTS } from '../api/config';

interface UseTaskControlReturn {
  isLoading: boolean;
  error: Error | null;
  retryTask: (taskId: string) => Promise<void>;
  skipTask: (taskId: string) => Promise<string[]>;
  modifyTask: (taskId: string, description: string) => Promise<void>;
  abortSession: (sessionId: string) => Promise<{
    completedTasks: string[];
    abortedTasks: string[];
  }>;
}

export function useTaskControl(): UseTaskControlReturn {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const retryTask = useCallback(async (taskId: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await fetch(API_ENDPOINTS.taskRetry(taskId), {
        method: 'POST',
      });
      if (!response.ok) {
        throw new Error('Failed to retry task');
      }
    } catch (err) {
      setError(err as Error);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const skipTask = useCallback(async (taskId: string): Promise<string[]> => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await fetch(API_ENDPOINTS.taskSkip(taskId), {
        method: 'POST',
      });
      if (!response.ok) {
        throw new Error('Failed to skip task');
      }
      const data = await response.json();
      return data.unblocked_tasks;
    } catch (err) {
      setError(err as Error);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const modifyTask = useCallback(
    async (taskId: string, description: string) => {
      setIsLoading(true);
      setError(null);
      try {
        const response = await fetch(
          `${API_ENDPOINTS.taskRetry(taskId).replace('/retry', '/modify')}`,
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({ description }),
          }
        );
        if (!response.ok) {
          throw new Error('Failed to modify task');
        }
      } catch (err) {
        setError(err as Error);
        throw err;
      } finally {
        setIsLoading(false);
      }
    },
    []
  );

  const abortSession = useCallback(
    async (
      sessionId: string
    ): Promise<{ completedTasks: string[]; abortedTasks: string[] }> => {
      setIsLoading(true);
      setError(null);
      try {
        const response = await fetch(API_ENDPOINTS.sessionAbort(sessionId), {
          method: 'POST',
        });
        if (!response.ok) {
          throw new Error('Failed to abort session');
        }
        const data = await response.json();
        return {
          completedTasks: data.completed_tasks,
          abortedTasks: data.aborted_tasks,
        };
      } catch (err) {
        setError(err as Error);
        throw err;
      } finally {
        setIsLoading(false);
      }
    },
    []
  );

  return {
    isLoading,
    error,
    retryTask,
    skipTask,
    modifyTask,
    abortSession,
  };
}
```

### API 配置更新

```typescript
// packages/web/src/api/config.ts (更新)
export const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const API_ENDPOINTS = {
  chat: `${API_BASE_URL}/api/chat`,
  chatStream: `${API_BASE_URL}/api/chat/stream`,
  plan: `${API_BASE_URL}/api/plan`,
  taskRetry: (id: string) => `${API_BASE_URL}/api/task/${id}/retry`,
  taskSkip: (id: string) => `${API_BASE_URL}/api/task/${id}/skip`,
  taskModify: (id: string) => `${API_BASE_URL}/api/task/${id}/modify`,
  taskStatus: (id: string) => `${API_BASE_URL}/api/task/${id}/status`,
  planStatus: (id: string) => `${API_BASE_URL}/api/plan/${id}/status`,
  sessionAbort: (id: string) => `${API_BASE_URL}/api/session/${id}/abort`,
};
```

## Testing Requirements

- [ ] FailureDialog 渲染测试
- [ ] RetryOptions 显示测试
- [ ] ModifyTaskForm 表单验证测试
- [ ] AbortConfirmation 交互测试
- [ ] useTaskControl API 调用测试
- [ ] 错误处理测试
- [ ] 加载状态测试

## Notes & Warnings

- 失败对话框需要阻止背景交互
- 修改需求时保留原始描述作为参考
- 终止操作需要二次确认
- API 调用需要处理网络错误
- 考虑添加操作历史记录
