# Phase D1: Plan 和 Task 数据模型扩展

## Metadata

- **Category**: Database
- **Priority**: P0 (Critical)
- **Estimated Complexity**: Medium
- **Parallel Development**: ✅ Can develop in parallel
- **Dependencies**:
  - **Blocked by**: None
  - **Blocks**: B2 (Planner 服务), B3 (并行执行引擎)

## Goal

扩展数据库 schema 以支持 Plan 和 Task 的存储，为多 Agent 并行执行提供数据基础。

## Detailed Tasks

### Task 1: 创建 plans 表

**Description**: 存储 AI Planner 生成的执行计划

**Implementation Details**:
- [ ] 创建 plans 表迁移脚本
- [ ] 添加 Plan SQLAlchemy 模型
- [ ] 添加 Plan Pydantic schema

**Files to modify/create**:
- `packages/backend/app/db/models.py`
- `packages/backend/app/db/migrations.py`
- `packages/backend/app/api/models.py`

**Acceptance Criteria**:
- [ ] plans 表成功创建
- [ ] 可以通过 ORM 进行 CRUD 操作
- [ ] 与 sessions 表正确关联

---

### Task 2: 创建 tasks 表

**Description**: 存储 Plan 中的各个 Task 及其状态

**Implementation Details**:
- [ ] 创建 tasks 表迁移脚本
- [ ] 添加 Task SQLAlchemy 模型
- [ ] 添加 Task Pydantic schema
- [ ] 实现 Task 状态枚举

**Files to modify/create**:
- `packages/backend/app/db/models.py`
- `packages/backend/app/db/migrations.py`
- `packages/backend/app/api/models.py`

**Acceptance Criteria**:
- [ ] tasks 表成功创建
- [ ] Task 状态可以正确更新
- [ ] 与 plans 表正确关联

---

### Task 3: 创建 task_events 表

**Description**: 存储 Task 执行过程中的事件日志

**Implementation Details**:
- [ ] 创建 task_events 表迁移脚本
- [ ] 添加 TaskEvent SQLAlchemy 模型
- [ ] 支持多种事件类型存储

**Files to modify/create**:
- `packages/backend/app/db/models.py`
- `packages/backend/app/db/migrations.py`

**Acceptance Criteria**:
- [ ] task_events 表成功创建
- [ ] 可以记录 agent_start, agent_progress, tool_call 等事件
- [ ] 支持按 task_id 查询事件历史

---

## Technical Specifications

### 表结构设计

```sql
-- plans 表
CREATE TABLE plans (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    goal TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',  -- pending, in_progress, done, failed, aborted
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

-- tasks 表
CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    agent_type TEXT,  -- Interview, Generation, Refinement, Validator, Export
    status TEXT NOT NULL DEFAULT 'pending',  -- pending, in_progress, done, failed, blocked, skipped, retrying
    progress INTEGER DEFAULT 0,  -- 0-100
    depends_on TEXT,  -- JSON array of task_ids
    can_parallel BOOLEAN DEFAULT TRUE,
    retry_count INTEGER DEFAULT 0,
    error_message TEXT,
    result TEXT,  -- JSON object with output_file, preview_url, summary
    started_at DATETIME,
    completed_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (plan_id) REFERENCES plans(id)
);

-- task_events 表
CREATE TABLE task_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    event_type TEXT NOT NULL,  -- agent_start, agent_progress, agent_end, tool_call, tool_result, error
    agent_id TEXT,
    agent_type TEXT,
    message TEXT,
    progress INTEGER,
    tool_name TEXT,
    tool_input TEXT,  -- JSON
    tool_output TEXT,  -- JSON
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);

-- 索引
CREATE INDEX idx_plans_session_id ON plans(session_id);
CREATE INDEX idx_tasks_plan_id ON tasks(plan_id);
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_task_events_task_id ON task_events(task_id);
CREATE INDEX idx_task_events_timestamp ON task_events(timestamp);
```

### SQLAlchemy 模型

```python
from sqlalchemy import Column, String, Text, Integer, Boolean, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
import enum

class PlanStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    FAILED = "failed"
    ABORTED = "aborted"

class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    FAILED = "failed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"
    RETRYING = "retrying"

class Plan(Base):
    __tablename__ = "plans"

    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)
    goal = Column(Text, nullable=False)
    status = Column(String, default=PlanStatus.PENDING.value)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    session = relationship("Session", back_populates="plans")
    tasks = relationship("Task", back_populates="plan", cascade="all, delete-orphan")

class Task(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True)
    plan_id = Column(String, ForeignKey("plans.id"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text)
    agent_type = Column(String)
    status = Column(String, default=TaskStatus.PENDING.value)
    progress = Column(Integer, default=0)
    depends_on = Column(Text)  # JSON array
    can_parallel = Column(Boolean, default=True)
    retry_count = Column(Integer, default=0)
    error_message = Column(Text)
    result = Column(Text)  # JSON object
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    plan = relationship("Plan", back_populates="tasks")
    events = relationship("TaskEvent", back_populates="task", cascade="all, delete-orphan")

class TaskEvent(Base):
    __tablename__ = "task_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, ForeignKey("tasks.id"), nullable=False)
    event_type = Column(String, nullable=False)
    agent_id = Column(String)
    agent_type = Column(String)
    message = Column(Text)
    progress = Column(Integer)
    tool_name = Column(String)
    tool_input = Column(Text)
    tool_output = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)

    task = relationship("Task", back_populates="events")
```

### Pydantic Schemas

```python
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from enum import Enum

class TaskStatusEnum(str, Enum):
    pending = "pending"
    in_progress = "in_progress"
    done = "done"
    failed = "failed"
    blocked = "blocked"
    skipped = "skipped"
    retrying = "retrying"

class TaskCreate(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    agent_type: Optional[str] = None
    depends_on: Optional[List[str]] = None
    can_parallel: bool = True

class TaskResponse(BaseModel):
    id: str
    title: str
    description: Optional[str]
    agent_type: Optional[str]
    status: TaskStatusEnum
    progress: int
    depends_on: Optional[List[str]]
    can_parallel: bool
    retry_count: int
    error_message: Optional[str]
    result: Optional[dict]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

class PlanCreate(BaseModel):
    goal: str
    tasks: List[TaskCreate]

class PlanResponse(BaseModel):
    id: str
    session_id: str
    goal: str
    status: str
    tasks: List[TaskResponse]
    created_at: datetime
    updated_at: datetime
```

## Testing Requirements

- [ ] Unit tests for Plan model CRUD operations
- [ ] Unit tests for Task model CRUD operations
- [ ] Unit tests for TaskEvent model CRUD operations
- [ ] Integration tests for Plan-Task-Event relationships
- [ ] Test Task status transitions
- [ ] Test depends_on JSON serialization/deserialization

## Notes & Warnings

- `depends_on` 字段存储为 JSON 字符串，需要在应用层进行序列化/反序列化
- Task 状态变更需要同时更新 Plan 状态
- 删除 Plan 时需要级联删除关联的 Tasks 和 TaskEvents
- 考虑为 task_events 表添加定期清理机制，避免数据膨胀
