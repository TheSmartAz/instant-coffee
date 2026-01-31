# Phase B3: 并行执行引擎

## Metadata

- **Category**: Backend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: High
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: D1 (Plan/Task Schema), B1 (事件协议), B2 (Planner 服务)
  - **Blocks**: B4 (任务控制 API), F4 (Task 卡片视图)

## Goal

实现支持最多 5 个 Agent 并行执行的引擎，根据 Task 依赖关系调度执行，并实时发射执行事件。

## Detailed Tasks

### Task 1: 创建 TaskScheduler

**Description**: 实现基于依赖关系的任务调度器

**Implementation Details**:
- [ ] 创建 TaskScheduler 类
- [ ] 实现依赖图解析
- [ ] 实现 get_ready_tasks() 方法
- [ ] 实现 mark_completed() / mark_failed() 方法

**Files to modify/create**:
- `packages/backend/app/executor/__init__.py`
- `packages/backend/app/executor/scheduler.py`

**Acceptance Criteria**:
- [ ] 正确识别可执行的 Task
- [ ] 依赖完成后自动解锁下游 Task
- [ ] 处理循环依赖检测

---

### Task 2: 创建 ParallelExecutor

**Description**: 实现并行执行引擎核心

**Implementation Details**:
- [ ] 创建 ParallelExecutor 类
- [ ] 实现 execute() 异步方法
- [ ] 控制最大并行数 (5)
- [ ] 集成 EventEmitter 发射事件

**Files to modify/create**:
- `packages/backend/app/executor/parallel.py`

**Acceptance Criteria**:
- [ ] 最多 5 个 Task 并行执行
- [ ] 实时发射 task_started, task_progress, task_done 事件
- [ ] 支持 SSE 流式输出

---

### Task 3: 实现 Task 执行器

**Description**: 为每种 Agent 类型实现 Task 执行逻辑

**Implementation Details**:
- [ ] 创建 TaskExecutor 基类
- [ ] 实现 InterviewTaskExecutor
- [ ] 实现 GenerationTaskExecutor
- [ ] 实现 RefinementTaskExecutor
- [ ] 实现 ExportTaskExecutor

**Files to modify/create**:
- `packages/backend/app/executor/task_executor.py`

**Acceptance Criteria**:
- [ ] 每种 Agent 类型有对应的执行器
- [ ] 执行器发射细粒度事件
- [ ] 支持进度报告

---

### Task 4: 实现自动重试机制

**Description**: 实现 Task 失败后的自动重试

**Implementation Details**:
- [ ] 实现指数退避重试
- [ ] 区分临时错误和逻辑错误
- [ ] 发射 task_retrying 事件
- [ ] 达到最大重试次数后标记失败

**Files to modify/create**:
- `packages/backend/app/executor/retry.py`
- `packages/backend/app/executor/parallel.py`

**Acceptance Criteria**:
- [ ] 临时错误自动重试 3 次
- [ ] 重试间隔: 1s, 2s, 4s
- [ ] 重试过程对用户可见

---

### Task 5: 集成到 Orchestrator

**Description**: 将并行执行引擎集成到现有 Orchestrator

**Implementation Details**:
- [ ] 修改 Orchestrator 使用 ParallelExecutor
- [ ] 实现 stream_parallel() 方法
- [ ] 保持与现有 stream() 方法的兼容

**Files to modify/create**:
- `packages/backend/app/agents/orchestrator.py`

**Acceptance Criteria**:
- [ ] Orchestrator 支持并行执行模式
- [ ] 现有线性执行模式不受影响
- [ ] SSE 流正确返回所有事件

---

## Technical Specifications

### TaskScheduler 实现

