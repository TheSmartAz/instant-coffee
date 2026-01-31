# Phase B1: 事件协议扩展

## Metadata

- **Category**: Backend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: Medium
- **Parallel Development**: ✅ Can develop in parallel
- **Dependencies**:
  - **Blocked by**: None
  - **Blocks**: F2 (SSE 事件消费), B2 (Planner 服务)

## Goal

扩展后端事件协议，支持细粒度的执行流事件，为前端实时可视化提供数据基础。

## Detailed Tasks

### Task 1: 定义事件类型枚举

**Description**: 创建所有事件类型的枚举定义

**Implementation Details**:
- [ ] 创建 EventType 枚举类
- [ ] 定义阶段 1 事件类型 (agent_start, agent_progress, agent_end, tool_call, tool_result, error, done)
- [ ] 定义阶段 2 事件类型 (plan_created, plan_updated, task_started, task_progress, task_done, task_failed, task_retrying, task_skipped, task_blocked)

**Files to modify/create**:
- `packages/backend/app/events/__init__.py`
- `packages/backend/app/events/types.py`

**Acceptance Criteria**:
- [ ] 所有事件类型有明确定义
- [ ] 类型可以被序列化为字符串

---

### Task 2: 创建事件数据模型

**Description**: 为每种事件类型创建 Pydantic 模型

**Implementation Details**:
- [ ] 创建 BaseEvent 基类
- [ ] 创建 AgentStartEvent, AgentProgressEvent, AgentEndEvent
- [ ] 创建 ToolCallEvent, ToolResultEvent
- [ ] 创建 PlanCreatedEvent, PlanUpdatedEvent
- [ ] 创建 TaskStartedEvent, TaskProgressEvent, TaskDoneEvent, TaskFailedEvent, TaskRetryingEvent

**Files to modify/create**:
- `packages/backend/app/events/models.py`

**Acceptance Criteria**:
- [ ] 所有事件模型可以正确序列化为 JSON
- [ ] 事件模型包含 timestamp 字段
- [ ] 类型检查通过

---

### Task 3: 创建事件发射器

**Description**: 创建统一的事件发射接口

**Implementation Details**:
- [ ] 创建 EventEmitter 类
- [ ] 实现 emit() 方法
- [ ] 支持事件序列化为 SSE 格式
- [ ] 添加事件日志记录

**Files to modify/create**:
- `packages/backend/app/events/emitter.py`

**Acceptance Criteria**:
- [ ] 可以发射任意类型的事件
- [ ] 事件自动添加 timestamp
- [ ] 支持 SSE 格式输出

---

### Task 4: 集成到 Orchestrator

**Description**: 在 Orchestrator 中集成事件发射

**Implementation Details**:
- [ ] 修改 AgentOrchestrator 使用 EventEmitter
- [ ] 在 Agent 执行各阶段发射对应事件
- [ ] 在 Tool 调用时发射事件
- [ ] 确保 stream() 方法返回新的事件格式

**Files to modify/create**:
- `packages/backend/app/agents/orchestrator.py`
- `packages/backend/app/agents/base.py`

**Acceptance Criteria**:
- [ ] Orchestrator 在执行过程中发射细粒度事件
- [ ] 现有 CLI 功能不受影响
- [ ] SSE 流返回新格式事件

---

## Technical Specifications

### 事件类型定义

```python
# packages/backend/app/events/types.py
from enum import Enum

class EventType(str, Enum):
    # 阶段 1: Agent 和 Tool 事件
    AGENT_START = "agent_start"
    AGENT_PROGRESS = "agent_progress"
    AGENT_END = "agent_end"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    ERROR = "error"
    DONE = "done"

    # 阶段 2: Plan 和 Task 事件
    PLAN_CREATED = "plan_created"
    PLAN_UPDATED = "plan_updated"
    TASK_STARTED = "task_started"
    TASK_PROGRESS = "task_progress"
    TASK_DONE = "task_done"
    TASK_FAILED = "task_failed"
    TASK_RETRYING = "task_retrying"
    TASK_SKIPPED = "task_skipped"
    TASK_BLOCKED = "task_blocked"
```

### 事件模型定义

