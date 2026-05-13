from __future__ import annotations

from datetime import timedelta
from typing import Any, Generator, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session as DbSession

from ..db.models import Page, Session as SessionModel, SessionRun, TokenUsage
from ..db.utils import get_db
from ..events.emitter import EventEmitter
from ..events.models import run_lifecycle_event
from ..events.types import EventType
from ..schemas.run import RunStatus
from ..services.event_store import EventStoreService
from ..services.export import ExportService
from ..services.plan_compat import (
    PlanCompatConflictError,
    PlanCompatNotFoundError,
    PlanCompatService,
)
from ..services.run import RunNotFoundError, RunService, RunStateConflictError
from ..utils.datetime import utcnow

router = APIRouter(prefix="/api", tags=["compat"])


class ExportRequest(BaseModel):
    session_id: Optional[str] = None
    version: Optional[int] = None
    output_dir: Optional[str] = None


class PlanTaskRequest(BaseModel):
    id: Optional[str] = None
    title: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    depends_on: list[str] = Field(default_factory=list)
    can_parallel: bool = False
    status: Optional[str] = None
    agent_type: Optional[str] = None
    progress: Optional[int] = None
    retry_count: Optional[int] = None
    error_message: Optional[str] = None


class PlanRequest(BaseModel):
    session_id: str
    message: Optional[str] = None
    goal: Optional[str] = None
    context: Any = None
    tasks: list[PlanTaskRequest] = Field(default_factory=list)
    target_pages: list[str] = Field(default_factory=list)


class TaskRetryRequest(BaseModel):
    reason: Optional[str] = None
    max_attempts: int = 3


class TaskSkipRequest(BaseModel):
    reason: Optional[str] = None


class TaskModifyRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    reason: Optional[str] = None


def _get_db_session() -> Generator[DbSession, None, None]:
    with get_db() as session:
        yield session


def _export_payload(result) -> dict:
    return {
        "export_dir": result.export_dir,
        "manifest": result.manifest,
        "success": result.success,
        "file_path": result.file_path,
        "assets_file": result.assets_file,
    }


def _run_export(
    db: DbSession,
    *,
    session_id: str,
    output_dir: Optional[str] = None,
    version: Optional[int] = None,
) -> dict:
    try:
        result = ExportService(db).export_session(
            session_id,
            output_dir=output_dir,
            version=version,
        )
    except ValueError as exc:
        if str(exc) == "Session not found":
            raise HTTPException(status_code=404, detail="Session not found") from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _export_payload(result)


def _plan_service(db: DbSession) -> PlanCompatService:
    return PlanCompatService(db)


def _handle_plan_error(exc: Exception) -> None:
    if isinstance(exc, PlanCompatNotFoundError):
        detail = str(exc)
        raise HTTPException(status_code=404, detail=detail) from exc
    if isinstance(exc, PlanCompatConflictError):
        detail = str(exc)
        raise HTTPException(status_code=409, detail=detail) from exc
    raise exc


@router.post("/sessions/{session_id}/export")
def export_session(
    session_id: str,
    payload: Optional[ExportRequest] = None,
    db: DbSession = Depends(_get_db_session),
) -> dict:
    payload = payload or ExportRequest()
    return _run_export(
        db,
        session_id=session_id,
        output_dir=payload.output_dir,
        version=payload.version,
    )


@router.post("/export")
def export_legacy(
    payload: ExportRequest,
    db: DbSession = Depends(_get_db_session),
) -> dict:
    if not payload.session_id:
        raise HTTPException(status_code=422, detail="session_id is required")
    return _run_export(
        db,
        session_id=payload.session_id,
        output_dir=payload.output_dir,
        version=payload.version,
    )


@router.post("/plan", status_code=201)
def create_plan(
    payload: PlanRequest,
    db: DbSession = Depends(_get_db_session),
) -> dict:
    try:
        result = _plan_service(db).create_plan(
            session_id=payload.session_id,
            message=payload.message,
            goal=payload.goal,
            context=payload.context,
            tasks=[task.model_dump(exclude_none=True) for task in payload.tasks],
            target_pages=payload.target_pages,
        )
    except Exception as exc:
        _handle_plan_error(exc)
        raise
    db.commit()
    return result


@router.get("/plan/{plan_id}/status")
def get_plan_status(
    plan_id: str,
    db: DbSession = Depends(_get_db_session),
) -> dict:
    try:
        return _plan_service(db).get_plan_status(plan_id)
    except Exception as exc:
        _handle_plan_error(exc)
        raise


@router.get("/task/{task_id}/status")
def get_task_status(
    task_id: str,
    db: DbSession = Depends(_get_db_session),
) -> dict:
    try:
        return _plan_service(db).get_task_status(task_id)
    except Exception as exc:
        _handle_plan_error(exc)
        raise


@router.post("/task/{task_id}/retry")
def retry_task(
    task_id: str,
    payload: Optional[TaskRetryRequest] = None,
    db: DbSession = Depends(_get_db_session),
) -> dict:
    payload = payload or TaskRetryRequest()
    try:
        result = _plan_service(db).retry_task(
            task_id,
            reason=payload.reason,
            max_attempts=payload.max_attempts,
        )
    except Exception as exc:
        _handle_plan_error(exc)
        raise
    db.commit()
    return result


@router.post("/task/{task_id}/skip")
def skip_task(
    task_id: str,
    payload: Optional[TaskSkipRequest] = None,
    db: DbSession = Depends(_get_db_session),
) -> dict:
    payload = payload or TaskSkipRequest()
    try:
        result = _plan_service(db).skip_task(task_id, reason=payload.reason)
    except Exception as exc:
        _handle_plan_error(exc)
        raise
    db.commit()
    return result