```python
# packages/backend/app/executor/scheduler.py
from typing import Optional
from dataclasses import dataclass, field
from ..db.models import Task, TaskStatus

@dataclass
class TaskNode:
    task: Task
    dependencies: set[str] = field(default_factory=set)
    dependents: set[str] = field(default_factory=set)

class TaskScheduler:
    def __init__(self, tasks: list[Task]):
        self.nodes: dict[str, TaskNode] = {}
        self._build_graph(tasks)

    def _build_graph(self, tasks: list[Task]) -> None:
        # 创建节点
        for task in tasks:
            self.nodes[task.id] = TaskNode(
                task=task,
                dependencies=set(json.loads(task.depends_on or "[]"))
            )

        # 建立反向依赖
        for task_id, node in self.nodes.items():
            for dep_id in node.dependencies:
                if dep_id in self.nodes:
                    self.nodes[dep_id].dependents.add(task_id)

        # 检测循环依赖
        self._detect_cycles()

    def _detect_cycles(self) -> None:
        visited = set()
        rec_stack = set()

        def dfs(task_id: str) -> bool:
            visited.add(task_id)
            rec_stack.add(task_id)

            for dep_id in self.nodes[task_id].dependents:
                if dep_id not in visited:
                    if dfs(dep_id):
                        return True
                elif dep_id in rec_stack:
                    return True

            rec_stack.remove(task_id)
            return False

        for task_id in self.nodes:
            if task_id not in visited:
                if dfs(task_id):
                    raise ValueError("Circular dependency detected")

    def get_ready_tasks(self, max_count: int = 5) -> list[Task]:
        """获取可以执行的 Task (依赖已完成且未开始)"""
        ready = []
        for node in self.nodes.values():
            task = node.task
            if task.status != TaskStatus.PENDING.value:
                continue

            # 检查所有依赖是否完成
            deps_completed = all(
                self.nodes[dep_id].task.status == TaskStatus.DONE.value
                for dep_id in node.dependencies
                if dep_id in self.nodes
            )

            if deps_completed:
                ready.append(task)
                if len(ready) >= max_count:
                    break

        return ready

    def mark_completed(self, task_id: str) -> list[str]:
        """标记 Task 完成，返回被解锁的 Task ID 列表"""
        if task_id not in self.nodes:
            return []

        self.nodes[task_id].task.status = TaskStatus.DONE.value

        # 检查哪些下游 Task 被解锁
        unblocked = []
        for dependent_id in self.nodes[task_id].dependents:
            dependent_node = self.nodes[dependent_id]
            if dependent_node.task.status == TaskStatus.BLOCKED.value:
                # 检查是否所有依赖都完成
                all_deps_done = all(
                    self.nodes[dep_id].task.status == TaskStatus.DONE.value
                    for dep_id in dependent_node.dependencies
                )
                if all_deps_done:
                    dependent_node.task.status = TaskStatus.PENDING.value
                    unblocked.append(dependent_id)

        return unblocked

    def mark_failed(self, task_id: str) -> list[str]:
        """标记 Task 失败，返回被阻塞的 Task ID 列表"""
        if task_id not in self.nodes:
            return []

        self.nodes[task_id].task.status = TaskStatus.FAILED.value

        # 标记所有下游 Task 为 blocked
        blocked = []
        for dependent_id in self.nodes[task_id].dependents:
            dependent_node = self.nodes[dependent_id]
            if dependent_node.task.status == TaskStatus.PENDING.value:
                dependent_node.task.status = TaskStatus.BLOCKED.value
                blocked.append(dependent_id)

        return blocked

    def is_all_done(self) -> bool:
        """检查是否所有 Task 都完成"""
        return all(
            node.task.status in [TaskStatus.DONE.value, TaskStatus.SKIPPED.value]
            for node in self.nodes.values()
        )

    def has_failed(self) -> bool:
        """检查是否有 Task 失败"""
        return any(
            node.task.status == TaskStatus.FAILED.value
            for node in self.nodes.values()
        )
```

### ParallelExecutor 实现

