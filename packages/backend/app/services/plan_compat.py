from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy.orm import Session as DbSession

from ..db.models import Session as SessionModel, SessionEvent
from ..events.types import EventType
from ..services.event_store import EventStoreService


class PlanCompatNotFoundError(ValueError):
    pass


class PlanCompatConflictError(ValueError):
    pass


VALID_TASK_STATUSES = {
    "pending",
    "in_progress",
    "done",
    "failed",
    "aborted",
    "timeout",
    "blocked",
    "skipped",
    "retrying",
}

TASK_EVENT_STATUS = {
    EventType.TASK_STARTED.value: "in_progress",
    EventType.TASK_DONE.value: "done",
    EventType.TASK_COMPLETED.value: "done",
    EventType.TASK_FAILED.value: "failed",
    EventType.TASK_ABORTED.value: "aborted",
    EventType.TASK_RETRYING.value: "retrying",
    EventType.TASK_SKIPPED.value: "skipped",
    EventType.TASK_BLOCKED.value: "blocked",
}


@dataclass
class PlanSnapshot:
    session_id: str
    created_seq: int
    plan: dict[str, Any]


def _payload(event: SessionEvent) -> dict[str, Any]:
    payload = event.payload or {}
    return payload if isinstance(payload, dict) else {"value": payload}


def _normalize_status(value: Any, default: str = "pending") -> str:
    status = str(value or default)
    return status if status in VALID_TASK_STATUSES else default


def _normalize_task(raw: dict[str, Any], *, plan_id: str, index: int) -> dict[str, Any]:
    task_id = str(raw.get("id") or f"{plan_id}-task-{index + 1}")
    title = str(raw.get("title") or raw.get("name") or f"Task {index + 1}")
    depends_on = raw.get("depends_on") or raw.get("dependsOn") or []
    if not isinstance(depends_on, list):
        depends_on = []
    retry_count = raw.get("retry_count") or raw.get("retryCount") or 0
    try:
        retry_count = int(retry_count)
    except (TypeError, ValueError):
        retry_count = 0
    progress = raw.get("progress", 0)
    try:
        progress = int(progress)
    except (TypeError, ValueError):
        progress = 0
    progress = min(max(progress, 0), 100)

    task = {
        "id": task_id,
        "title": title,
        "description": raw.get("description"),
        "depends_on": [str(item) for item in depends_on],
        "can_parallel": bool(raw.get("can_parallel") or raw.get("canParallel")),
        "status": _normalize_status(raw.get("status")),
        "agent_type": raw.get("agent_type"),
        "progress": progress,
        "retry_count": retry_count,
    }
    if raw.get("error_message") is not None:
        task["error_message"] = str(raw["error_message"])
    if raw.get("summary") is not None:
        task["summary"] = str(raw["summary"])
    return task


def _default_tasks(plan_id: str, message: Optional[str], target_pages: list[str]) -> list[dict[str, Any]]:
    page_label = ", ".join(target_pages) if target_pages else "requested mobile pages"
    implement_id = f"{plan_id}-implement"
    build_id = f"{plan_id}-build"
    return [
        _normalize_task(
            {
                "id": implement_id,
                "title": "Generate requested page changes",
                "description": message or f"Implement {page_label}.",
                "agent_type": "generation",
                "can_parallel": False,
            },
            plan_id=plan_id,
            index=0,
        ),
        _normalize_task(
            {
                "id": build_id,
                "title": "Build preview artifacts",
                "description": f"Build {page_label} into previewable HTML.",
                "agent_type": "build",
                "depends_on": [implement_id],
            },
            plan_id=plan_id,
            index=1,
        ),
        _normalize_task(
            {
                "id": f"{plan_id}-review",
                "title": "Review generated output",
                "description": "Check output completeness and obvious rendering risks.",
                "agent_type": "review",
                "depends_on": [build_id],
            },
            plan_id=plan_id,
            index=2,
        ),
    ]


def _plan_from_payload(payload: dict[str, Any]) -> Optional[dict[str, Any]]:
    candidate = payload.get("plan") if isinstance(payload.get("plan"), dict) else payload
    if not isinstance(candidate, dict):
        return None
    if candidate.get("id") is None and payload.get("plan_id") is None:
        return None
    plan = copy.deepcopy(candidate)
    if plan.get("id") is None:
        plan["id"] = str(payload["plan_id"])
    if "tasks" not in plan or not isinstance(plan["tasks"], list):
        plan["tasks"] = []
    return plan


def _plan_id_from_payload(payload: dict[str, Any]) -> Optional[str]:
    if payload.get("plan_id") is not None:
        return str(payload["plan_id"])
    plan = payload.get("plan")
    if isinstance(plan, dict) and plan.get("id") is not None:
        return str(plan["id"])
    if payload.get("id") is not None and isinstance(payload.get("tasks"), list):
        return str(payload["id"])
    return None


