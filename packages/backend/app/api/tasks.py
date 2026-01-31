from __future__ import annotations

from typing import Generator

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DbSession

from ..db.models import Task
from ..db.utils import get_db
from ..services.task import TaskService

router = APIRouter(prefix="/api/task", tags=["tasks"])


def _get_db_session() -> Generator[DbSession, None, None]:
    with get_db() as session:
        yield session


@router.post("/{task_id}/retry")
def retry_task(task_id: str, db: DbSession = Depends(_get_db_session)) -> dict:
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    service = TaskService(db)
    service.retry_task(task_id)
    db.commit()
    return {"success": True, "task_id": task_id}


@router.post("/{task_id}/skip")
def skip_task(task_id: str, db: DbSession = Depends(_get_db_session)) -> dict:
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    service = TaskService(db)
    service.skip_task(task_id, reason="skipped by user")
    db.commit()
    return {"success": True, "task_id": task_id}


__all__ = ["router"]
