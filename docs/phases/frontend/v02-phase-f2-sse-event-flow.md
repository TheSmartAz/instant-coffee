# Phase F2: SSE 事件消费 + 执行流列表

## Metadata

- **Category**: Frontend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: Medium
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: F1 (Web 前端骨架), B1 (事件协议)
  - **Blocks**: F3 (Todo 面板), F4 (Task 卡片视图)

## Goal

实现 SSE 事件消费和执行流列表 UI，让用户实时看到 AI 执行过程。

## Detailed Tasks

### Task 1: 创建 SSE Hook

**Description**: 封装 SSE 连接和事件处理逻辑

**Implementation Details**:
- [ ] 创建 useSSE hook
- [ ] 实现自动重连机制
- [ ] 处理连接状态
- [ ] 解析 SSE 事件数据

**Files to modify/create**:
- `packages/web/src/hooks/useSSE.ts`

**Acceptance Criteria**:
- [ ] 可以建立 SSE 连接
- [ ] 正确解析事件数据
- [ ] 断开后自动重连
- [ ] 提供连接状态

---

### Task 2: 定义事件类型

**Description**: 创建 TypeScript 类型定义

**Implementation Details**:
- [ ] 定义所有事件类型接口
- [ ] 创建事件类型守卫函数
- [ ] 导出类型供组件使用

**Files to modify/create**:
- `packages/web/src/types/events.ts`

**Acceptance Criteria**:
- [ ] 所有事件类型有完整定义
- [ ] 类型检查通过
- [ ] 类型守卫函数正确工作

---

### Task 3: 创建执行流列表组件

**Description**: 实现事件列表 UI

**Implementation Details**:
- [ ] 创建 EventList 组件
- [ ] 创建 EventItem 组件
- [ ] 实现自动滚动到底部
- [ ] 用户滚动时暂停自动滚动

**Files to modify/create**:
- `packages/web/src/components/EventFlow/EventList.tsx`
- `packages/web/src/components/EventFlow/EventItem.tsx`

**Acceptance Criteria**:
- [ ] 事件逐条显示
- [ ] 新事件自动滚动到底部
- [ ] 用户滚动时不强制滚动

---

### Task 4: 实现状态渲染

**Description**: 根据事件状态渲染不同样式

**Implementation Details**:
- [ ] 创建状态图标组件
- [ ] 实现不同状态的颜色
- [ ] 添加进行中动画

**Files to modify/create**:
- `packages/web/src/components/EventFlow/StatusIcon.tsx`
- `packages/web/src/components/EventFlow/ProgressBar.tsx`

**Acceptance Criteria**:
- [ ] pending/in_progress/done/failed 状态正确显示
- [ ] 进行中有动画效果
- [ ] 颜色符合设计规范

---

### Task 5: 实现事件折叠

**Description**: 完成的事件可以折叠

**Implementation Details**:
- [ ] 添加折叠/展开状态
- [ ] 实现折叠动画
- [ ] 显示折叠摘要

**Files to modify/create**:
- `packages/web/src/components/EventFlow/CollapsibleEvent.tsx`

**Acceptance Criteria**:
- [ ] 完成的事件自动折叠
- [ ] 点击可以展开详情
- [ ] 折叠有平滑动画

---

## Technical Specifications

### 事件类型定义

