from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from sqlalchemy.orm import Session as DbSession

from ..db.models import Plan, PlanEvent, Task, TaskEvent
from ..events.models import BaseEvent, PlanCreatedEvent, PlanUpdatedEvent
from .plan import PlanService

logger = logging.getLogger(__name__)


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, Enum):
        return value.value
    return str(value)


def _safe_json_dumps(value: Any) -> Optional[str]:
    if value is None:
        return None
    try:
        return json.dumps(value, ensure_ascii=False, default=_json_default)
    except TypeError:
        return json.dumps(str(value), ensure_ascii=False)


class EventStoreService:
    """Persist emitted events into plan/task event tables."""

    def __init__(self, db: DbSession) -> None:
        self.db = db
        self._plan_service = PlanService(db)

    def record_event(self, event: BaseEvent) -> None:
        event_type = getattr(event.type, "value", event.type)
        payload = event.model_dump()
        timestamp = event.timestamp or datetime.now(timezone.utc)
        if isinstance(event, PlanCreatedEvent):
            plan_payload = payload.get("plan") or {}
            plan = self._plan_service.upsert_plan_from_payload(
                plan_payload, session_id=event.session_id
            )
            if plan is None:
                return
            plan_event = PlanEvent(
                plan_id=plan.id,
                event_type=event_type,
                message=payload.get("message"),
                payload=_safe_json_dumps(payload),
                timestamp=timestamp,
            )
            self.db.add(plan_event)
            return

        if isinstance(event, PlanUpdatedEvent):
            plan_id = payload.get("plan_id")
            if not plan_id:
                return
            if self.db.get(Plan, plan_id) is None:
                return
            plan_event = PlanEvent(
                plan_id=plan_id,
                event_type=event_type,
                message=payload.get("message"),
                payload=_safe_json_dumps(payload),
                timestamp=timestamp,
            )
            self.db.add(plan_event)
            return

        task_id = payload.get("task_id")
        if not task_id:
            return
        task = self.db.get(Task, task_id)
        if task is None:
            logger.debug("Skipping event for unknown task_id=%s", task_id)
            return
        task_event = TaskEvent(
            task_id=task_id,
            event_type=event_type,
            agent_id=payload.get("agent_id"),
            agent_type=payload.get("agent_type"),
            agent_instance=payload.get("agent_instance"),
            message=payload.get("message") or payload.get("summary"),
            progress=payload.get("progress"),
            tool_name=payload.get("tool_name"),
            tool_input=_safe_json_dumps(payload.get("tool_input")),
            tool_output=_safe_json_dumps(payload.get("tool_output")),
            payload=_safe_json_dumps(payload),
            timestamp=timestamp,
        )
        self.db.add(task_event)


__all__ = ["EventStoreService"]
