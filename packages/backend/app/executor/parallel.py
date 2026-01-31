from __future__ import annotations

import asyncio
import logging
from typing import AsyncGenerator, Dict, List, Optional

from sqlalchemy.orm import Session as DbSession

from ..agents.base import APIError, RateLimitError
from ..config import Settings
from ..db.models import Plan, Task, TaskStatus
from ..events.emitter import EventEmitter
from ..events.models import (
    DoneEvent,
    TaskBlockedEvent,
    TaskDoneEvent,
    TaskFailedEvent,
    TaskRetryingEvent,
    TaskStartedEvent,
)
from ..services.task import TaskService
from ..services.token_tracker import TokenTrackerService
from .retry import RetryPolicy, TemporaryError
from .scheduler import TaskScheduler
from .task_executor import ExecutionContext, TaskExecutorFactory

logger = logging.getLogger(__name__)


class ParallelExecutor:
    def __init__(
        self,
        *,
        db: DbSession,
        plan: Plan,
        emitter: EventEmitter,
        settings: Settings,
        output_dir: str,
        user_message: str,
        history: List[Dict[str, str]],
        max_concurrent: int = 5,
        task_timeout_seconds: float = 180.0,
        retry_policy: Optional[RetryPolicy] = None,
        poll_interval: float = 0.1,
    ) -> None:
        self.db = db
        self.plan = plan
        self.emitter = emitter
        self.settings = settings
        self.output_dir = output_dir
        self.user_message = user_message
        self.history = history
        self.max_concurrent = max_concurrent
        self.task_timeout_seconds = task_timeout_seconds
        self.retry_policy = retry_policy or RetryPolicy()
        self.poll_interval = poll_interval
        self.scheduler: Optional[TaskScheduler] = None
        self._running_tasks: Dict[str, asyncio.Task] = {}
        self._running_non_parallel: set[str] = set()
        self._aborted = False
        self._event_index = 0
        self.task_service = TaskService(db)
        self.task_lookup = {task.id: task for task in plan.tasks}
        self.context = ExecutionContext(
            db=db,
            session_id=plan.session_id,
            settings=settings,
            output_dir=output_dir,
            history=history,
            user_message=user_message,
            plan_goal=plan.goal,
            task_service=self.task_service,
            task_lookup=self.task_lookup,
        )

    async def execute(self) -> AsyncGenerator[object, None]:
        tasks = list(self.plan.tasks)
        self.scheduler = TaskScheduler(tasks)

        while True:
            if self._aborted:
                break

            ready_tasks = self._select_ready_tasks()
            for task in ready_tasks:
                self._start_task(task)

            for event in self._drain_events():
                yield event

            if self._should_stop():
                break

            await asyncio.sleep(self.poll_interval)

        self.emitter.emit(
            DoneEvent(
                summary=f"Plan {self.plan.id} execution completed",
                token_usage=TokenTrackerService(self.db).summarize_session(self.plan.session_id),
            )
        )
        for event in self._drain_events():
            yield event

    def _select_ready_tasks(self) -> List[Task]:
        if not self.scheduler:
            return []
        if self._running_non_parallel:
            return []
        available_slots = self.max_concurrent - len(self._running_tasks)
        if available_slots <= 0:
            return []

        ready = self.scheduler.get_ready_tasks(available_slots)
        selected: List[Task] = []
        for task in ready:
            if task.id in self._running_tasks:
                continue
            if not task.can_parallel and self._running_tasks:
                continue
            selected.append(task)
            if not task.can_parallel:
                break
            if len(selected) >= available_slots:
                break
        return selected

    def _start_task(self, task: Task) -> None:
        task_coro = asyncio.create_task(self._execute_task(task))
        self._running_tasks[task.id] = task_coro
        if not task.can_parallel:
            self._running_non_parallel.add(task.id)

        def _done_callback(done_task: asyncio.Task) -> None:
            self._running_tasks.pop(task.id, None)
            self._running_non_parallel.discard(task.id)
            if done_task.cancelled():
                return
            exc = done_task.exception()
            if exc:
                logger.exception("Task %s failed", task.id, exc_info=exc)

        task_coro.add_done_callback(_done_callback)

    def _drain_events(self) -> List[object]:
        events, new_index = self.emitter.events_since(self._event_index)
        self._event_index = new_index
        return events

    def _should_stop(self) -> bool:
        if not self.scheduler:
            return True
        if self.scheduler.is_all_done():
            return True
        if self.scheduler.has_failed() and not self._running_tasks:
            return True
        if not self._running_tasks:
            if not self.scheduler.get_ready_tasks(1):
                return True
        return False

    async def _execute_task(self, task: Task) -> None:
        if not self.scheduler:
            return
        self.task_service.set_status(task.id, TaskStatus.IN_PROGRESS.value, progress=0)
        self.emitter.emit(TaskStartedEvent(task_id=task.id, task_title=task.title))

        executor = TaskExecutorFactory.create(task.agent_type)
        retry_count = 0

        while True:
            if self._aborted:
                raise asyncio.CancelledError()
            try:
                result = await asyncio.wait_for(
                    executor.execute(task, self.emitter, self.context),
                    timeout=self.task_timeout_seconds,
                )
                self.task_service.set_status(
                    task.id,
                    TaskStatus.DONE.value,
                    progress=100,
                    result=result,
                )
                self.emitter.emit(TaskDoneEvent(task_id=task.id, result=result))
                if self.scheduler:
                    self.scheduler.mark_completed(task.id)
                break
            except asyncio.TimeoutError as exc:
                raise TemporaryError(
                    f"Task timed out after {int(self.task_timeout_seconds)}s"
                ) from exc
            except asyncio.CancelledError:
                self._handle_abort(task)
                raise
            except (TemporaryError, RateLimitError, APIError) as exc:
                retry_count += 1
                task.retry_count = retry_count
                if retry_count <= self.retry_policy.max_retries:
                    delay = self.retry_policy.get_delay(retry_count)
                    try:
                        self.task_service.retry_task(task.id, max_retries=self.retry_policy.max_retries)
                    except Exception:
                        logger.exception("Failed to mark task retrying")
                    self.emitter.emit(
                        TaskRetryingEvent(
                            task_id=task.id,
                            attempt=retry_count,
                            max_attempts=self.retry_policy.max_retries,
                            next_retry_in=int(delay),
                            retry_count=retry_count,
                        )
                    )
                    await asyncio.sleep(delay)
                    continue
                await self._handle_failure(task, str(exc), "temporary", retry_count)
                break
            except Exception as exc:
                await self._handle_failure(task, str(exc), "logic", retry_count)
                break

    async def _handle_failure(
        self,
        task: Task,
        error_message: str,
        error_type: str,
        retry_count: int,
    ) -> None:
        blocked_tasks: List[str] = []
        if self.scheduler:
            blocked_tasks = self.scheduler.mark_failed(task.id)
        try:
            self.task_service.set_status(task.id, TaskStatus.FAILED.value, message=error_message)
        except Exception:
            logger.exception("Failed to mark task failed")
        self.emitter.emit(
            TaskFailedEvent(
                task_id=task.id,
                error_type=error_type,
                error_message=error_message,
                retry_count=retry_count,
                max_retries=self.retry_policy.max_retries,
                available_actions=["retry", "skip", "modify", "abort"],
                blocked_tasks=blocked_tasks,
            )
        )
        for blocked_id in blocked_tasks:
            self.emitter.emit(
                TaskBlockedEvent(
                    task_id=blocked_id,
                    blocked_by=[task.id],
                    reason="dependency failed",
                )
            )

    def _handle_abort(self, task: Task) -> None:
        try:
            self.task_service.set_status(task.id, TaskStatus.ABORTED.value, message="aborted")
        except Exception:
            logger.exception("Failed to mark task aborted")

    def abort(self) -> None:
        self._aborted = True
        for running in list(self._running_tasks.values()):
            running.cancel()


__all__ = ["ParallelExecutor"]