```python
# packages/backend/app/executor/parallel.py
import asyncio
import logging
from typing import AsyncGenerator, Optional
from datetime import datetime

from ..db.models import Plan, Task, TaskStatus
from ..events.models import (
    TaskStartedEvent, TaskProgressEvent, TaskDoneEvent,
    TaskFailedEvent, TaskRetryingEvent, TaskBlockedEvent,
    DoneEvent
)
from ..events.emitter import EventEmitter
from .scheduler import TaskScheduler
from .task_executor import TaskExecutorFactory
from .retry import RetryPolicy

logger = logging.getLogger(__name__)

class ParallelExecutor:
    def __init__(
        self,
        plan: Plan,
        emitter: EventEmitter,
        max_concurrent: int = 5,
        retry_policy: Optional[RetryPolicy] = None
    ):
        self.plan = plan
        self.emitter = emitter
        self.max_concurrent = max_concurrent
        self.retry_policy = retry_policy or RetryPolicy()
        self.scheduler: Optional[TaskScheduler] = None
        self.running_tasks: set[str] = set()
        self._aborted = False

    async def execute(self) -> AsyncGenerator[str, None]:
        """Execute plan and yield SSE events"""
        tasks = list(self.plan.tasks)
        self.scheduler = TaskScheduler(tasks)

        while not self.scheduler.is_all_done() and not self._aborted:
            # 获取可执行的 Task
            available_slots = self.max_concurrent - len(self.running_tasks)
            if available_slots <= 0:
                await asyncio.sleep(0.1)
                continue

            ready_tasks = self.scheduler.get_ready_tasks(available_slots)

            if not ready_tasks and not self.running_tasks:
                # 没有可执行的 Task 且没有正在运行的 Task
                if self.scheduler.has_failed():
                    # 有失败的 Task，等待用户决策
                    break
                else:
                    # 所有 Task 完成
                    break

            # 并行启动 Task
            for task in ready_tasks:
                self.running_tasks.add(task.id)
                asyncio.create_task(self._execute_task(task))

            await asyncio.sleep(0.1)

        # 发射完成事件
        done_event = DoneEvent(
            summary=f"Plan {self.plan.id} execution completed"
        )
        self.emitter.emit(done_event)

        # 流式输出所有事件
        async for sse in self.emitter.stream():
            yield sse

    async def _execute_task(self, task: Task) -> None:
        """Execute a single task with retry"""
        # 发射开始事件
        self.emitter.emit(TaskStartedEvent(
            task_id=task.id,
            task_title=task.title
        ))

        task.status = TaskStatus.IN_PROGRESS.value
        task.started_at = datetime.utcnow()

        executor = TaskExecutorFactory.create(task.agent_type)
        retry_count = 0

        while retry_count <= self.retry_policy.max_retries:
            try:
                # 执行 Task
                result = await executor.execute(
                    task=task,
                    emitter=self.emitter
                )

                # 成功
                task.status = TaskStatus.DONE.value
                task.completed_at = datetime.utcnow()
                task.result = json.dumps(result)

                self.emitter.emit(TaskDoneEvent(
                    task_id=task.id,
                    result=result
                ))

                # 更新调度器
                unblocked = self.scheduler.mark_completed(task.id)
                for unblocked_id in unblocked:
                    logger.info(f"Task {unblocked_id} unblocked")

                break

            except TemporaryError as e:
                # 临时错误，重试
                retry_count += 1
                task.retry_count = retry_count

                if retry_count <= self.retry_policy.max_retries:
                    delay = self.retry_policy.get_delay(retry_count)
                    self.emitter.emit(TaskRetryingEvent(
                        task_id=task.id,
                        attempt=retry_count,
                        max_attempts=self.retry_policy.max_retries,
                        next_retry_in=delay
                    ))
                    await asyncio.sleep(delay)
                else:
                    # 重试次数用尽
                    await self._handle_failure(task, str(e), "temporary")

            except Exception as e:
                # 逻辑错误，不重试
                await self._handle_failure(task, str(e), "logic")
                break

        self.running_tasks.discard(task.id)

    async def _handle_failure(
        self,
        task: Task,
        error_message: str,
        error_type: str
    ) -> None:
        """Handle task failure"""
        task.status = TaskStatus.FAILED.value
        task.error_message = error_message

        blocked_tasks = self.scheduler.mark_failed(task.id)

        self.emitter.emit(TaskFailedEvent(
            task_id=task.id,
            error_type=error_type,
            error_message=error_message,
            retry_count=task.retry_count,
            max_retries=self.retry_policy.max_retries,
            available_actions=["retry", "skip", "modify", "abort"],
            blocked_tasks=blocked_tasks
        ))

    def abort(self) -> None:
        """Abort execution"""
        self._aborted = True
```

