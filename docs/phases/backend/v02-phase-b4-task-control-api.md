# Phase B4: 任务控制 API

## Metadata

- **Category**: Backend
- **Priority**: P1 (Important)
- **Estimated Complexity**: Medium
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: B3 (并行执行引擎)
  - **Blocks**: F5 (失败处理 UI)

## Goal

实现任务控制 API，支持用户重试失败任务、跳过任务、终止执行等操作。

## Detailed Tasks

### Task 1: 实现重试 API

**Description**: 允许用户重试失败的 Task

**Implementation Details**:
- [ ] 创建 POST /api/task/{id}/retry 端点
- [ ] 重置 Task 状态为 pending
- [ ] 触发 ParallelExecutor 重新调度
- [ ] 发射 task_started 事件

**Files to modify/create**:
- `packages/backend/app/api/task_control.py`

**Acceptance Criteria**:
- [ ] 失败的 Task 可以重试
- [ ] 重试后 Task 重新进入执行队列
- [ ] 下游被阻塞的 Task 保持阻塞状态

---

### Task 2: 实现跳过 API

**Description**: 允许用户跳过失败的 Task

**Implementation Details**:
- [ ] 创建 POST /api/task/{id}/skip 端点
- [ ] 将 Task 状态设为 skipped
- [ ] 解除下游 Task 的阻塞
- [ ] 发射 task_skipped 事件

**Files to modify/create**:
- `packages/backend/app/api/task_control.py`

**Acceptance Criteria**:
- [ ] 失败的 Task 可以跳过
- [ ] 下游 Task 被解除阻塞
- [ ] 跳过的 Task 不再执行

---

### Task 3: 实现终止 API

**Description**: 允许用户终止整个执行

**Implementation Details**:
- [ ] 创建 POST /api/session/{id}/abort 端点
- [ ] 停止所有正在执行的 Task
- [ ] 将 Plan 状态设为 aborted
- [ ] 保留已完成的 Task 结果

**Files to modify/create**:
- `packages/backend/app/api/task_control.py`

**Acceptance Criteria**:
- [ ] 可以终止整个执行
- [ ] 正在执行的 Task 被取消
- [ ] 已完成的结果被保留

---

### Task 4: 实现修改需求后重试

**Description**: 允许用户修改 Task 描述后重试

**Implementation Details**:
- [ ] 创建 POST /api/task/{id}/modify 端点
- [ ] 接收新的 Task 描述
- [ ] 更新 Task 并重试

**Files to modify/create**:
- `packages/backend/app/api/task_control.py`

**Acceptance Criteria**:
- [ ] 可以修改 Task 描述
- [ ] 修改后自动重试
- [ ] 保留修改历史

---

## Technical Specifications

### API 端点定义

