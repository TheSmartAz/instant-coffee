import json

import pytest

from app.db.models import Task, TaskStatus
from app.executor.scheduler import TaskScheduler


def _task(task_id: str, status: str, depends_on=None):
    return Task(
        id=task_id,
        plan_id="plan-1",
        title=task_id,
        status=status,
        depends_on=json.dumps(depends_on) if depends_on is not None else None,
    )


def test_task_scheduler_ready_and_unblock() -> None:
    task_a = _task("a", TaskStatus.DONE.value)
    task_b = _task("b", TaskStatus.PENDING.value, ["a"])
    task_c = _task("c", TaskStatus.BLOCKED.value, ["b"])

    scheduler = TaskScheduler([task_a, task_b, task_c])
    ready = scheduler.get_ready_tasks()
    assert [task.id for task in ready] == ["b"]

    scheduler.mark_completed("b")
    assert task_c.status == TaskStatus.PENDING.value


def test_task_scheduler_cycle_detection() -> None:
    task_a = _task("a", TaskStatus.PENDING.value, ["b"])
    task_b = _task("b", TaskStatus.PENDING.value, ["a"])
    with pytest.raises(ValueError):
        TaskScheduler([task_a, task_b])
