from __future__ import annotations

import asyncio
import logging
import time
from typing import AsyncGenerator, Dict, List, Optional

from sqlalchemy.orm import Session as DbSession

from ..agents.base import APIError, RateLimitError
from ..config import Settings
from ..db.models import Plan, PlanStatus, ProjectSnapshot, Task, TaskStatus, VersionSource
from ..events.emitter import EventEmitter
from ..events.models import (
    DoneEvent,
    TaskBlockedEvent,
    TaskDoneEvent,
    TaskFailedEvent,
    TaskRetryingEvent,
    TaskStartedEvent,
)
from ..services.project_snapshot import ProjectSnapshotService
from ..services.task import TaskService
from ..services.token_tracker import TokenTrackerService
from .retry import RetryPolicy, TemporaryError
from .scheduler import TaskScheduler
from .task_executor import ExecutionContext, TaskExecutorFactory
from ..exceptions import TrackedError, new_trace_id

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
        task_timeout_seconds: float = 600.0,
        retry_policy: Optional[RetryPolicy] = None,
        poll_interval: float = 1.0,
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
        self.task_timeout_minutes = int(getattr(settings, "task_timeout_minutes", 30))
        self.task_cleanup_interval_seconds = float(
            getattr(settings, "task_cleanup_interval_seconds", 60.0)
        )
        self._last_timeout_cleanup = 0.0
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

            self._maybe_cleanup_timeouts()
            ready_tasks = self._select_ready_tasks()
            for task in ready_tasks:
                self._start_task(task)

            for event in self._drain_events():
                yield event

            if self._should_stop():
                break

            await asyncio.sleep(self.poll_interval)

        self._maybe_create_auto_snapshot()
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
        if self._running_tasks:
            return False
        if self.scheduler.get_ready_tasks(1):
            return False
        return True

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
                error_message = f"Task timed out after {int(self.task_timeout_seconds)}s"
                await self._handle_timeout(task, error_message, exc)
                break
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
                await self._handle_failure(task, str(exc), "temporary", retry_count, exc=exc)
                break
            except Exception as exc:
                await self._handle_failure(task, str(exc), "logic", retry_count, exc=exc)
                break

    async def _handle_failure(
        self,
        task: Task,
        error_message: str,
        error_type: str,
        retry_count: int,
        exc: Exception | None = None,
    ) -> None:
        blocked_tasks: List[str] = []
        if self.scheduler:
            blocked_tasks = self.scheduler.mark_failed(task.id)
        trace_id = new_trace_id()
        if isinstance(exc, TrackedError):
            trace_id = exc.trace_id
        formatted_message = f"{error_message} (trace_id={trace_id})"
        self._log_task_error(
            task_id=task.id,
            error_type=error_type,
            error_message=formatted_message,
            trace_id=trace_id,
            exc=exc,
        )
        try:
            self.task_service.set_status(
                task.id,
                TaskStatus.FAILED.value,
                message=formatted_message,
            )
        except Exception:
            logger.exception("Failed to mark task failed")
        self.emitter.emit(
            TaskFailedEvent(
                task_id=task.id,
                error_type=error_type,
                error_message=formatted_message,
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
            trace_id = new_trace_id()
            self._log_task_error(
                task_id=task.id,
                error_type="aborted",
                error_message=f"aborted (trace_id={trace_id})",
                trace_id=trace_id,
            )
            self.task_service.set_status(
                task.id, TaskStatus.ABORTED.value, message=f"aborted (trace_id={trace_id})"
            )
        except Exception:
            logger.exception("Failed to mark task aborted")

    async def _handle_timeout(self, task: Task, message: str, exc: Exception | None = None) -> None:
        blocked_tasks: List[str] = []
        if self.scheduler:
            blocked_tasks = self.scheduler.mark_timeout(task.id)
        trace_id = new_trace_id()
        formatted_message = f"{message} (trace_id={trace_id})"
        self._log_task_error(
            task_id=task.id,
            error_type="timeout",
            error_message=formatted_message,
            trace_id=trace_id,
            exc=exc,
        )
        try:
            self.task_service.set_status(
                task.id,
                TaskStatus.TIMEOUT.value,
                message=formatted_message,
            )
        except Exception:
            logger.exception("Failed to mark task timeout")
        self.emitter.emit(
            TaskFailedEvent(
                task_id=task.id,
                error_type="timeout",
                error_message=formatted_message,
                retry_count=task.retry_count,
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
                    reason="dependency timed out",
                )
            )

    def abort(self) -> None:
        self._aborted = True
        for running in list(self._running_tasks.values()):
            running.cancel()

    def cleanup_timeout_tasks(self, timeout_minutes: int = 30) -> List[dict]:
        timed_out = self.task_service.cleanup_timeout_tasks(
            timeout_minutes=timeout_minutes,
            reason=f"timeout after {timeout_minutes}m",
        )
        if self.scheduler:
            for item in timed_out:
                task_id = item["task_id"]
                blocked = self.scheduler.mark_timeout(task_id)
                item["blocked_tasks"] = blocked
                if blocked:
                    for blocked_id in blocked:
                        self.emitter.emit(
                            TaskBlockedEvent(
                                task_id=blocked_id,
                                blocked_by=[task_id],
                                reason="dependency timed out",
                            )
                        )
        return timed_out

    def _maybe_cleanup_timeouts(self) -> None:
        now = time.monotonic()
        if now - self._last_timeout_cleanup < self.task_cleanup_interval_seconds:
            return
        self._last_timeout_cleanup = now
        timed_out = self.cleanup_timeout_tasks(timeout_minutes=self.task_timeout_minutes)
        if timed_out:
            for item in timed_out:
                task_id = item["task_id"]
                message = item["message"]
                blocked_tasks = item.get("blocked_tasks", [])
                self.emitter.emit(
                    TaskFailedEvent(
                        task_id=task_id,
                        error_type="timeout",
                        error_message=message,
                        retry_count=0,
                        max_retries=self.retry_policy.max_retries,
                        available_actions=["retry", "skip", "modify", "abort"],
                        blocked_tasks=blocked_tasks,
                    )
                )

    def _log_task_error(
        self,
        *,
        task_id: str,
        error_type: str,
        error_message: str,
        trace_id: str,
        exc: Exception | None = None,
    ) -> None:
        logger.error(
            "Task error: task_id=%s type=%s trace_id=%s message=%s",
            task_id,
            error_type,
            trace_id,
            error_message,
        )
        if exc is not None:
            logger.exception("Task error detail", exc_info=exc)

    def _maybe_create_auto_snapshot(self) -> None:
        try:
            plan = self.db.get(Plan, self.plan.id)
            if plan is None or plan.status != PlanStatus.DONE.value:
                return
            if any(task.status != TaskStatus.DONE.value for task in plan.tasks):
                return
            latest_auto = (
                self.db.query(ProjectSnapshot)
                .filter(ProjectSnapshot.session_id == plan.session_id)
                .filter(ProjectSnapshot.source == VersionSource.AUTO)
                .order_by(ProjectSnapshot.created_at.desc())
                .first()
            )
            if latest_auto and plan.updated_at and latest_auto.created_at >= plan.updated_at:
                return
            ProjectSnapshotService(self.db, event_emitter=self.emitter).create_snapshot(
                plan.session_id,
                source=VersionSource.AUTO,
                label=None,
            )
        except Exception:
            logger.exception("Failed to create auto snapshot")


__all__ = ["ParallelExecutor"]
