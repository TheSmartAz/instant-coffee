from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .base import Base


class Session(Base):
    __tablename__ = "sessions"

    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    current_version = Column(Integer, default=0)

    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")
    versions = relationship("Version", back_populates="session", cascade="all, delete-orphan")
    token_usage = relationship("TokenUsage", back_populates="session", cascade="all, delete-orphan")
    plans = relationship("Plan", back_populates="session", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    session = relationship("Session", back_populates="messages")


class Version(Base):
    __tablename__ = "versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    version = Column(Integer, nullable=False)
    html = Column(Text, nullable=False)
    description = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("Session", back_populates="versions")

    __table_args__ = (UniqueConstraint("session_id", "version", name="uq_versions_session"),)


class TokenUsage(Base):
    __tablename__ = "token_usage"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    agent_type = Column(String, nullable=False)
    model = Column(String, nullable=False)
    input_tokens = Column(Integer, nullable=False)
    output_tokens = Column(Integer, nullable=False)
    total_tokens = Column(Integer, nullable=False)
    cost_usd = Column(Float, nullable=False)

    session = relationship("Session", back_populates="token_usage")


class PlanStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    FAILED = "failed"
    ABORTED = "aborted"


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    FAILED = "failed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"
    RETRYING = "retrying"
    ABORTED = "aborted"


class Plan(Base):
    __tablename__ = "plans"

    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)
    goal = Column(Text, nullable=False)
    status = Column(String, default=PlanStatus.PENDING.value)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    session = relationship("Session", back_populates="plans")
    tasks = relationship("Task", back_populates="plan", cascade="all, delete-orphan")
    events = relationship("PlanEvent", back_populates="plan", cascade="all, delete-orphan")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True)
    plan_id = Column(String, ForeignKey("plans.id"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text)
    agent_type = Column(String)
    status = Column(String, default=TaskStatus.PENDING.value)
    progress = Column(Integer, default=0)
    depends_on = Column(Text)
    can_parallel = Column(Boolean, default=True)
    retry_count = Column(Integer, default=0)
    error_message = Column(Text)
    result = Column(Text)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    plan = relationship("Plan", back_populates="tasks")
    events = relationship("TaskEvent", back_populates="task", cascade="all, delete-orphan")


class PlanEvent(Base):
    __tablename__ = "plan_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    plan_id = Column(String, ForeignKey("plans.id"), nullable=False)
    event_type = Column(String, nullable=False)
    message = Column(Text)
    payload = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)

    plan = relationship("Plan", back_populates="events")


class TaskEvent(Base):
    __tablename__ = "task_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, ForeignKey("tasks.id"), nullable=False)
    event_type = Column(String, nullable=False)
    agent_id = Column(String)
    agent_type = Column(String)
    agent_instance = Column(Integer)
    message = Column(Text)
    progress = Column(Integer)
    tool_name = Column(String)
    tool_input = Column(Text)
    tool_output = Column(Text)
    payload = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)

    task = relationship("Task", back_populates="events")


__all__ = [
    "Session",
    "Message",
    "Version",
    "TokenUsage",
    "Plan",
    "Task",
    "PlanEvent",
    "TaskEvent",
    "PlanStatus",
    "TaskStatus",
]