```python
# packages/backend/app/api/task_control.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from ..db.utils import get_db
from ..db.models import Task, Plan, TaskStatus, PlanStatus
from ..events.models import TaskSkippedEvent, PlanUpdatedEvent
from ..executor.parallel import ParallelExecutor

router = APIRouter(prefix="/api")

# 存储活跃的执行器实例
active_executors: dict[str, ParallelExecutor] = {}

class RetryResponse(BaseModel):
    success: bool
    message: str
    task_id: str

class SkipResponse(BaseModel):
    success: bool
    message: str
    task_id: str
    unblocked_tasks: list[str]

class ModifyRequest(BaseModel):
    description: str

class AbortResponse(BaseModel):
    success: bool
    message: str
    plan_id: str
    completed_tasks: list[str]
    aborted_tasks: list[str]

@router.post("/task/{task_id}/retry", response_model=RetryResponse)
async def retry_task(
    task_id: str,
    db: Session = Depends(get_db)
):
    """重试失败的 Task"""
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status != TaskStatus.FAILED.value:
        raise HTTPException(
            status_code=400,
            detail=f"Task is not failed, current status: {task.status}"
        )

    # 重置 Task 状态
    task.status = TaskStatus.PENDING.value
    task.retry_count = 0
    task.error_message = None
    db.commit()

    # 通知执行器重新调度
    plan = db.get(Plan, task.plan_id)
    if plan.id in active_executors:
        executor = active_executors[plan.id]
        executor.scheduler.nodes[task_id].task.status = TaskStatus.PENDING.value

    return RetryResponse(
        success=True,
        message=f"Task {task_id} queued for retry",
        task_id=task_id
    )

@router.post("/task/{task_id}/skip", response_model=SkipResponse)
async def skip_task(
    task_id: str,
    db: Session = Depends(get_db)
):
    """跳过失败的 Task"""
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status not in [TaskStatus.FAILED.value, TaskStatus.BLOCKED.value]:
        raise HTTPException(
            status_code=400,
            detail=f"Task cannot be skipped, current status: {task.status}"
        )

    # 标记为跳过
    task.status = TaskStatus.SKIPPED.value
    db.commit()

    # 解除下游 Task 的阻塞
    unblocked_tasks = []
    plan = db.get(Plan, task.plan_id)

    for other_task in plan.tasks:
        if other_task.status == TaskStatus.BLOCKED.value:
            depends_on = json.loads(other_task.depends_on or "[]")
            if task_id in depends_on:
                # 检查其他依赖是否都完成或跳过
                all_deps_resolved = all(
                    db.get(Task, dep_id).status in [
                        TaskStatus.DONE.value,
                        TaskStatus.SKIPPED.value
                    ]
                    for dep_id in depends_on
                )
                if all_deps_resolved:
                    other_task.status = TaskStatus.PENDING.value
                    unblocked_tasks.append(other_task.id)

    db.commit()

    return SkipResponse(
        success=True,
        message=f"Task {task_id} skipped",
        task_id=task_id,
        unblocked_tasks=unblocked_tasks
    )

@router.post("/task/{task_id}/modify", response_model=RetryResponse)
async def modify_and_retry_task(
    task_id: str,
    request: ModifyRequest,
    db: Session = Depends(get_db)
):
    """修改 Task 描述后重试"""
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status != TaskStatus.FAILED.value:
        raise HTTPException(
            status_code=400,
            detail=f"Task is not failed, current status: {task.status}"
        )

    # 更新描述
    task.description = request.description
    task.status = TaskStatus.PENDING.value
    task.retry_count = 0
    task.error_message = None
    db.commit()

    return RetryResponse(
        success=True,
        message=f"Task {task_id} modified and queued for retry",
        task_id=task_id
    )

@router.post("/session/{session_id}/abort", response_model=AbortResponse)
async def abort_execution(
    session_id: str,
    db: Session = Depends(get_db)
):
    """终止执行"""
    # 获取当前 Plan
    plan = db.query(Plan).filter(
        Plan.session_id == session_id,
        Plan.status == PlanStatus.IN_PROGRESS.value
    ).first()

    if not plan:
        raise HTTPException(
            status_code=404,
            detail="No active plan found for this session"
        )

    # 通知执行器终止
    if plan.id in active_executors:
        executor = active_executors[plan.id]
        executor.abort()
        del active_executors[plan.id]

    # 更新状态
    completed_tasks = []
    aborted_tasks = []

    for task in plan.tasks:
        if task.status == TaskStatus.DONE.value:
            completed_tasks.append(task.id)
        elif task.status in [
            TaskStatus.IN_PROGRESS.value,
            TaskStatus.PENDING.value,
            TaskStatus.BLOCKED.value
        ]:
            task.status = TaskStatus.SKIPPED.value
            aborted_tasks.append(task.id)

    plan.status = PlanStatus.ABORTED.value
    db.commit()

    return AbortResponse(
        success=True,
        message=f"Execution aborted for plan {plan.id}",
        plan_id=plan.id,
        completed_tasks=completed_tasks,
        aborted_tasks=aborted_tasks
    )

@router.get("/task/{task_id}/status")
async def get_task_status(
    task_id: str,
    db: Session = Depends(get_db)
):
    """获取 Task 状态"""
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return {
        "id": task.id,
        "title": task.title,
        "status": task.status,
        "progress": task.progress,
        "retry_count": task.retry_count,
        "error_message": task.error_message
    }

@router.get("/plan/{plan_id}/status")
async def get_plan_status(
    plan_id: str,
    db: Session = Depends(get_db)
):
    """获取 Plan 状态"""
    plan = db.get(Plan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    tasks_summary = {
        "total": len(plan.tasks),
        "pending": 0,
        "in_progress": 0,
        "done": 0,
        "failed": 0,
        "blocked": 0,
        "skipped": 0
    }

    for task in plan.tasks:
        if task.status in tasks_summary:
            tasks_summary[task.status] += 1

    return {
        "id": plan.id,
        "goal": plan.goal,
        "status": plan.status,
        "tasks": tasks_summary
    }
```

### 注册路由

```python
# packages/backend/app/main.py (更新)
from .api.task_control import router as task_control_router

app.include_router(task_control_router)
```

### 执行器管理

```python
# packages/backend/app/executor/manager.py
from typing import Optional
from .parallel import ParallelExecutor

class ExecutorManager:
    """管理活跃的执行器实例"""
    _instance: Optional['ExecutorManager'] = None
    _executors: dict[str, ParallelExecutor] = {}

    @classmethod
    def get_instance(cls) -> 'ExecutorManager':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, plan_id: str, executor: ParallelExecutor) -> None:
        self._executors[plan_id] = executor

    def unregister(self, plan_id: str) -> None:
        if plan_id in self._executors:
            del self._executors[plan_id]

    def get(self, plan_id: str) -> Optional[ParallelExecutor]:
        return self._executors.get(plan_id)

    def abort(self, plan_id: str) -> bool:
        executor = self.get(plan_id)
        if executor:
            executor.abort()
            self.unregister(plan_id)
            return True
        return False
```

## Testing Requirements

- [ ] Unit tests for retry API
- [ ] Unit tests for skip API
- [ ] Unit tests for abort API
- [ ] Unit tests for modify API
- [ ] Integration tests for retry → re-execution flow
- [ ] Integration tests for skip → unblock flow
- [ ] Test concurrent API calls
- [ ] Test invalid state transitions

## Notes & Warnings

- 重试时需要确保 Task 状态正确重置
- 跳过 Task 时需要正确处理依赖链
- 终止执行时需要优雅地停止正在运行的 Task
- 考虑添加操作日志记录
- API 需要处理并发请求的竞态条件