```typescript
// packages/web/src/types/events.ts

export type EventType =
  | 'agent_start'
  | 'agent_progress'
  | 'agent_end'
  | 'tool_call'
  | 'tool_result'
  | 'plan_created'
  | 'plan_updated'
  | 'task_started'
  | 'task_progress'
  | 'task_done'
  | 'task_failed'
  | 'task_retrying'
  | 'task_skipped'
  | 'task_blocked'
  | 'error'
  | 'done';

export interface BaseEvent {
  type: EventType;
  timestamp: string;
}

export interface AgentStartEvent extends BaseEvent {
  type: 'agent_start';
  task_id?: string;
  agent_id: string;
  agent_type: string;
  agent_instance?: number;
}

export interface AgentProgressEvent extends BaseEvent {
  type: 'agent_progress';
  task_id?: string;
  agent_id: string;
  message: string;
  progress?: number;
}

export interface AgentEndEvent extends BaseEvent {
  type: 'agent_end';
  task_id?: string;
  agent_id: string;
  status: 'success' | 'failed';
  summary?: string;
}

export interface ToolCallEvent extends BaseEvent {
  type: 'tool_call';
  task_id?: string;
  agent_id: string;
  tool_name: string;
  tool_input?: Record<string, unknown>;
}

export interface ToolResultEvent extends BaseEvent {
  type: 'tool_result';
  task_id?: string;
  agent_id: string;
  tool_name: string;
  success: boolean;
  tool_output?: Record<string, unknown>;
  error?: string;
}

export interface TaskStartedEvent extends BaseEvent {
  type: 'task_started';
  task_id: string;
  task_title: string;
}

export interface TaskProgressEvent extends BaseEvent {
  type: 'task_progress';
  task_id: string;
  progress: number;
  message?: string;
}

export interface TaskDoneEvent extends BaseEvent {
  type: 'task_done';
  task_id: string;
  result?: {
    output_file?: string;
    preview_url?: string;
    summary?: string;
  };
}

export interface TaskFailedEvent extends BaseEvent {
  type: 'task_failed';
  task_id: string;
  error_type: 'temporary' | 'logic' | 'dependency';
  error_message: string;
  retry_count: number;
  max_retries: number;
  available_actions: string[];
  blocked_tasks: string[];
}

export interface ErrorEvent extends BaseEvent {
  type: 'error';
  message: string;
  details?: string;
}

export interface DoneEvent extends BaseEvent {
  type: 'done';
  summary?: string;
}

export type ExecutionEvent =
  | AgentStartEvent
  | AgentProgressEvent
  | AgentEndEvent
  | ToolCallEvent
  | ToolResultEvent
  | TaskStartedEvent
  | TaskProgressEvent
  | TaskDoneEvent
  | TaskFailedEvent
  | ErrorEvent
  | DoneEvent;

// 类型守卫
export function isAgentEvent(event: ExecutionEvent): event is AgentStartEvent | AgentProgressEvent | AgentEndEvent {
  return event.type.startsWith('agent_');
}

export function isTaskEvent(event: ExecutionEvent): event is TaskStartedEvent | TaskProgressEvent | TaskDoneEvent | TaskFailedEvent {
  return event.type.startsWith('task_');
}

export function isToolEvent(event: ExecutionEvent): event is ToolCallEvent | ToolResultEvent {
  return event.type.startsWith('tool_');
}
```

### useSSE Hook

```typescript
// packages/web/src/hooks/useSSE.ts
import { useState, useEffect, useCallback, useRef } from 'react';
import { ExecutionEvent } from '../types/events';

interface UseSSEOptions {
  url: string;
  onEvent?: (event: ExecutionEvent) => void;
  onError?: (error: Error) => void;
  onDone?: () => void;
  autoReconnect?: boolean;
  reconnectDelay?: number;
}

interface UseSSEReturn {
  events: ExecutionEvent[];
  isConnected: boolean;
  isLoading: boolean;
  error: Error | null;
  connect: () => void;
  disconnect: () => void;
}

export function useSSE({
  url,
  onEvent,
  onError,
  onDone,
  autoReconnect = true,
  reconnectDelay = 3000,
}: UseSSEOptions): UseSSEReturn {
  const [events, setEvents] = useState<ExecutionEvent[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);

  const connect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    setIsLoading(true);
    setError(null);

    const eventSource = new EventSource(url);
    eventSourceRef.current = eventSource;

    eventSource.onopen = () => {
      setIsConnected(true);
      setIsLoading(false);
    };

    eventSource.onmessage = (e) => {
      if (e.data === '[DONE]') {
        setIsConnected(false);
        eventSource.close();
        onDone?.();
        return;
      }

      try {
        const event = JSON.parse(e.data) as ExecutionEvent;
        setEvents((prev) => [...prev, event]);
        onEvent?.(event);
      } catch (err) {
        console.error('Failed to parse event:', err);
      }
    };

    eventSource.onerror = (e) => {
      setIsConnected(false);
      setIsLoading(false);
      const err = new Error('SSE connection error');
      setError(err);
      onError?.(err);

      eventSource.close();

      if (autoReconnect) {
        reconnectTimeoutRef.current = window.setTimeout(() => {
          connect();
        }, reconnectDelay);
      }
    };
  }, [url, onEvent, onError, onDone, autoReconnect, reconnectDelay]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setIsConnected(false);
  }, []);

  useEffect(() => {
    return () => {
      disconnect();
    };
  }, [disconnect]);

  return {
    events,
    isConnected,
    isLoading,
    error,
    connect,
    disconnect,
  };
}
```

### EventList 组件

```tsx
// packages/web/src/components/EventFlow/EventList.tsx
import { useRef, useEffect, useState } from 'react';
import { ExecutionEvent } from '../../types/events';
import { EventItem } from './EventItem';

interface EventListProps {
  events: ExecutionEvent[];
}

export function EventList({ events }: EventListProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);

  // 自动滚动到底部
  useEffect(() => {
    if (autoScroll && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [events, autoScroll]);

  // 检测用户滚动
  const handleScroll = () => {
    if (!containerRef.current) return;

    const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 50;
    setAutoScroll(isAtBottom);
  };

  if (events.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-gray-400">
        等待执行...
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      onScroll={handleScroll}
      className="flex-1 overflow-y-auto p-4 space-y-2"
    >
      {events.map((event, index) => (
        <EventItem key={`${event.timestamp}-${index}`} event={event} />
      ))}
    </div>
  );
}
```

