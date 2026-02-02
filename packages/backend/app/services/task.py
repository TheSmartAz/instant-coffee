from __future__ import annotations

import json
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy.orm import Session as DbSession

from ..db.models import Plan, PlanStatus, Task, TaskEvent, TaskStatus
from ..exceptions import new_trace_id
from .plan import PlanService


def _parse_depends_on(value: Optional[str]) -> List[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(item) for item in parsed]
        except json.JSONDecodeError:
            return [value]
    return [str(value)]


class TaskService:
    """Service for managing plan tasks and their dependencies."""

    def __init__(self, db: DbSession) -> None:
        self.db = db
        self._plan_service = PlanService(db)

    def get_task(self, task_id: str) -> Optional[Task]:
        return self.db.get(Task, task_id)

    def update_task(self, task_id: str, **fields: Any) -> Task:
        task = self.get_task(task_id)
        if task is None:
            raise ValueError(f"Task not found: {task_id}")
        for key, value in fields.items():
            if value is None:
                continue
            if hasattr(task, key):
                setattr(task, key, value)
        self.db.add(task)
        self.db.flush()
        self._plan_service.recompute_status(task.plan_id)
        return task

    def set_status(
        self,
        task_id: str,
        status: str,
        *,
        progress: Optional[int] = None,
        message: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
    ) -> Task:
        task = self.get_task(task_id)
        if task is None:
            raise ValueError(f"Task not found: {task_id}")
        if isinstance(status, Enum):
            status = status.value
        previous_status = task.status
        task.status = status
        if progress is not None:
            task.progress = progress
        if message is not None:
            task.error_message = message
        if result is not None:
            task.result = json.dumps(result, ensure_ascii=False)
        now = datetime.utcnow()
        if status in (TaskStatus.IN_PROGRESS.value, TaskStatus.RETRYING.value):
            task.started_at = task.started_at or now
        if status in (
            TaskStatus.DONE.value,
            TaskStatus.FAILED.value,
            TaskStatus.SKIPPED.value,
            TaskStatus.ABORTED.value,
            TaskStatus.TIMEOUT.value,
        ):
            task.completed_at = task.completed_at or now
        self.db.add(task)
        self.db.flush()
        if status in (TaskStatus.FAILED.value, TaskStatus.ABORTED.value, TaskStatus.TIMEOUT.value):
            self._block_dependents(task, reason=message)
        if status in (TaskStatus.DONE.value, TaskStatus.SKIPPED.value):
            self._unblock_dependents_if_ready(task.plan_id)
        if previous_status != status and previous_status == TaskStatus.BLOCKED.value:
            self._unblock_dependents_if_ready(task.plan_id)
        self._plan_service.recompute_status(task.plan_id)
        return task

    def retry_task(self, task_id: str, *, max_retries: int = 3) -> Task:
        task = self.get_task(task_id)
        if task is None:
            raise ValueError(f"Task not found: {task_id}")
        task.retry_count = min(task.retry_count + 1, max_retries)
        return self.set_status(task_id, TaskStatus.RETRYING.value)

    def reset_task_for_retry(self, task_id: str) -> Task:
        task = self.get_task(task_id)
        if task is None:
            raise ValueError(f"Task not found: {task_id}")
        return self._reset_task_state(task)

    def skip_task(self, task_id: str, *, reason: Optional[str] = None) -> Task:
        return self.set_status(task_id, TaskStatus.SKIPPED.value, message=reason)

    def modify_task_and_retry(self, task_id: str, description: str) -> Task:
        task = self.get_task(task_id)
        if task is None:
            raise ValueError(f"Task not found: {task_id}")
        if description != task.description:
            self._record_task_modification(task, task.description, description)
            task.description = description
        return self._reset_task_state(task)

    def abort_plan(self, plan_id: str) -> Optional[Plan]:
        plan = self.db.get(Plan, plan_id)
        if plan is None:
            return None
        plan.status = PlanStatus.ABORTED.value
        plan.updated_at = datetime.utcnow()
        self.db.add(plan)
        tasks = self.db.query(Task).filter(Task.plan_id == plan_id).all()
        for task in tasks:
            if task.status in (
                TaskStatus.DONE.value,
                TaskStatus.FAILED.value,
                TaskStatus.SKIPPED.value,
                TaskStatus.ABORTED.value,
                TaskStatus.TIMEOUT.value,
            ):
                continue
            task.status = TaskStatus.ABORTED.value
            task.completed_at = task.completed_at or datetime.utcnow()
            self.db.add(task)
        self.db.flush()
        return plan

    def cleanup_timeout_tasks(
        self,
        *,
        timeout_minutes: int = 30,
        reason: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        cutoff = datetime.utcnow() - timedelta(minutes=timeout_minutes)
        candidates = (
            self.db.query(Task)
            .filter(Task.status.in_([TaskStatus.IN_PROGRESS.value, TaskStatus.RETRYING.value]))
            .filter(Task.started_at.isnot(None))
            .filter(Task.started_at < cutoff)
            .all()
        )
        timed_out: List[Dict[str, str]] = []
        for task in candidates:
            trace_id = new_trace_id()
            base_message = reason or f"timeout after {timeout_minutes}m"
            message = f"{base_message} (trace_id={trace_id})"
            self.set_status(task.id, TaskStatus.TIMEOUT.value, message=message)
            timed_out.append({"task_id": task.id, "message": message})
        return timed_out

    def abort_session(self, session_id: str) -> List[str]:
        plans = (
            self.db.query(Plan)
            .filter(Plan.session_id == session_id)
            .filter(Plan.status.notin_(
                [PlanStatus.DONE.value, PlanStatus.FAILED.value, PlanStatus.ABORTED.value]
            ))
            .all()
        )
        if not plans:
            return []
        plan_ids: List[str] = []
        for plan in plans:
            plan_ids.append(plan.id)
            self.abort_plan(plan.id)
        return plan_ids

    def abort_session_with_details(
        self, session_id: str
    ) -> tuple[List[str], List[str], List[str]]:
        plans = (
            self.db.query(Plan)
            .filter(Plan.session_id == session_id)
            .filter(Plan.status.notin_(
                [PlanStatus.DONE.value, PlanStatus.FAILED.value, PlanStatus.ABORTED.value]
            ))
            .all()
        )
        if not plans:
            return [], [], []
        plan_ids: List[str] = []
        completed_tasks: List[str] = []
        aborted_tasks: List[str] = []
        for plan in plans:
            plan_ids.append(plan.id)
            tasks = self.db.query(Task).filter(Task.plan_id == plan.id).all()
            for task in tasks:
                if task.status == TaskStatus.DONE.value:
                    completed_tasks.append(task.id)
                if task.status not in (
                    TaskStatus.DONE.value,
                    TaskStatus.FAILED.value,
                    TaskStatus.SKIPPED.value,
                    TaskStatus.ABORTED.value,
                    TaskStatus.TIMEOUT.value,
                ):
                    aborted_tasks.append(task.id)
            self.abort_plan(plan.id)
        return plan_ids, completed_tasks, aborted_tasks

    def _record_task_modification(
        self,
        task: Task,
        old_description: Optional[str],
        new_description: Optional[str],
    ) -> None:
        payload = {
            "old_description": old_description,
            "new_description": new_description,
        }
        event = TaskEvent(
            task_id=task.id,
            event_type="task_modified",
            message="Task description modified",
            payload=json.dumps(payload, ensure_ascii=False),
            timestamp=datetime.utcnow(),
        )
        self.db.add(event)

    def _reset_task_state(self, task: Task) -> Task:
        task.status = TaskStatus.PENDING.value
        task.progress = 0
        task.retry_count = 0
        task.error_message = None
        task.result = None
        task.started_at = None
        task.completed_at = None
        self.db.add(task)
        self.db.flush()
        self._plan_service.recompute_status(task.plan_id)
        return task

    def _block_dependents(self, task: Task, *, reason: Optional[str] = None) -> None:
        tasks, task_map = self._load_plan_tasks(task.plan_id)
        for candidate in tasks:
            if candidate.id == task.id:
                continue
            if candidate.status in (
                TaskStatus.DONE.value,
                TaskStatus.SKIPPED.value,
                TaskStatus.FAILED.value,
                TaskStatus.ABORTED.value,
                TaskStatus.TIMEOUT.value,
            ):
                continue
            depends_on = _parse_depends_on(candidate.depends_on)
            if task.id in depends_on:
                candidate.status = TaskStatus.BLOCKED.value
                if reason:
                    candidate.error_message = reason
                self.db.add(candidate)

    def _unblock_dependents_if_ready(self, plan_id: str) -> None:
        tasks, task_map = self._load_plan_tasks(plan_id)
        for candidate in tasks:
            if candidate.status != TaskStatus.BLOCKED.value:
                continue
            depends_on = _parse_depends_on(candidate.depends_on)
            if not depends_on:
                continue
            if all(
                task_map.get(dep) is not None
                and task_map[dep].status in (TaskStatus.DONE.value, TaskStatus.SKIPPED.value)
                for dep in depends_on
            ):
                candidate.status = TaskStatus.PENDING.value
                candidate.error_message = None
                self.db.add(candidate)

    def _load_plan_tasks(self, plan_id: str) -> tuple[List[Task], Dict[str, Task]]:
        tasks = self.db.query(Task).filter(Task.plan_id == plan_id).all()
        task_map = {task.id: task for task in tasks}
        return tasks, task_map


__all__ = ["TaskService"]
