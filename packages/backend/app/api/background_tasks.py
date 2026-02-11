"""Background task API endpoints."""

from __future__ import annotations

from typing import Generator, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session as DbSession

from ..db.utils import get_db
from ..services.background_tasks import BackgroundTaskService


def _get_db_session() -> Generator[DbSession, None, None]:
    with get_db() as session:
        yield session


router = APIRouter(prefix="/api/background-tasks", tags=["background-tasks"])


@router.get("/{session_id}")
def list_tasks(
    session_id: str,
    db: DbSession = Depends(_get_db_session),
):
    """List all background tasks for a session."""
    service = BackgroundTaskService(db)

    from ..engine.registry import get_engine_orchestrator

    engine_orch = get_engine_orchestrator(session_id)
    if engine_orch and hasattr(engine_orch, '_task_manager'):
        service.set_task_manager(engine_orch._task_manager)

    return {"tasks": service.list_tasks(session_id)}


@router.get("/{session_id}/{task_id}")
def get_task(
    session_id: str,
    task_id: str,
    db: DbSession = Depends(_get_db_session),
):
    """Get details of a specific background task."""
    service = BackgroundTaskService(db)

    from ..engine.registry import get_engine_orchestrator

    engine_orch = get_engine_orchestrator(session_id)
    if engine_orch and hasattr(engine_orch, '_task_manager'):
        service.set_task_manager(engine_orch._task_manager)

    task = service.get_task(session_id, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return task


@router.post("/{session_id}/{task_id}/stop")
def stop_task(
    session_id: str,
    task_id: str,
    db: DbSession = Depends(_get_db_session),
):
    """Stop a running background task."""
    service = BackgroundTaskService(db)

    from ..engine.registry import get_engine_orchestrator

    engine_orch = get_engine_orchestrator(session_id)
    if engine_orch and hasattr(engine_orch, '_task_manager'):
        service.set_task_manager(engine_orch._task_manager)

    if service.stop_task(session_id, task_id):
        return {"success": True, "task_id": task_id}

    raise HTTPException(status_code=404, detail="Task not found or could not be stopped")


@router.get("/{session_id}/{task_id}/output")
def get_task_output(
    session_id: str,
    task_id: str,
    since: int = Query(None),
    db: DbSession = Depends(_get_db_session),
):
    """Get output from a background task."""
    service = BackgroundTaskService(db)

    from ..engine.registry import get_engine_orchestrator

    engine_orch = get_engine_orchestrator(session_id)
    if engine_orch and hasattr(engine_orch, '_task_manager'):
        service.set_task_manager(engine_orch._task_manager)

    return service.get_task_output(session_id, task_id, since)


__all__ = ["router"]