```python
# packages/backend/app/events/models.py
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from .types import EventType

class BaseEvent(BaseModel):
    type: EventType
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    def to_sse(self) -> str:
        """Convert event to SSE format"""
        import json
        data = self.model_dump(mode='json')
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

# Agent 事件
class AgentStartEvent(BaseEvent):
    type: EventType = EventType.AGENT_START
    task_id: Optional[str] = None
    agent_id: str
    agent_type: str  # Interview, Generation, Refinement, etc.
    agent_instance: Optional[int] = None

class AgentProgressEvent(BaseEvent):
    type: EventType = EventType.AGENT_PROGRESS
    task_id: Optional[str] = None
    agent_id: str
    message: str
    progress: Optional[int] = None  # 0-100

class AgentEndEvent(BaseEvent):
    type: EventType = EventType.AGENT_END
    task_id: Optional[str] = None
    agent_id: str
    status: str  # success, failed
    summary: Optional[str] = None

# Tool 事件
class ToolCallEvent(BaseEvent):
    type: EventType = EventType.TOOL_CALL
    task_id: Optional[str] = None
    agent_id: str
    tool_name: str
    tool_input: Optional[Dict[str, Any]] = None

class ToolResultEvent(BaseEvent):
    type: EventType = EventType.TOOL_RESULT
    task_id: Optional[str] = None
    agent_id: str
    tool_name: str
    success: bool
    tool_output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

# Plan 事件
class PlanCreatedEvent(BaseEvent):
    type: EventType = EventType.PLAN_CREATED
    plan: Dict[str, Any]  # {id, goal, tasks[]}

class PlanUpdatedEvent(BaseEvent):
    type: EventType = EventType.PLAN_UPDATED
    plan_id: str
    changes: List[Dict[str, Any]]  # [{task_id, field, old_value, new_value}]

# Task 事件
class TaskStartedEvent(BaseEvent):
    type: EventType = EventType.TASK_STARTED
    task_id: str
    task_title: str

class TaskProgressEvent(BaseEvent):
    type: EventType = EventType.TASK_PROGRESS
    task_id: str
    progress: int  # 0-100
    message: Optional[str] = None

class TaskDoneEvent(BaseEvent):
    type: EventType = EventType.TASK_DONE
    task_id: str
    result: Optional[Dict[str, Any]] = None  # {output_file, preview_url, summary}

class TaskFailedEvent(BaseEvent):
    type: EventType = EventType.TASK_FAILED
    task_id: str
    error_type: str  # temporary, logic, dependency
    error_message: str
    retry_count: int
    max_retries: int
    available_actions: List[str]  # retry, skip, modify, abort
    blocked_tasks: List[str]

class TaskRetryingEvent(BaseEvent):
    type: EventType = EventType.TASK_RETRYING
    task_id: str
    attempt: int
    max_attempts: int
    next_retry_in: int  # seconds

class ErrorEvent(BaseEvent):
    type: EventType = EventType.ERROR
    message: str
    details: Optional[str] = None

class DoneEvent(BaseEvent):
    type: EventType = EventType.DONE
    summary: Optional[str] = None
```

### 事件发射器

```python
# packages/backend/app/events/emitter.py
from typing import AsyncGenerator, Union
from datetime import datetime
import logging
from .models import BaseEvent

logger = logging.getLogger(__name__)

EventUnion = Union[
    AgentStartEvent, AgentProgressEvent, AgentEndEvent,
    ToolCallEvent, ToolResultEvent,
    PlanCreatedEvent, PlanUpdatedEvent,
    TaskStartedEvent, TaskProgressEvent, TaskDoneEvent,
    TaskFailedEvent, TaskRetryingEvent,
    ErrorEvent, DoneEvent
]

class EventEmitter:
    def __init__(self):
        self._events: list[EventUnion] = []

    def emit(self, event: EventUnion) -> None:
        """Emit an event"""
        if not event.timestamp:
            event.timestamp = datetime.utcnow()
        self._events.append(event)
        logger.debug(f"Event emitted: {event.type.value}")

    def get_events(self) -> list[EventUnion]:
        """Get all emitted events"""
        return self._events.copy()

    def clear(self) -> None:
        """Clear all events"""
        self._events.clear()

    async def stream(self) -> AsyncGenerator[str, None]:
        """Stream events as SSE"""
        for event in self._events:
            yield event.to_sse()
        yield "data: [DONE]\n\n"
```

### SSE 消息格式示例

```
data: {"type":"agent_start","timestamp":"2025-01-30T14:23:01Z","agent_id":"interview_1","agent_type":"Interview"}

data: {"type":"agent_progress","timestamp":"2025-01-30T14:23:02Z","agent_id":"interview_1","message":"正在分析用户需求...","progress":30}

data: {"type":"tool_call","timestamp":"2025-01-30T14:23:03Z","agent_id":"interview_1","tool_name":"analyze_intent","tool_input":{"message":"帮我做一个报名页面"}}

data: {"type":"agent_end","timestamp":"2025-01-30T14:23:05Z","agent_id":"interview_1","status":"success","summary":"收集了3个需求信息"}

data: [DONE]
```

## Testing Requirements

- [ ] Unit tests for all event models serialization
- [ ] Unit tests for EventEmitter emit/stream
- [ ] Integration tests for Orchestrator event emission
- [ ] Test SSE format output correctness
- [ ] Test backward compatibility with existing CLI

## Notes & Warnings

- 确保 timestamp 使用 UTC 时间
- 事件序列化时使用 `ensure_ascii=False` 以支持中文
- 保持与现有 ChatResponse 的兼容性，逐步迁移
- 考虑事件量大时的内存管理
