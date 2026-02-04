from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional
from uuid import uuid4
from enum import Enum

from sqlalchemy import func
from sqlalchemy.orm import Session as DbSession

from ..db.models import Plan, PlanStatus, Task, TaskStatus


def _serialize_json(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False)
    except TypeError:
        return json.dumps(str(value), ensure_ascii=False)


def _normalize_depends_on(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple, set)):
        return _serialize_json(list(value))
    return _serialize_json([str(value)])


def _normalize_status(value: Any, default: str) -> str:
    if value is None:
        return default
    if isinstance(value, Enum):
        return value.value
    return str(value)


class PlanService:
    """Service for managing execution plans."""

    def __init__(self, db: DbSession) -> None:
        self.db = db

    def create_plan(
        self,
        *,
        session_id: str,
        goal: str,
        tasks: Iterable[Dict[str, Any]],
        plan_id: Optional[str] = None,
    ) -> Plan:
        resolved_id = plan_id or uuid4().hex
        plan = Plan(
            id=resolved_id,
            session_id=session_id,
            goal=goal,
            status=PlanStatus.PENDING.value,
        )
        self.db.add(plan)
        self.db.flush()
        self._upsert_tasks(plan.id, tasks)
        self.recompute_status(plan.id)
        return plan

    def get_plan(self, plan_id: str) -> Optional[Plan]:
        return self.db.get(Plan, plan_id)

    def list_plans(self, session_id: str) -> List[Plan]:
        return (
            self.db.query(Plan)
            .filter(Plan.session_id == session_id)
            .order_by(Plan.created_at.asc())
            .all()
        )

    def upsert_plan_from_payload(
        self, payload: Dict[str, Any], *, session_id: Optional[str]
    ) -> Optional[Plan]:
        if not session_id:
            return None
        plan_id = payload.get("id") or payload.get("plan_id")
        if not plan_id:
            return None
        plan = self.db.get(Plan, plan_id)
        if plan is None:
            plan = Plan(
                id=plan_id,
                session_id=session_id,
                goal=str(payload.get("goal") or ""),
                status=PlanStatus.PENDING.value,
            )
            self.db.add(plan)
        else:
            goal = payload.get("goal")
            if goal:
                plan.goal = str(goal)
        self.db.flush()
        tasks = payload.get("tasks") or []
        if isinstance(tasks, list):
            self._upsert_tasks(plan.id, tasks)
        self.recompute_status(plan.id)
        return plan

    def recompute_status(self, plan_id: str) -> Optional[Plan]:
        plan = self.db.get(Plan, plan_id)
        if plan is None:
            return None
        rows = (
            self.db.query(Task.status, func.count(Task.id))
            .filter(Task.plan_id == plan_id)
            .group_by(Task.status)
            .all()
        )
        if not rows:
            return plan
        statuses = {row[0] for row in rows}
        if TaskStatus.ABORTED.value in statuses:
            plan.status = PlanStatus.ABORTED.value
        elif TaskStatus.FAILED.value in statuses or TaskStatus.TIMEOUT.value in statuses:
            plan.status = PlanStatus.FAILED.value
        elif TaskStatus.IN_PROGRESS.value in statuses or TaskStatus.RETRYING.value in statuses:
            plan.status = PlanStatus.IN_PROGRESS.value
        elif TaskStatus.BLOCKED.value in statuses:
            plan.status = PlanStatus.IN_PROGRESS.value
        elif statuses.issubset({TaskStatus.DONE.value, TaskStatus.SKIPPED.value}):
            plan.status = PlanStatus.DONE.value
        else:
            plan.status = PlanStatus.PENDING.value
        plan.updated_at = datetime.utcnow()
        self.db.add(plan)
        return plan

    def _upsert_tasks(self, plan_id: str, tasks: Iterable[Dict[str, Any]]) -> None:
        for task_payload in tasks:
            if not isinstance(task_payload, dict):
                continue
            task_id = task_payload.get("id")
            if not task_id:
                continue
            record = self.db.get(Task, task_id)
            depends_on = _normalize_depends_on(task_payload.get("depends_on"))
            result = _serialize_json(task_payload.get("result"))
            if record is None:
                record = Task(
                    id=task_id,
                    plan_id=plan_id,
                    title=str(task_payload.get("title") or ""),
                    description=task_payload.get("description"),
                    agent_type=task_payload.get("agent_type"),
                    status=_normalize_status(
                        task_payload.get("status"), TaskStatus.PENDING.value
                    ),
                    progress=int(task_payload.get("progress") or 0),
                    depends_on=depends_on,
                    can_parallel=bool(task_payload.get("can_parallel", True)),
                    retry_count=int(task_payload.get("retry_count") or 0),
                    error_message=task_payload.get("error_message"),
                    result=result,
                    started_at=task_payload.get("started_at"),
                    completed_at=task_payload.get("completed_at"),
                )
                self.db.add(record)
                continue

            record.plan_id = plan_id
            if task_payload.get("title"):
                record.title = str(task_payload.get("title"))
            if "description" in task_payload:
                record.description = task_payload.get("description")
            if "agent_type" in task_payload:
                record.agent_type = task_payload.get("agent_type")
            if "status" in task_payload:
                record.status = _normalize_status(
                    task_payload.get("status"), record.status
                )
            if "progress" in task_payload:
                record.progress = int(task_payload.get("progress") or 0)
            if "depends_on" in task_payload:
                record.depends_on = depends_on
            if "can_parallel" in task_payload:
                record.can_parallel = bool(task_payload.get("can_parallel", True))
            if "retry_count" in task_payload:
                record.retry_count = int(task_payload.get("retry_count") or 0)
            if "error_message" in task_payload:
                record.error_message = task_payload.get("error_message")
            if "result" in task_payload:
                record.result = result
            if "started_at" in task_payload:
                record.started_at = task_payload.get("started_at")
            if "completed_at" in task_payload:
                record.completed_at = task_payload.get("completed_at")
            self.db.add(record)


__all__ = ["PlanService"]
