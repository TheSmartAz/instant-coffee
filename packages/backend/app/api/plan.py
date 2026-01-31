from __future__ import annotations

import json
from typing import Generator, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DbSession

from ..db.models import Plan, Session as SessionModel, Task
from ..db.utils import get_db
from ..events.emitter import EventEmitter
from ..events.models import PlanCreatedEvent
from ..planner.factory import PlannerFactory
from ..services.event_store import EventStoreService
from ..services.plan import PlanService
from .models import PlanResponse, TaskResponse

router = APIRouter(prefix="/api", tags=["plan"])


class PlanRequest(BaseModel):
    session_id: str = Field(min_length=1)
    message: str = Field(min_length=1)
    context: Optional[str] = None


def _get_db_session() -> Generator[DbSession, None, None]:
    with get_db() as session:
        yield session


def _parse_json(value: Optional[str]):
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def _serialize_task(task: Task) -> TaskResponse:
    depends_on = _parse_json(task.depends_on)
    result = _parse_json(task.result)
    return TaskResponse(
        id=task.id,
        title=task.title,
        description=task.description,
        agent_type=task.agent_type,
        status=task.status,
        progress=task.progress,
        depends_on=depends_on,
        can_parallel=task.can_parallel,
        retry_count=task.retry_count,
        error_message=task.error_message,
        result=result,
        started_at=task.started_at,
        completed_at=task.completed_at,
    )


@router.post("/plan", response_model=PlanResponse)
async def create_plan(
    request: PlanRequest,
    db: DbSession = Depends(_get_db_session),
) -> PlanResponse:
    session = db.get(SessionModel, request.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    planner = PlannerFactory.create()
    service = PlanService(db)
    try:
        plan_payload = await planner.plan(
            user_message=request.message,
            context=request.context,
        )
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    tasks_payload = [task.model_dump() for task in plan_payload.tasks]
    plan = service.create_plan(
        session_id=request.session_id,
        goal=plan_payload.goal,
        tasks=tasks_payload,
        plan_id=plan_payload.id,
    )
    emitter = EventEmitter(
        session_id=request.session_id,
        event_store=EventStoreService(db),
    )
    emitter.emit(
        PlanCreatedEvent(
            plan={
                "id": plan.id,
                "goal": plan.goal,
                "tasks": tasks_payload,
            }
        )
    )
    db.commit()
    tasks = sorted(plan.tasks, key=lambda item: item.created_at or item.id)
    return PlanResponse(
        id=plan.id,
        session_id=plan.session_id,
        goal=plan.goal,
        status=plan.status,
        tasks=[_serialize_task(task) for task in tasks],
        created_at=plan.created_at,
        updated_at=plan.updated_at,
    )


@router.get("/plan/{plan_id}/status")
def get_plan_status(
    plan_id: str,
    db: DbSession = Depends(_get_db_session),
) -> dict:
    plan = db.get(Plan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")

    tasks_summary = {
        "total": len(plan.tasks),
        "pending": 0,
        "in_progress": 0,
        "done": 0,
        "failed": 0,
        "blocked": 0,
        "skipped": 0,
        "retrying": 0,
        "aborted": 0,
    }

    for task in plan.tasks:
        status = task.status
        if status in tasks_summary:
            tasks_summary[status] += 1

    return {
        "id": plan.id,
        "goal": plan.goal,
        "status": plan.status,
        "tasks": tasks_summary,
    }


__all__ = ["router"]