### RetryPolicy 实现

```python
# packages/backend/app/executor/retry.py
from dataclasses import dataclass

class TemporaryError(Exception):
    """Temporary error that can be retried"""
    pass

@dataclass
class RetryPolicy:
    max_retries: int = 3
    base_delay: float = 1.0
    multiplier: float = 2.0

    def get_delay(self, attempt: int) -> float:
        """Get delay for given attempt (exponential backoff)"""
        return self.base_delay * (self.multiplier ** (attempt - 1))
```

### TaskExecutor 实现

```python
# packages/backend/app/executor/task_executor.py
from abc import ABC, abstractmethod
from typing import Any, Optional
from ..db.models import Task
from ..events.emitter import EventEmitter
from ..events.models import AgentStartEvent, AgentProgressEvent, AgentEndEvent
from ..agents.interview import InterviewAgent
from ..agents.generation import GenerationAgent
from ..agents.refinement import RefinementAgent

class BaseTaskExecutor(ABC):
    @abstractmethod
    async def execute(
        self,
        task: Task,
        emitter: EventEmitter
    ) -> dict[str, Any]:
        pass

class InterviewTaskExecutor(BaseTaskExecutor):
    async def execute(self, task: Task, emitter: EventEmitter) -> dict:
        agent_id = f"interview_{task.id}"
        emitter.emit(AgentStartEvent(
            task_id=task.id,
            agent_id=agent_id,
            agent_type="Interview"
        ))

        # 执行 Interview Agent
        agent = InterviewAgent()
        result = await agent.run(task.description)

        emitter.emit(AgentEndEvent(
            task_id=task.id,
            agent_id=agent_id,
            status="success",
            summary=f"收集了 {len(result.get('questions', []))} 个需求信息"
        ))

        return result

class GenerationTaskExecutor(BaseTaskExecutor):
    async def execute(self, task: Task, emitter: EventEmitter) -> dict:
        agent_id = f"generation_{task.id}"
        emitter.emit(AgentStartEvent(
            task_id=task.id,
            agent_id=agent_id,
            agent_type="Generation"
        ))

        agent = GenerationAgent()

        # 模拟进度
        for progress in [20, 40, 60, 80, 100]:
            emitter.emit(AgentProgressEvent(
                task_id=task.id,
                agent_id=agent_id,
                message=f"生成进度 {progress}%",
                progress=progress
            ))
            result = await agent.generate_step(task.description, progress)

        emitter.emit(AgentEndEvent(
            task_id=task.id,
            agent_id=agent_id,
            status="success",
            summary="页面生成完成"
        ))

        return {"output_file": result.get("file_path")}

class TaskExecutorFactory:
    _executors = {
        "Interview": InterviewTaskExecutor,
        "Generation": GenerationTaskExecutor,
        "Refinement": RefinementTaskExecutor,
        "Export": ExportTaskExecutor,
    }

    @classmethod
    def create(cls, agent_type: str) -> BaseTaskExecutor:
        executor_class = cls._executors.get(agent_type)
        if not executor_class:
            raise ValueError(f"Unknown agent type: {agent_type}")
        return executor_class()
```

## Testing Requirements

- [ ] Unit tests for TaskScheduler dependency resolution
- [ ] Unit tests for TaskScheduler cycle detection
- [ ] Unit tests for ParallelExecutor max concurrency
- [ ] Unit tests for RetryPolicy exponential backoff
- [ ] Integration tests for full plan execution
- [ ] Test parallel execution with multiple Generation tasks
- [ ] Test failure handling and task blocking
- [ ] Test abort functionality

## Notes & Warnings

- 使用 `asyncio.create_task()` 启动并行任务，注意异常处理
- Task 状态更新需要同步到数据库
- 考虑添加执行超时机制 (120s per task)
- 并行执行时注意资源竞争 (如文件写入)
- 日志记录要包含 task_id 便于追踪