def _derive_plan_status(tasks: list[dict[str, Any]]) -> str:
    if not tasks:
        return "pending"
    statuses = [str(task.get("status") or "pending") for task in tasks]
    if any(status in {"failed", "timeout"} for status in statuses):
        return "failed"
    if all(status == "aborted" for status in statuses):
        return "aborted"
    if any(status in {"in_progress", "retrying", "blocked"} for status in statuses):
        return "in_progress"
    if all(status in {"done", "skipped", "aborted"} for status in statuses):
        return "done"
    if all(status == "pending" for status in statuses):
        return "pending"
    return "in_progress"


class PlanCompatService:
    """Event-store-backed compatibility for the old plan/task API surface."""

    def __init__(self, db: DbSession) -> None:
        self.db = db
        self.event_store = EventStoreService(db)

    def create_plan(
        self,
        *,
        session_id: str,
        message: Optional[str] = None,
        goal: Optional[str] = None,
        context: Any = None,
        tasks: Optional[list[dict[str, Any]]] = None,
        target_pages: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        if self.db.get(SessionModel, session_id) is None:
            raise PlanCompatNotFoundError("Session not found")

        plan_id = uuid.uuid4().hex
        resolved_target_pages = [str(page) for page in (target_pages or [])]
        normalized_tasks = (
            [
                _normalize_task(task, plan_id=plan_id, index=index)
                for index, task in enumerate(tasks or [])
            ]
            if tasks
            else _default_tasks(plan_id, message, resolved_target_pages)
        )
        plan = {
            "id": plan_id,
            "goal": goal or message or "Generate a mobile-first page",
            "tasks": normalized_tasks,
            "status": _derive_plan_status(normalized_tasks),
        }
        payload = {
            "session_id": session_id,
            "plan_id": plan_id,
            "plan": plan,
            "context": context,
        }
        seq = self.event_store.store_event(
            session_id,
            EventType.PLAN_CREATED.value,
            payload,
            "plan",
        )
        return {**plan, "session_id": session_id, "seq": seq}

    def get_plan_status(self, plan_id: str) -> dict[str, Any]:
        return self._build_snapshot(self._find_plan_event(plan_id)).plan

    def get_task_status(self, task_id: str) -> dict[str, Any]:
        _snapshot, task = self._find_task(task_id)
        return dict(task)

    def retry_task(
        self,
        task_id: str,
        *,
        reason: Optional[str] = None,
        max_attempts: int = 3,
    ) -> dict[str, Any]:
        snapshot, task = self._find_task(task_id)
        old_status = str(task.get("status") or "pending")
        if old_status in {"in_progress", "retrying"}:
            raise PlanCompatConflictError(f"Task {task_id} is already {old_status}")
        if old_status == "done":
            raise PlanCompatConflictError(f"Task {task_id} is already done")

        attempt = int(task.get("retry_count") or 0) + 1
        changes = [
            {
                "task_id": task_id,
                "field": "status",
                "old_value": old_status,
                "new_value": "retrying",
            },
            {
                "task_id": task_id,
                "field": "retry_count",
                "old_value": int(task.get("retry_count") or 0),
                "new_value": attempt,
            },
        ]
        self._store_plan_updated(snapshot, changes)
        self.event_store.store_event(
            snapshot.session_id,
            EventType.TASK_RETRYING.value,
            {
                "plan_id": snapshot.plan["id"],
                "task_id": task_id,
                "attempt": attempt,
                "max_attempts": max_attempts,
                "next_retry_in": 0,
                "reason": reason,
            },
            "task",
        )
        return {
            "success": True,
            "plan_id": snapshot.plan["id"],
            "task_id": task_id,
            "status": "retrying",
            "attempt": attempt,
            "max_attempts": max_attempts,
            "scheduled": False,
        }

    def skip_task(self, task_id: str, *, reason: Optional[str] = None) -> dict[str, Any]:
        snapshot, task = self._find_task(task_id)
        old_status = str(task.get("status") or "pending")
        if old_status == "done":
            raise PlanCompatConflictError(f"Task {task_id} is already done")
        if old_status == "skipped":
            return {
                "success": True,
                "plan_id": snapshot.plan["id"],
                "task_id": task_id,
                "status": "skipped",
                "changed": False,
            }

        self._store_plan_updated(
            snapshot,
            [
                {
                    "task_id": task_id,
                    "field": "status",
                    "old_value": old_status,
                    "new_value": "skipped",
                },
                {
                    "task_id": task_id,
                    "field": "progress",
                    "old_value": int(task.get("progress") or 0),
                    "new_value": 100,
                },
            ],
        )
        self.event_store.store_event(
            snapshot.session_id,
            EventType.TASK_SKIPPED.value,
            {
                "plan_id": snapshot.plan["id"],
                "task_id": task_id,
                "reason": reason,
            },
            "task",
        )
        return {
            "success": True,
            "plan_id": snapshot.plan["id"],
            "task_id": task_id,
            "status": "skipped",
            "changed": True,
        }

    def modify_task(
        self,
        task_id: str,
        *,
        title: Optional[str] = None,
        description: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> dict[str, Any]:
        snapshot, task = self._find_task(task_id)
        changes: list[dict[str, Any]] = []
        if title is not None and title != task.get("title"):
            changes.append(
                {
                    "task_id": task_id,
                    "field": "title",
                    "old_value": task.get("title"),
                    "new_value": title,
                }
            )
        if description is not None and description != task.get("description"):
            changes.append(
                {
                    "task_id": task_id,
                    "field": "description",
                    "old_value": task.get("description"),
                    "new_value": description,
                }
            )
        if changes:
            self._store_plan_updated(snapshot, changes)
        retry = self.retry_task(task_id, reason=reason or "modified")
        return {**retry, "modified": bool(changes)}

    def _store_plan_updated(
        self,
        snapshot: PlanSnapshot,
        changes: list[dict[str, Any]],
    ) -> None:
        self.event_store.store_event(
            snapshot.session_id,
            EventType.PLAN_UPDATED.value,
            {
                "plan_id": snapshot.plan["id"],
                "changes": changes,
            },
            "plan",
        )

    def _find_plan_event(self, plan_id: str) -> SessionEvent:
        events = (
            self.db.query(SessionEvent)
            .filter(SessionEvent.type == EventType.PLAN_CREATED.value)
            .order_by(SessionEvent.created_at.desc(), SessionEvent.seq.desc())
            .all()
        )
        for event in events:
            if _plan_id_from_payload(_payload(event)) == plan_id:
                return event
        raise PlanCompatNotFoundError("Plan not found")

    def _find_task(self, task_id: str) -> tuple[PlanSnapshot, dict[str, Any]]:
        events = (
            self.db.query(SessionEvent)
            .filter(SessionEvent.type == EventType.PLAN_CREATED.value)
            .order_by(SessionEvent.created_at.desc(), SessionEvent.seq.desc())
            .all()
        )
        for event in events:
            snapshot = self._build_snapshot(event)
            for task in snapshot.plan.get("tasks", []):
                if task.get("id") == task_id:
                    return snapshot, task
        raise PlanCompatNotFoundError("Task not found")

    def _build_snapshot(self, created_event: SessionEvent) -> PlanSnapshot:
        payload = _payload(created_event)
        plan = _plan_from_payload(payload)
        if plan is None:
            raise PlanCompatNotFoundError("Plan not found")
        plan_id = str(plan["id"])
        tasks = [
            _normalize_task(task, plan_id=plan_id, index=index)
            for index, task in enumerate(plan.get("tasks", []))
            if isinstance(task, dict)
        ]
        tasks_by_id = {task["id"]: task for task in tasks}

        events = (
            self.db.query(SessionEvent)
            .filter(
                SessionEvent.session_id == created_event.session_id,
                SessionEvent.seq > created_event.seq,
            )
            .order_by(SessionEvent.seq.asc())
            .all()
        )
        for event in events:
            event_payload = _payload(event)
            if _plan_id_from_payload(event_payload) not in {None, plan_id}:
                continue
            if event.type == EventType.PLAN_UPDATED.value:
                self._apply_plan_updated(tasks_by_id, event_payload)
            elif event.type in TASK_EVENT_STATUS:
                self._apply_task_event(tasks_by_id, event.type, event_payload)

        plan["tasks"] = list(tasks_by_id.values())
        plan["status"] = _derive_plan_status(plan["tasks"])
        return PlanSnapshot(
            session_id=created_event.session_id,
            created_seq=created_event.seq,
            plan=plan,
        )

    def _apply_plan_updated(
        self,
        tasks_by_id: dict[str, dict[str, Any]],
        payload: dict[str, Any],
    ) -> None:
        changes = payload.get("changes")
        if not isinstance(changes, list):
            return
        for change in changes:
            if not isinstance(change, dict):
                continue
            task_id = change.get("task_id")
            field = change.get("field")
            if task_id not in tasks_by_id or not isinstance(field, str):
                continue
            tasks_by_id[task_id][field] = change.get("new_value")
            if field == "status":
                tasks_by_id[task_id][field] = _normalize_status(change.get("new_value"))

    def _apply_task_event(
        self,
        tasks_by_id: dict[str, dict[str, Any]],
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        task_id = payload.get("task_id")
        if task_id not in tasks_by_id:
            return
        task = tasks_by_id[task_id]
        task["status"] = TASK_EVENT_STATUS[event_type]
        if event_type in {EventType.TASK_DONE.value, EventType.TASK_COMPLETED.value}:
            task["progress"] = 100
            result = payload.get("result")
            if isinstance(result, dict) and result.get("summary") is not None:
                task["summary"] = str(result["summary"])
        elif event_type == EventType.TASK_FAILED.value:
            task["error_message"] = str(payload.get("error_message") or "")
            task["retry_count"] = int(payload.get("retry_count") or task.get("retry_count") or 0)
        elif event_type == EventType.TASK_RETRYING.value:
            task["retry_count"] = int(payload.get("attempt") or task.get("retry_count") or 0)
            task["progress"] = 0
        elif event_type == EventType.TASK_SKIPPED.value:
            task["progress"] = 100


__all__ = [
    "PlanCompatConflictError",
    "PlanCompatNotFoundError",
    "PlanCompatService",
]
