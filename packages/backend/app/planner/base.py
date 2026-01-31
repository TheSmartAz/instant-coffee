from __future__ import annotations

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class PlannerError(RuntimeError):
    pass


class PlannerAPIError(PlannerError):
    pass


class PlannerRateLimitError(PlannerAPIError):
    pass


class PlannerResponseError(PlannerError):
    pass


class TaskPlan(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    agent_type: str
    depends_on: List[str] = Field(default_factory=list)
    can_parallel: bool = True


class Plan(BaseModel):
    id: str
    goal: str
    tasks: List[TaskPlan]


class BasePlanner(ABC):
    max_retries: int = 3
    base_backoff_seconds: float = 1.0

    @abstractmethod
    async def plan(self, user_message: str, context: Optional[str] = None) -> Plan:
        """Generate execution plan from user message."""
        raise NotImplementedError

    async def _backoff(self, attempt: int, reason: str) -> None:
        delay = self.base_backoff_seconds * (2 ** (attempt - 1))
        logger.warning("Planner retry after %s (attempt %s/%s)", reason, attempt, self.max_retries)
        await asyncio.sleep(delay)

    def _extract_json(self, raw: str) -> Dict[str, Any]:
        if not raw:
            return {}
        raw = raw.strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        fenced = self._extract_fenced_json(raw)
        if fenced:
            try:
                return json.loads(fenced)
            except json.JSONDecodeError:
                pass

        json_block = self._extract_json_block(raw)
        if json_block:
            try:
                return json.loads(json_block)
            except json.JSONDecodeError:
                pass

        logger.warning("Planner failed to parse JSON response")
        return {}

    def _extract_fenced_json(self, raw: str) -> Optional[str]:
        marker = "```"
        if marker not in raw:
            return None
        parts = raw.split(marker)
        for i in range(1, len(parts), 2):
            candidate = parts[i].strip()
            if candidate.startswith("json"):
                candidate = candidate[4:].strip()
            if candidate.startswith("{") and candidate.endswith("}"):
                return candidate
        return None

    def _extract_json_block(self, raw: str) -> Optional[str]:
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        return raw[start : end + 1]

    def _build_plan(self, data: Dict[str, Any], user_message: str) -> Plan:
        if not isinstance(data, dict):
            raise PlannerResponseError("Planner response is not a JSON object")
        plan_id = uuid4().hex
        goal = str(data.get("goal") or user_message).strip() or user_message
        tasks_payload = data.get("tasks")
        if not isinstance(tasks_payload, list):
            tasks_payload = []

        normalized_tasks: List[Dict[str, Any]] = []
        seen_raw_ids: set[str] = set()
        for idx, raw_task in enumerate(tasks_payload):
            if not isinstance(raw_task, dict):
                continue
            raw_id = str(raw_task.get("id") or f"task_{idx + 1}").strip()
            if not raw_id:
                raw_id = f"task_{idx + 1}"
            original_id = raw_id
            counter = 1
            while raw_id in seen_raw_ids:
                counter += 1
                raw_id = f"{original_id}_{counter}"
            seen_raw_ids.add(raw_id)

            title = str(raw_task.get("title") or "").strip() or f"Task {idx + 1}"
            description = raw_task.get("description")
            agent_type = str(raw_task.get("agent_type") or "Generation")
            depends_on = raw_task.get("depends_on") or []
            if isinstance(depends_on, str):
                depends_on = [depends_on]
            elif not isinstance(depends_on, list):
                depends_on = [str(depends_on)]
            depends_on_list = [str(dep).strip() for dep in depends_on if dep]
            can_parallel = bool(raw_task.get("can_parallel", True))

            normalized_tasks.append(
                {
                    "raw_id": raw_id,
                    "title": title,
                    "description": description,
                    "agent_type": agent_type,
                    "depends_on": depends_on_list,
                    "can_parallel": can_parallel,
                }
            )

        if not normalized_tasks:
            raise PlannerResponseError("Planner returned no tasks")

        if len(normalized_tasks) > 20:
            normalized_tasks = normalized_tasks[:20]

        id_map = {
            task["raw_id"]: f"{plan_id}_task_{index + 1}"
            for index, task in enumerate(normalized_tasks)
        }
        tasks: List[TaskPlan] = []
        for task_data in normalized_tasks:
            task_id = id_map[task_data["raw_id"]]
            depends_on = [
                id_map[dep]
                for dep in task_data["depends_on"]
                if dep in id_map and id_map[dep] != task_id
            ]
            tasks.append(
                TaskPlan(
                    id=task_id,
                    title=task_data["title"],
                    description=task_data["description"],
                    agent_type=task_data["agent_type"],
                    depends_on=depends_on,
                    can_parallel=task_data["can_parallel"],
                )
            )

        return Plan(id=plan_id, goal=goal, tasks=tasks)


__all__ = [
    "BasePlanner",
    "Plan",
    "TaskPlan",
    "PlannerError",
    "PlannerAPIError",
    "PlannerRateLimitError",
    "PlannerResponseError",
]
