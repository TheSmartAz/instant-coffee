from __future__ import annotations

import enum
import re
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship, validates

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
    product_doc = relationship(
        "ProductDoc",
        back_populates="session",
        uselist=False,
        cascade="all, delete-orphan",
    )
    pages = relationship("Page", back_populates="session", cascade="all, delete-orphan")
    snapshots = relationship(
        "ProjectSnapshot",
        back_populates="session",
        cascade="all, delete-orphan",
    )
    session_events = relationship(
        "SessionEvent",
        back_populates="session",
        cascade="all, delete-orphan",
    )


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
    TIMEOUT = "timeout"


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


class ProductDocStatus(str, enum.Enum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    OUTDATED = "outdated"


class VersionSource(str, enum.Enum):
    AUTO = "auto"
    MANUAL = "manual"
    ROLLBACK = "rollback"


class SessionEventSource(str, enum.Enum):
    SESSION = "session"
    PLAN = "plan"
    TASK = "task"


def _enum_values(enum_cls: type[enum.Enum]) -> list[str]:
    return [member.value for member in enum_cls]


class ProductDoc(Base):
    __tablename__ = "product_docs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(
        String,
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    content = Column(Text, nullable=False, default="")
    structured = Column(JSON, nullable=False, default=dict)
    version = Column(Integer, nullable=False, default=1)
    status = Column(
        SAEnum(ProductDocStatus, name="product_doc_status"),
        nullable=False,
        default=ProductDocStatus.DRAFT,
    )
    pending_regeneration_pages = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    session = relationship("Session", back_populates="product_doc")
    histories = relationship(
        "ProductDocHistory",
        back_populates="product_doc",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_product_docs_session_id", "session_id"),
        UniqueConstraint(
            "session_id",
            "version",
            name="uq_product_docs_session_version",
        ),
    )


class ProductDocHistory(Base):
    __tablename__ = "product_doc_histories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_doc_id = Column(
        String,
        ForeignKey("product_docs.id", ondelete="CASCADE"),
        nullable=False,
    )
    version = Column(Integer, nullable=False)
    content = Column(Text)
    structured = Column(JSON)
    change_summary = Column(Text)
    source = Column(
        SAEnum(VersionSource, name="version_source", values_callable=_enum_values),
        nullable=False,
        default=VersionSource.AUTO,
    )
    is_pinned = Column(Boolean, nullable=False, default=False)
    is_released = Column(Boolean, nullable=False, default=False)
    released_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    product_doc = relationship("ProductDoc", back_populates="histories")

    __table_args__ = (
        UniqueConstraint(
            "product_doc_id",
            "version",
            name="uq_product_doc_histories_doc_version",
        ),
        Index("idx_product_doc_histories_created_at", "created_at"),
    )


class ProjectSnapshot(Base):
    __tablename__ = "project_snapshots"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    snapshot_number = Column(Integer, nullable=False)
    label = Column(String(255))
    source = Column(
        SAEnum(VersionSource, name="version_source", values_callable=_enum_values),
        nullable=False,
        default=VersionSource.AUTO,
    )
    is_pinned = Column(Boolean, nullable=False, default=False)
    is_released = Column(Boolean, nullable=False, default=False)
    released_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("Session", back_populates="snapshots")
    doc = relationship(
        "ProjectSnapshotDoc",
        back_populates="snapshot",
        cascade="all, delete-orphan",
        uselist=False,
    )
    pages = relationship(
        "ProjectSnapshotPage",
        back_populates="snapshot",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "snapshot_number",
            name="uq_project_snapshots_session_number",
        ),
    )


class ProjectSnapshotDoc(Base):
    __tablename__ = "project_snapshot_docs"

    snapshot_id = Column(
        String,
        ForeignKey("project_snapshots.id", ondelete="CASCADE"),
        primary_key=True,
    )
    content = Column(Text)
    structured = Column(JSON)
    global_style = Column(JSON)
    design_direction = Column(JSON)
    product_doc_version = Column(Integer)

    snapshot = relationship("ProjectSnapshot", back_populates="doc")


class ProjectSnapshotPage(Base):
    __tablename__ = "project_snapshot_pages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_id = Column(
        String,
        ForeignKey("project_snapshots.id", ondelete="CASCADE"),
        nullable=False,
    )
    page_id = Column(String, ForeignKey("pages.id"), nullable=False)
    slug = Column(String(255), nullable=False)
    title = Column(String(255), nullable=False)
    order_index = Column(Integer, nullable=False)
    rendered_html = Column(Text)

    snapshot = relationship("ProjectSnapshot", back_populates="pages")

    __table_args__ = (Index("idx_snapshot_page", "snapshot_id", "page_id"),)


class Page(Base):
    __tablename__ = "pages"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False)
    slug = Column(String(40), nullable=False)
    description = Column(Text, nullable=False, default="")
    order_index = Column(Integer, nullable=False, default=0)
    current_version_id = Column(Integer, ForeignKey("page_versions.id", ondelete="SET NULL"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    session = relationship("Session", back_populates="pages")
    versions = relationship(
        "PageVersion",
        back_populates="page",
        cascade="all, delete-orphan",
        foreign_keys="PageVersion.page_id",
    )
    current_version = relationship(
        "PageVersion",
        foreign_keys=[current_version_id],
        post_update=True,
    )

    __table_args__ = (
        UniqueConstraint("session_id", "slug", name="uq_pages_session_slug"),
        Index("idx_pages_session_id", "session_id"),
        Index("idx_pages_slug", "session_id", "slug"),
    )

    @validates("slug")
    def validate_slug(self, _key: str, value: str) -> str:
        if value is None:
            raise ValueError("slug is required")
        if len(value) > 40:
            raise ValueError("slug must be 40 characters or fewer")
        if re.fullmatch(r"[a-z0-9-]+", value) is None:
            raise ValueError("slug must match pattern [a-z0-9-]+")
        return value


class PageVersion(Base):
    __tablename__ = "page_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    page_id = Column(String, ForeignKey("pages.id", ondelete="CASCADE"), nullable=False)
    version = Column(Integer, nullable=False)
    html = Column(Text)
    description = Column(String(500))
    source = Column(
        SAEnum(VersionSource, name="version_source", values_callable=_enum_values),
        nullable=False,
        default=VersionSource.AUTO,
    )
    is_pinned = Column(Boolean, nullable=False, default=False)
    is_released = Column(Boolean, nullable=False, default=False)
    released_at = Column(DateTime)
    payload_pruned_at = Column(DateTime)
    fallback_used = Column(Boolean, nullable=False, default=False)
    fallback_excerpt = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    page = relationship("Page", back_populates="versions", foreign_keys=[page_id])

    __table_args__ = (
        UniqueConstraint("page_id", "version", name="uq_page_versions_page_version"),
        Index("idx_page_versions_page_id", "page_id"),
    )


class SessionEvent(Base):
    __tablename__ = "session_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    seq = Column(Integer, nullable=False)
    type = Column(String(100), nullable=False)
    payload = Column(JSON)
    source = Column(
        SAEnum(SessionEventSource, name="session_event_source", values_callable=_enum_values),
        nullable=False,
    )
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("Session", back_populates="session_events")

    __table_args__ = (Index("idx_session_event_seq", "session_id", "seq"),)


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
    "ProductDocStatus",
    "VersionSource",
    "SessionEventSource",
    "ProductDoc",
    "ProductDocHistory",
    "ProjectSnapshot",
    "ProjectSnapshotDoc",
    "ProjectSnapshotPage",
    "Page",
    "PageVersion",
    "SessionEvent",
]
