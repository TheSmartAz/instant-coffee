from __future__ import annotations

import uuid
from threading import Lock
from typing import Any, Optional

from sqlalchemy.orm import Session as DbSession

from ..utils.datetime import utcnow
from ..db.models import Session as SessionModel
from ..db.models import SessionRun


class RunNotFoundError(ValueError):
    pass


class RunStateConflictError(ValueError):
    pass


class RunCancelledError(RuntimeError):
    pass


class RunService:
    TERMINAL_STATES = {"completed", "failed", "cancelled"}
    ALLOWED_TRANSITIONS = {
        "queued": {"running", "cancelled"},
        "running": {"waiting_input", "completed", "failed", "cancelled"},
        "waiting_input": {"running", "cancelled"},
        "completed": set(),
        "failed": set(),
        "cancelled": set(),
    }
    _cancelled_runs: set[str] = set()
    _cancelled_guard = Lock()

    def __init__(self, db: DbSession) -> None:
        self.db = db

    def create_run(
        self,
        *,
        session_id: str,
        message: str,
        generate_now: bool = False,
        style_reference: Optional[dict[str, Any]] = None,
        target_pages: Optional[list[str]] = None,
        trigger_source: str = "chat",
        parent_run_id: Optional[str] = None,
        checkpoint_thread: Optional[str] = None,
        checkpoint_ns: Optional[str] = None,
    ) -> SessionRun:
        session = self.db.get(SessionModel, session_id)
        if session is None:
            raise ValueError("Session not found")

        run_id = uuid.uuid4().hex
        resolved_checkpoint_thread = checkpoint_thread or f"{session_id}:{run_id}"
        request_context = {
            "generate_now": bool(generate_now),
            "target_pages": list(target_pages or []),
        }
        if style_reference is not None:
            request_context["style_reference"] = style_reference

        run = SessionRun(
            id=run_id,
            session_id=session_id,
            parent_run_id=parent_run_id,
            trigger_source=trigger_source,
            status="queued",
            input_message=message,
            checkpoint_thread=resolved_checkpoint_thread,
            checkpoint_ns=checkpoint_ns,
            metrics=request_context,
        )
        self.db.add(run)
        self.db.flush([run])
        return run

    def get_run(self, run_id: str) -> SessionRun:
        run = self.db.get(SessionRun, run_id)
        if run is None:
            raise RunNotFoundError("Run not found")
        return run

    def list_runs(self, session_id: str) -> list[SessionRun]:
        return (
            self.db.query(SessionRun)
            .filter(SessionRun.session_id == session_id)
            .order_by(SessionRun.created_at.desc())
            .all()
        )

    def get_latest_waiting_run(self, session_id: str) -> Optional[SessionRun]:
        return (
            self.db.query(SessionRun)
            .filter(
                SessionRun.session_id == session_id,
                SessionRun.status == "waiting_input",
            )
            .order_by(SessionRun.updated_at.desc(), SessionRun.created_at.desc())
            .first()
        )

    def resolve_resume_run(
        self,
        *,
        session_id: str,
        run_id: Optional[str] = None,
    ) -> SessionRun:
        if run_id:
            run = self.get_run(run_id)
            if run.session_id != session_id:
                raise RunStateConflictError(f"Run {run_id} does not belong to session {session_id}")
            return run

        waiting = self.get_latest_waiting_run(session_id)
        if waiting is None:
            raise RunStateConflictError(
                f"No waiting_input run found for session {session_id}"
            )
        return waiting

    def start_run(self, run_id: str) -> SessionRun:
        self.clear_cancelled_marker(run_id)
        return self.persist_run_state(
            run_id,
            "running",
            started_at=utcnow(),
        )

    def resume_run(self, run_id: str, resume_payload: dict[str, Any]) -> SessionRun:
        run = self.get_run(run_id)
        if run.status != "waiting_input":
            raise RunStateConflictError(
                f"Run {run_id} is in state '{run.status}', expected 'waiting_input'"
            )
        self.clear_cancelled_marker(run_id)
        return self.persist_run_state(
            run_id,
            "running",
            resume_payload=resume_payload,
            started_at=run.started_at or utcnow(),
        )

    def cancel_run(self, run_id: str) -> tuple[SessionRun, bool]:
        run = self.get_run(run_id)
        if run.status in self.TERMINAL_STATES:
            if run.status == "cancelled":
                self.mark_cancelled(run_id)
            return run, False
        updated = self.persist_run_state(
            run_id,
            "cancelled",
            finished_at=run.finished_at or utcnow(),
        )
        self.mark_cancelled(run_id)
        return updated, True

    def persist_run_state(self, run_id: str, status: str, **kwargs: Any) -> SessionRun:
        run = self.get_run(run_id)
        current_status = run.status
        next_status = str(status)

        if next_status != current_status:
            allowed = self.ALLOWED_TRANSITIONS.get(current_status, set())
            if next_status not in allowed:
                raise RunStateConflictError(
                    f"Invalid transition {current_status} -> {next_status}"
                )
            run.status = next_status

        if next_status == "running" and run.started_at is None and "started_at" not in kwargs:
            kwargs["started_at"] = utcnow()
        if next_status in self.TERMINAL_STATES and run.finished_at is None and "finished_at" not in kwargs:
            kwargs["finished_at"] = utcnow()

        if next_status != "cancelled" and next_status in self.TERMINAL_STATES:
            self.clear_cancelled_marker(run_id)

        for key, value in kwargs.items():
            if hasattr(run, key):
                setattr(run, key, value)

        self.db.add(run)
        self.db.flush([run])
        return run

    @classmethod
    def mark_cancelled(cls, run_id: str) -> None:
        if not run_id:
            return
        with cls._cancelled_guard:
            cls._cancelled_runs.add(run_id)

    @classmethod
    def clear_cancelled_marker(cls, run_id: str) -> None:
        if not run_id:
            return
        with cls._cancelled_guard:
            cls._cancelled_runs.discard(run_id)

    @classmethod
    def is_cancelled(cls, run_id: str) -> bool:
        if not run_id:
            return False
        with cls._cancelled_guard:
            return run_id in cls._cancelled_runs


__all__ = [
    "RunService",
    "RunNotFoundError",
    "RunStateConflictError",
    "RunCancelledError",
]
