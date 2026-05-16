from __future__ import annotations

import uuid
from datetime import timedelta
from threading import Lock
from typing import Any, Optional

from sqlalchemy.orm import Session as DbSession
from sqlalchemy.exc import IntegrityError

from ..utils.datetime import utcnow
from ..db.models import Session as SessionModel
from ..db.models import SessionRun
from ..schemas.run import RunPhase, RunStatus, normalize_execution_mode


class RunNotFoundError(ValueError):
    pass


class RunStateConflictError(ValueError):
    pass


class RunCancelledError(RuntimeError):
    pass


class RunService:
    TERMINAL_STATES = {"completed", "failed", "cancelled"}
    ACTIVE_STATES = {"queued", "running"}
    ALLOWED_TRANSITIONS = {
        "queued": {"running", "failed", "cancelled"},
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
        execution_mode: Optional[str] = None,
        approval_mode: str = "agent",
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
        normalized_execution_mode = normalize_execution_mode(
            execution_mode if execution_mode is not None else approval_mode
        )
        request_context = {
            "generate_now": bool(generate_now),
            "execution_mode": normalized_execution_mode,
            "approval_mode": normalized_execution_mode,
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
        try:
            self.db.flush([run])
        except IntegrityError as exc:
            self.db.rollback()
            raise RunStateConflictError(
                f"Run already active for session {session_id}"
            ) from exc
        return run

    @staticmethod
    def normalize_phase(phase: RunPhase | str) -> str:
        try:
            return phase.value if isinstance(phase, RunPhase) else RunPhase(str(phase)).value
        except ValueError as exc:
            allowed = ", ".join(item.value for item in RunPhase)
            raise ValueError(f"phase must be one of: {allowed}") from exc

    @staticmethod
    def normalize_status(status: RunStatus | str) -> str:
        try:
            return status.value if isinstance(status, RunStatus) else RunStatus(str(status)).value
        except ValueError as exc:
            allowed = ", ".join(item.value for item in RunStatus)
            raise ValueError(f"status must be one of: {allowed}") from exc

    @classmethod
    def phase_metadata(
        cls,
        *,
        phase: RunPhase | str,
        status: Optional[RunStatus | str] = None,
        **metadata: Any,
    ) -> dict[str, Any]:
        payload = {
            "phase": cls.normalize_phase(phase),
            **{key: value for key, value in metadata.items() if value is not None},
        }
        if status is not None:
            payload["status"] = cls.normalize_status(status)
        return payload

    @staticmethod
    def get_phase_metadata(run: SessionRun) -> dict[str, Any]:
        metrics = run.metrics if isinstance(run.metrics, dict) else {}
        phase_metadata = metrics.get("phase_metadata")
        if isinstance(phase_metadata, dict):
            return dict(phase_metadata)

        phase = metrics.get("phase")
        if phase is None:
            return {}

        metadata = {"phase": phase}
        if isinstance(metrics.get("phase_status"), str):
            metadata["status"] = metrics["phase_status"]
        return metadata

    def get_run(self, run_id: str) -> SessionRun:
        run = self.db.get(SessionRun, run_id)
        if run is None:
            raise RunNotFoundError("Run not found")
        return run

    def list_runs(self, session_id: str, *, limit: Optional[int] = None) -> list[SessionRun]:
        query = (
            self.db.query(SessionRun)
            .filter(SessionRun.session_id == session_id)
            .order_by(SessionRun.created_at.desc())
        )
        if limit is not None:
            query = query.limit(limit)
        return query.all()

    def count_runs(self, session_id: str) -> int:
        return (
            self.db.query(SessionRun)
            .filter(SessionRun.session_id == session_id)
            .count()
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

    def get_latest_active_run(self, session_id: str) -> Optional[SessionRun]:
        return (
            self.db.query(SessionRun)
            .filter(
                SessionRun.session_id == session_id,
                SessionRun.status.in_(self.ACTIVE_STATES),
            )
            .order_by(SessionRun.updated_at.desc(), SessionRun.created_at.desc())
            .first()
        )

    def fail_stale_runs(
        self,
        *,
        session_id: Optional[str] = None,
        stale_after_seconds: float,
    ) -> list[SessionRun]:
        if stale_after_seconds <= 0:
            return []
        cutoff = utcnow() - timedelta(seconds=float(stale_after_seconds))
        query = self.db.query(SessionRun).filter(
            SessionRun.status.in_(self.ACTIVE_STATES),
            SessionRun.updated_at < cutoff,
        )
        if session_id:
            query = query.filter(SessionRun.session_id == session_id)

        stale_runs = query.all()
        for run in stale_runs:
            run.status = "failed"
            run.finished_at = run.finished_at or utcnow()
            run.latest_error = {
                "code": "run_stale_timeout",
                "message": "Run was marked failed after exceeding the stale timeout.",
                "stale_after_seconds": stale_after_seconds,
            }
            metrics = dict(run.metrics) if isinstance(run.metrics, dict) else {}
            metrics["stale_timeout"] = {
                "failed_at": utcnow().isoformat(),
                "stale_after_seconds": stale_after_seconds,
            }
            run.metrics = metrics
            self.clear_cancelled_marker(run.id)
            self.db.add(run)
        if stale_runs:
            self.db.flush(stale_runs)
            for run in stale_runs:
                self.db.refresh(run)
                self.db.expunge(run)
        return stale_runs

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
        try:
            self.db.flush([run])
        except IntegrityError as exc:
            self.db.rollback()
            raise RunStateConflictError(
                f"Run already active for session {run.session_id}"
            ) from exc
        return run

    def persist_run_phase(
        self,
        run_id: str,
        phase: RunPhase | str,
        *,
        status: Optional[RunStatus | str] = None,
        **metadata: Any,
    ) -> SessionRun:
        run = self.get_run(run_id)
        metrics = dict(run.metrics) if isinstance(run.metrics, dict) else {}
        phase_metadata = self.phase_metadata(
            phase=phase,
            status=status or run.status,
            **metadata,
        )
        metrics["phase"] = phase_metadata["phase"]
        metrics["phase_status"] = phase_metadata["status"]
        metrics["phase_metadata"] = phase_metadata
        run.metrics = metrics

        self.db.add(run)
        self.db.flush([run])
        return run

    def heartbeat_run(
        self,
        run_id: str,
        *,
        phase: Optional[RunPhase | str] = None,
        status: Optional[RunStatus | str] = None,
        **metadata: Any,
    ) -> SessionRun:
        run = self.get_run(run_id)
        metrics = dict(run.metrics) if isinstance(run.metrics, dict) else {}
        heartbeat = {
            "at": utcnow().isoformat(),
            **{key: value for key, value in metadata.items() if value is not None},
        }
        if phase is not None:
            heartbeat["phase"] = self.normalize_phase(phase)
        if status is not None:
            heartbeat["status"] = self.normalize_status(status)
        metrics["heartbeat"] = heartbeat
        run.metrics = metrics
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