### EventItem 组件

```tsx
// packages/web/src/components/EventFlow/EventItem.tsx
import { useState } from 'react';
import { ExecutionEvent, isAgentEvent, isToolEvent } from '../../types/events';
import { StatusIcon } from './StatusIcon';
import { ChevronDown, ChevronRight } from 'lucide-react';
import clsx from 'clsx';

interface EventItemProps {
  event: ExecutionEvent;
}

export function EventItem({ event }: EventItemProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const getEventTitle = (): string => {
    switch (event.type) {
      case 'agent_start':
        return `${event.agent_type} Agent 启动`;
      case 'agent_progress':
        return event.message;
      case 'agent_end':
        return `${event.agent_id} ${event.status === 'success' ? '完成' : '失败'}`;
      case 'tool_call':
        return `调用工具: ${event.tool_name}`;
      case 'tool_result':
        return `工具返回: ${event.tool_name}`;
      case 'task_started':
        return `开始: ${event.task_title}`;
      case 'task_progress':
        return event.message || `进度: ${event.progress}%`;
      case 'task_done':
        return `完成: ${event.result?.summary || '任务完成'}`;
      case 'task_failed':
        return `失败: ${event.error_message}`;
      case 'error':
        return event.message;
      case 'done':
        return event.summary || '执行完成';
      default:
        return event.type;
    }
  };

  const getStatus = (): 'pending' | 'in_progress' | 'done' | 'failed' => {
    switch (event.type) {
      case 'agent_start':
      case 'task_started':
        return 'in_progress';
      case 'agent_end':
        return event.status === 'success' ? 'done' : 'failed';
      case 'task_done':
      case 'done':
        return 'done';
      case 'task_failed':
      case 'error':
        return 'failed';
      default:
        return 'in_progress';
    }
  };

  const hasDetails = isAgentEvent(event) || isToolEvent(event);
  const status = getStatus();

  return (
    <div
      className={clsx(
        'rounded-lg border p-3 transition-all',
        status === 'done' && 'bg-green-50 border-green-200',
        status === 'failed' && 'bg-red-50 border-red-200',
        status === 'in_progress' && 'bg-blue-50 border-blue-200',
        status === 'pending' && 'bg-gray-50 border-gray-200'
      )}
    >
      <div
        className="flex items-center gap-2 cursor-pointer"
        onClick={() => hasDetails && setIsExpanded(!isExpanded)}
      >
        <StatusIcon status={status} />
        <span className="flex-1 text-sm">{getEventTitle()}</span>
        <span className="text-xs text-gray-400">
          {new Date(event.timestamp).toLocaleTimeString()}
        </span>
        {hasDetails && (
          isExpanded ? (
            <ChevronDown className="w-4 h-4 text-gray-400" />
          ) : (
            <ChevronRight className="w-4 h-4 text-gray-400" />
          )
        )}
      </div>

      {isExpanded && hasDetails && (
        <div className="mt-2 pl-6 text-xs text-gray-600">
          <pre className="whitespace-pre-wrap">
            {JSON.stringify(event, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
```

### StatusIcon 组件

```tsx
// packages/web/src/components/EventFlow/StatusIcon.tsx
import { Check, X, Loader2, Circle } from 'lucide-react';
import clsx from 'clsx';

interface StatusIconProps {
  status: 'pending' | 'in_progress' | 'done' | 'failed';
}

export function StatusIcon({ status }: StatusIconProps) {
  const iconClass = 'w-4 h-4';

  switch (status) {
    case 'done':
      return <Check className={clsx(iconClass, 'text-green-600')} />;
    case 'failed':
      return <X className={clsx(iconClass, 'text-red-600')} />;
    case 'in_progress':
      return <Loader2 className={clsx(iconClass, 'text-blue-600 animate-spin')} />;
    case 'pending':
    default:
      return <Circle className={clsx(iconClass, 'text-gray-400')} />;
  }
}
```

## Testing Requirements

- [ ] useSSE hook 连接测试
- [ ] useSSE hook 重连测试
- [ ] EventList 渲染测试
- [ ] EventItem 状态渲染测试
- [ ] 自动滚动行为测试
- [ ] 事件折叠交互测试

## Notes & Warnings

- SSE 连接需要处理跨域问题
- 事件量大时考虑虚拟滚动优化
- 断开重连时需要考虑事件去重
- 移动端需要测试滚动性能
