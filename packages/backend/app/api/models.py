from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel


class TaskResponse(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    agent_type: Optional[str] = None
    status: str
    progress: int = 0
    depends_on: Optional[List[str]] = None
    can_parallel: bool = True
    retry_count: int = 0
    error_message: Optional[str] = None
    result: Optional[Any] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class PlanResponse(BaseModel):
    id: str
    session_id: str
    goal: str
    status: str
    tasks: List[TaskResponse]
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


__all__ = ["PlanResponse", "TaskResponse"]