@router.post("/task/{task_id}/modify")
def modify_task(
    task_id: str,
    payload: TaskModifyRequest,
    db: DbSession = Depends(_get_db_session),
) -> dict:
    try:
        result = _plan_service(db).modify_task(
            task_id,
            title=payload.title,
            description=payload.description,
            reason=payload.reason,
        )
    except Exception as exc:
        _handle_plan_error(exc)
        raise
    db.commit()
    return result


def _usage_query(db: DbSession, *, session_id: Optional[str] = None, since=None):
    query = db.query(TokenUsage)
    if session_id is not None:
        query = query.filter(TokenUsage.session_id == session_id)
    if since is not None:
        query = query.filter(TokenUsage.timestamp >= since)
    return query


def _usage_totals(db: DbSession, *, session_id: Optional[str] = None, since=None) -> dict:
    row = (
        _usage_query(db, session_id=session_id, since=since)
        .with_entities(
            func.coalesce(func.sum(TokenUsage.input_tokens), 0),
            func.coalesce(func.sum(TokenUsage.output_tokens), 0),
            func.coalesce(func.sum(TokenUsage.total_tokens), 0),
            func.coalesce(func.sum(TokenUsage.cost_usd), 0.0),
            func.count(TokenUsage.id),
        )
        .one()
    )
    total_tokens = int(row[2] or 0)
    return {
        "input_tokens": int(row[0] or 0),
        "output_tokens": int(row[1] or 0),
        "total_tokens": total_tokens,
        "tokens": total_tokens,
        "cost_usd": float(row[3] or 0.0),
        "calls": int(row[4] or 0),
    }


def _usage_by_agent(db: DbSession, *, session_id: Optional[str] = None, since=None) -> dict:
    rows = (
        _usage_query(db, session_id=session_id, since=since)
        .with_entities(
            TokenUsage.agent_type,
            func.coalesce(func.sum(TokenUsage.input_tokens), 0),
            func.coalesce(func.sum(TokenUsage.output_tokens), 0),
            func.coalesce(func.sum(TokenUsage.total_tokens), 0),
            func.coalesce(func.sum(TokenUsage.cost_usd), 0.0),
            func.count(TokenUsage.id),
        )
        .group_by(TokenUsage.agent_type)
        .all()
    )
    result = {}
    for agent_type, input_tokens, output_tokens, total_tokens, cost_usd, calls in rows:
        total = int(total_tokens or 0)
        result[agent_type or "unknown"] = {
            "input_tokens": int(input_tokens or 0),
            "output_tokens": int(output_tokens or 0),
            "total_tokens": total,
            "tokens": total,
            "cost_usd": float(cost_usd or 0.0),
            "calls": int(calls or 0),
        }
    return result


@router.get("/stats")
def get_stats(db: DbSession = Depends(_get_db_session)) -> dict:
    now = utcnow()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week = now - timedelta(days=7)
    total = _usage_totals(db)
    total["sessions"] = int(db.query(func.count(SessionModel.id)).scalar() or 0)
    total["pages"] = int(db.query(func.count(Page.id)).scalar() or 0)
    return {
        "today": _usage_totals(db, since=today),
        "week": _usage_totals(db, since=week),
        "total": total,
        "by_agent": _usage_by_agent(db),
    }


@router.get("/stats/session/{session_id}")
def get_session_stats(
    session_id: str,
    db: DbSession = Depends(_get_db_session),
) -> dict:
    session = db.get(SessionModel, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    totals = _usage_totals(db, session_id=session_id)
    timeline = [
        {
            "timestamp": row.timestamp,
            "agent_type": row.agent_type,
            "tokens": row.total_tokens,
            "cost_usd": row.cost_usd,
        }
        for row in (
            db.query(TokenUsage)
            .filter(TokenUsage.session_id == session_id)
            .order_by(TokenUsage.timestamp.asc())
            .all()
        )
    ]
    return {
        "session_id": session_id,
        "title": session.title,
        "created_at": session.created_at,
        "input_tokens": totals["input_tokens"],
        "output_tokens": totals["output_tokens"],
        "total_tokens": totals["total_tokens"],
        "tokens": totals["tokens"],
        "cost_usd": totals["cost_usd"],
        "calls": totals["calls"],
        "by_agent": _usage_by_agent(db, session_id=session_id),
        "timeline": timeline,
    }


@router.post("/session/{session_id}/abort")
def abort_session(
    session_id: str,
    db: DbSession = Depends(_get_db_session),
) -> dict:
    if db.get(SessionModel, session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")

    service = RunService(db)
    active_runs = (
        db.query(SessionRun)
        .filter(
            SessionRun.session_id == session_id,
            SessionRun.status.in_(["queued", "running", "waiting_input"]),
        )
        .order_by(SessionRun.updated_at.desc(), SessionRun.created_at.desc())
        .all()
    )

    aborted_ids: list[str] = []
    for run in active_runs:
        try:
            cancelled, accepted = service.cancel_run(run.id)
        except (RunNotFoundError, RunStateConflictError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if accepted:
            aborted_ids.append(cancelled.id)
            EventEmitter(
                session_id=cancelled.session_id,
                run_id=cancelled.id,
                event_store=EventStoreService(db),
            ).emit(
                run_lifecycle_event(
                    EventType.RUN_CANCELLED,
                    phase="done",
                    status=RunStatus.CANCELLED.value,
                )
            )

    db.commit()
    return {
        "success": True,
        "plan_ids": [],
        "completed_tasks": [],
        "aborted_tasks": aborted_ids,
        "run_ids": aborted_ids,
    }


__all__ = ["router"]
