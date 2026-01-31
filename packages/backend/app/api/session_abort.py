from __future__ import annotations

from typing import Generator

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DbSession

from ..db.models import Session as SessionModel
from ..db.utils import get_db
from ..executor.manager import ExecutorManager
from ..services.task import TaskService

router = APIRouter(prefix="/api/session", tags=["sessions"])


def _get_db_session() -> Generator[DbSession, None, None]:
    with get_db() as session:
        yield session


@router.post("/{session_id}/abort")
def abort_session(
    session_id: str,
    db: DbSession = Depends(_get_db_session),
) -> dict:
    session = db.get(SessionModel, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    service = TaskService(db)
    plan_ids, completed_tasks, aborted_tasks = service.abort_session_with_details(session_id)
    if not plan_ids:
        raise HTTPException(status_code=404, detail="No active plan found")
    manager = ExecutorManager.get_instance()
    for plan_id in plan_ids:
        manager.abort(plan_id)
    db.commit()
    return {
        "success": True,
        "plan_ids": plan_ids,
        "completed_tasks": completed_tasks,
        "aborted_tasks": aborted_tasks,
    }


__all__ = ["router"]
