from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Optional

from sqlalchemy.orm import Session as DbSession

from ..db.models import SessionRun
from ..events.emitter import EventEmitter
from ..events.models import run_lifecycle_event
from ..events.types import EventType
from ..schemas.run import RunPhase, RunStatus
from ..services.event_store import EventStoreService
from ..services.run import RunCancelledError, RunService


PhaseContext = dict[str, Any]
PhaseResult = Any
PhaseCallable = Callable[[PhaseContext], Awaitable[PhaseResult] | PhaseResult]


@dataclass(slots=True)
class RunCoordinatorPhases:
    build: PhaseCallable
    review: PhaseCallable
    fix: PhaseCallable
    implement: PhaseCallable | None = None


@dataclass
class RunCoordinatorResult:
    status: str
    run_id: str
    current_phase: str
    phase_history: list[dict[str, Any]] = field(default_factory=list)
    fix_attempts: int = 0
    build: Any = None
    review: Any = None
    implement: Any = None
    fix: Any = None
    final_response: Any = None


class RunCoordinator:
    def __init__(
        self,
        *,
        db: DbSession,
        run_service: RunService | None = None,
        event_store: EventStoreService | None = None,
        event_emitter: EventEmitter | None = None,
        phases: RunCoordinatorPhases,
        max_fix_attempts: int = 1,
        phase_timeout_seconds: float | None = 900.0,
    ) -> None:
        self.db = db
        self.run_service = run_service or RunService(db)
        self.event_store = event_store
        self.phases = phases
        self.max_fix_attempts = max(0, int(max_fix_attempts))
        self.phase_timeout_seconds = phase_timeout_seconds
        self._emitter: EventEmitter | None = event_emitter

    async def run(self, run_id: str) -> RunCoordinatorResult:
        run = self.run_service.get_run(run_id)
        if run.status == RunStatus.CANCELLED.value:
            raise RunCancelledError(f"Run {run_id} is cancelled")
        if run.status == RunStatus.COMPLETED.value:
            return self._result_from_run(run, current_phase=self._state(run).get("current_phase", "done"))
        if run.status == RunStatus.FAILED.value:
            return self._result_from_run(run, current_phase=self._state(run).get("current_phase", "done"))

        if run.status == RunStatus.QUEUED.value:
            self.run_service.start_run(run_id)

        state = self._state(run)
        current_phase = str(state.get("current_phase") or "").strip()
        if not current_phase:
            current_phase = RunPhase.IMPLEMENT.value if self.phases.implement else RunPhase.BUILD.value
        fix_attempts = int(state.get("fix_attempts") or 0)
        artifacts = dict(state.get("artifacts") or {})
        phase_history = list(state.get("phase_history") or [])

        context = self._context(run, state)

        if current_phase == RunPhase.IMPLEMENT.value and self.phases.implement is not None:
            implement_result = await self._execute_phase(
                run_id,
                run,
                phase=RunPhase.IMPLEMENT,
                callable_=self.phases.implement,
                context=context,
                artifacts=artifacts,
                phase_history=phase_history,
                fix_attempts=fix_attempts,
            )
            if self._is_waiting(implement_result):
                return self._finalize_waiting(run_id, run, state, phase_history, artifacts, fix_attempts, implement_result)
            state["current_phase"] = RunPhase.BUILD.value
            state["artifacts"] = artifacts
            state["phase_history"] = phase_history
            self._save_state(run_id, state)

        if current_phase == RunPhase.BUILD.value or state.get("current_phase") in {None, RunPhase.BUILD.value}:
            build_result = await self._execute_phase(
                run_id,
                run,
                phase=RunPhase.BUILD,
                callable_=self.phases.build,
                context=context,
                artifacts=artifacts,
                phase_history=phase_history,
                fix_attempts=fix_attempts,
            )
            artifacts["build"] = self._jsonable(build_result)
            state["current_phase"] = RunPhase.REVIEW.value
            state["artifacts"] = artifacts
            state["phase_history"] = phase_history
            self._save_state(run_id, state)
        else:
            build_result = artifacts.get("build")

        if current_phase == RunPhase.FIX.value:
            fix_attempts = max(1, fix_attempts)
            state["fix_attempts"] = fix_attempts
            fix_result = await self._execute_phase(
                run_id,
                run,
                phase=RunPhase.FIX,
                callable_=self.phases.fix,
                context={
                    **context,
                    "review": artifacts.get("review"),
                    "build": build_result,
                    "fix_attempt": fix_attempts,
                    "fix_attempts": fix_attempts,
                },
                artifacts=artifacts,
                phase_history=phase_history,
                fix_attempts=fix_attempts,
            )
            artifacts["fix"] = self._jsonable(fix_result)
            state["current_phase"] = RunPhase.REVIEW.value
            state["artifacts"] = artifacts
            state["phase_history"] = phase_history
            self._save_state(run_id, state)

        review_result = None
        while True:
            state["current_phase"] = RunPhase.REVIEW.value
            state["artifacts"] = artifacts
            state["phase_history"] = phase_history
            self._save_state(run_id, state)
            self._emit_verify_start(run, fix_attempts=fix_attempts)
            review_result = await self._execute_phase(
                run_id,
                run,
                phase=RunPhase.REVIEW,
                callable_=self.phases.review,
                context=context,
                artifacts=artifacts,
                phase_history=phase_history,
                fix_attempts=fix_attempts,
            )
            artifacts["review"] = self._jsonable(review_result)
            self._emit_verify_event(run, passed=self._is_passed(review_result), review_result=review_result)
            if self._is_passed(review_result):
                state["current_phase"] = RunPhase.DONE.value
                state["artifacts"] = artifacts
                state["phase_history"] = phase_history
                self._save_state(run_id, state)
                self.run_service.persist_run_state(run_id, RunStatus.COMPLETED.value)
                self._emit_lifecycle_event(run, EventType.RUN_COMPLETED, phase=RunPhase.DONE.value, status=RunStatus.COMPLETED.value)
                return RunCoordinatorResult(
                    status=RunStatus.COMPLETED.value,
                    run_id=run_id,
                    current_phase=RunPhase.DONE.value,
                    phase_history=phase_history,
                    fix_attempts=fix_attempts,
                    build=build_result,
                    review=review_result,
                    implement=artifacts.get("implement"),
                    fix=artifacts.get("fix"),
                )

            if fix_attempts >= self.max_fix_attempts:
                state["current_phase"] = RunPhase.DONE.value
                state["artifacts"] = artifacts
                state["phase_history"] = phase_history
                state["last_review"] = self._jsonable(review_result)
                self._save_state(run_id, state)
                latest_error = {"review": self._jsonable(review_result)}
                self.run_service.persist_run_state(
                    run_id,
                    RunStatus.FAILED.value,
                    latest_error=latest_error,
                )
                self._emit_lifecycle_event(
                    run,
                    EventType.RUN_FAILED,
                    phase=RunPhase.REVIEW.value,
                    status=RunStatus.FAILED.value,
                    error="Review failed",
                )
                return RunCoordinatorResult(
                    status=RunStatus.FAILED.value,
                    run_id=run_id,
                    current_phase=RunPhase.DONE.value,
                    phase_history=phase_history,
                    fix_attempts=fix_attempts,
                    build=build_result,
                    review=review_result,
                    implement=artifacts.get("implement"),
                    fix=artifacts.get("fix"),
                )

            fix_attempts += 1
            state["fix_attempts"] = fix_attempts
            state["current_phase"] = RunPhase.FIX.value
            state["artifacts"] = artifacts
            state["phase_history"] = phase_history
            self._save_state(run_id, state)
            fix_result = await self._execute_phase(
                run_id,
                run,
                phase=RunPhase.FIX,
                callable_=self.phases.fix,
                context={
                    **context,
                    "review": review_result,
                    "build": build_result,
                    "fix_attempt": fix_attempts,
                    "fix_attempts": fix_attempts,
                },
                artifacts=artifacts,
                phase_history=phase_history,
                fix_attempts=fix_attempts,
            )
            artifacts["fix"] = self._jsonable(fix_result)
            state["current_phase"] = RunPhase.REVIEW.value
            state["artifacts"] = artifacts
            state["phase_history"] = phase_history
            self._save_state(run_id, state)

    def _state(self, run: SessionRun) -> dict[str, Any]:
        metrics = run.metrics if isinstance(run.metrics, dict) else {}
        coordinator = metrics.get("coordinator")
        if isinstance(coordinator, dict):
            return dict(coordinator)
        return {
            "current_phase": metrics.get("phase") if isinstance(metrics.get("phase"), str) else None,
            "phase_history": [],
            "fix_attempts": 0,
            "artifacts": {},
        }

    def _context(self, run: SessionRun, state: dict[str, Any]) -> PhaseContext:
        return {
            "run": run,
            "run_id": run.id,
            "session_id": run.session_id,
            "message": run.input_message,
            "resume_payload": run.resume_payload if isinstance(run.resume_payload, dict) else None,
            "state": state,
            "phase_history": list(state.get("phase_history") or []),
            "fix_attempts": int(state.get("fix_attempts") or 0),
            "artifacts": dict(state.get("artifacts") or {}),
        }

    async def _execute_phase(
        self,
        run_id: str,
        run: SessionRun,
        *,
        phase: RunPhase,
        callable_: PhaseCallable,
        context: PhaseContext,
        artifacts: dict[str, Any],
        phase_history: list[dict[str, Any]],
        fix_attempts: int | None = None,
    ) -> Any:
        self._ensure_not_cancelled(run_id)
        self.run_service.persist_run_phase(
            run_id,
            phase,
            status=RunStatus.RUNNING,
            started_at=self._timestamp(),
        )
        self.run_service.heartbeat_run(
            run_id,
            phase=phase,
            status=RunStatus.RUNNING,
            step="phase_start",
        )
        self._save_state(run_id, {
            **self._state(run),
            "current_phase": phase.value,
            "phase_history": phase_history,
            "artifacts": artifacts,
            "fix_attempts": int(fix_attempts or 0),
        })
        self._emit_lifecycle_event(
            run,
            EventType.RUN_STARTED,
            phase=phase.value,
            status=RunStatus.RUNNING.value,
        )
        self.db.commit()
        try:
            result = await self._call_with_timeout(
                callable_,
                self._phase_context(
                    context,
                    artifacts=artifacts,
                    phase_history=phase_history,
                    fix_attempts=fix_attempts,
                ),
            )
        except RunCancelledError:
            cancelled_at = self._timestamp()
            artifacts[phase.value] = {"cancelled": True}
            phase_history.append(
                {
                    "phase": phase.value,
                    "status": RunStatus.CANCELLED.value,
                    "completed_at": cancelled_at,
                }
            )
            self._save_state(run_id, {
                **self._state(run),
                "current_phase": phase.value,
                "phase_history": phase_history,
                "artifacts": artifacts,
            })
            self.run_service.persist_run_phase(
                run_id,
                phase,
                status=RunStatus.CANCELLED,
                completed_at=cancelled_at,
            )
            self.run_service.persist_run_state(
                run_id,
                RunStatus.CANCELLED.value,
            )
            self._emit_lifecycle_event(
                run,
                EventType.RUN_CANCELLED,
                phase=phase.value,
                status=RunStatus.CANCELLED.value,
            )
            self.db.commit()
            raise
        except Exception as exc:
            error_payload = {"message": str(exc) or exc.__class__.__name__}
            artifacts[phase.value] = {"error": error_payload}
            phase_history.append(
                {
                    "phase": phase.value,
                    "status": RunStatus.FAILED.value,
                    "error": error_payload,
                    "completed_at": self._timestamp(),
                }
            )
            self._save_state(run_id, {
                **self._state(run),
                "current_phase": phase.value,
                "phase_history": phase_history,
                "artifacts": artifacts,
            })
            self.run_service.persist_run_phase(
                run_id,
                phase,
                status=RunStatus.FAILED,
                error=error_payload,
                completed_at=self._timestamp(),
            )
            self.run_service.heartbeat_run(
                run_id,
                phase=phase,
                status=RunStatus.FAILED,
                step="phase_failed",
            )
            self.run_service.persist_run_state(
                run_id,
                RunStatus.FAILED.value,
                latest_error={"phase": phase.value, **error_payload},
            )
            self._emit_lifecycle_event(
                run,
                EventType.RUN_FAILED,
                phase=phase.value,
                status=RunStatus.FAILED.value,
                error=error_payload["message"],
            )
            self.db.commit()
            raise
        payload = self._jsonable(result)
        artifacts[phase.value] = payload
        phase_history.append(
            {
                "phase": phase.value,
                "status": RunStatus.COMPLETED.value,
                "output": payload,
                "completed_at": self._timestamp(),
            }
        )
        self.run_service.persist_run_phase(
            run_id,
            phase,
            status=RunStatus.COMPLETED,
            result=payload,
            completed_at=self._timestamp(),
        )
        self.run_service.heartbeat_run(
            run_id,
            phase=phase,
            status=RunStatus.COMPLETED,
            step="phase_complete",
        )
        self._save_state(run_id, {
            **self._state(run),
            "current_phase": phase.value,
            "phase_history": phase_history,
            "artifacts": artifacts,
        })
        return result

    def _phase_context(
        self,
        context: PhaseContext,
        *,
        artifacts: dict[str, Any],
        phase_history: list[dict[str, Any]],
        fix_attempts: int | None = None,
    ) -> PhaseContext:
        resolved_fix_attempts = int(
            fix_attempts
            if fix_attempts is not None
            else context.get("fix_attempts") or context.get("fix_attempt") or 0
        )
        next_state = dict(context.get("state") or {})
        next_state["artifacts"] = dict(artifacts)
        next_state["phase_history"] = list(phase_history)
        next_state["fix_attempts"] = resolved_fix_attempts
        return {
            **context,
            "state": next_state,
            "artifacts": dict(artifacts),
            "phase_history": list(phase_history),
            "fix_attempts": resolved_fix_attempts,
        }

    def _finalize_waiting(
        self,
        run_id: str,
        run: SessionRun,
        state: dict[str, Any],
        phase_history: list[dict[str, Any]],
        artifacts: dict[str, Any],
        fix_attempts: int,
        result: Any,
    ) -> RunCoordinatorResult:
        waiting_reason = self._waiting_reason(result)
        waiting_at = self._timestamp()
        if phase_history and phase_history[-1].get("phase") == RunPhase.IMPLEMENT.value:
            phase_history[-1] = {
                **phase_history[-1],
                "status": RunStatus.WAITING_INPUT.value,
                "waiting_reason": waiting_reason,
                "output": self._jsonable(result),
                "waiting_at": waiting_at,
            }
        else:
            phase_history.append(
                {
                    "phase": RunPhase.IMPLEMENT.value,
                    "status": RunStatus.WAITING_INPUT.value,
                    "waiting_reason": waiting_reason,
                    "output": self._jsonable(result),
                    "waiting_at": waiting_at,
                }
            )
        state["current_phase"] = RunPhase.IMPLEMENT.value
        state["phase_history"] = phase_history
        state["artifacts"] = artifacts
        state["fix_attempts"] = fix_attempts
        self._save_state(run_id, state)
        self.run_service.persist_run_phase(
            run_id,
            RunPhase.IMPLEMENT,
            status=RunStatus.WAITING_INPUT,
            waiting_reason=waiting_reason,
            result=self._jsonable(result),
            waiting_at=waiting_at,
        )
        self.run_service.heartbeat_run(
            run_id,
            phase=RunPhase.IMPLEMENT,
            status=RunStatus.WAITING_INPUT,
            step="waiting_input",
        )
        self.run_service.persist_run_state(
            run_id,
            RunStatus.WAITING_INPUT.value,
            latest_error=self._waiting_error(result),
        )
        self._emit_lifecycle_event(
            run,
            EventType.RUN_WAITING_INPUT,
            phase=RunPhase.IMPLEMENT.value,
            status=RunStatus.WAITING_INPUT.value,
            waiting_reason=waiting_reason,
        )
        return RunCoordinatorResult(
            status=RunStatus.WAITING_INPUT.value,
            run_id=run_id,
            current_phase=RunPhase.IMPLEMENT.value,
            phase_history=phase_history,
            fix_attempts=fix_attempts,
            final_response=result,
        )

    def _save_state(self, run_id: str, coordinator_state: dict[str, Any]) -> None:
        run = self.run_service.get_run(run_id)
        metrics = dict(run.metrics) if isinstance(run.metrics, dict) else {}
        last_review = coordinator_state.get("last_review")
        coordinator_state = {
            "current_phase": coordinator_state.get("current_phase"),
            "phase_history": list(coordinator_state.get("phase_history") or []),
            "fix_attempts": int(coordinator_state.get("fix_attempts") or 0),
            "artifacts": self._jsonable(coordinator_state.get("artifacts") or {}),
        }
        if last_review is not None:
            coordinator_state["last_review"] = self._jsonable(last_review)
        metrics["coordinator"] = coordinator_state
        run.metrics = metrics
        self.db.add(run)
        self.db.flush([run])
        self.db.commit()

    def _result_from_run(self, run: SessionRun, *, current_phase: str) -> RunCoordinatorResult:
        state = self._state(run)
        return RunCoordinatorResult(
            status=run.status,
            run_id=run.id,
            current_phase=current_phase,
            phase_history=list(state.get("phase_history") or []),
            fix_attempts=int(state.get("fix_attempts") or 0),
            build=(state.get("artifacts") or {}).get("build"),
            review=(state.get("artifacts") or {}).get("review"),
            implement=(state.get("artifacts") or {}).get("implement"),
            fix=(state.get("artifacts") or {}).get("fix"),
        )

    def _emit_verify_start(self, run: SessionRun, *, fix_attempts: int) -> None:
        self._emit_lifecycle_event(
            run,
            EventType.VERIFY_START,
            phase=RunPhase.REVIEW.value,
            status=RunStatus.RUNNING.value,
            fix_attempts=fix_attempts,
        )

    def _emit_verify_event(self, run: SessionRun, *, passed: bool, review_result: Any) -> None:
        self._emit_lifecycle_event(
            run,
            EventType.VERIFY_PASS if passed else EventType.VERIFY_FAIL,
            phase=RunPhase.REVIEW.value,
            status=RunStatus.COMPLETED.value if passed else RunStatus.FAILED.value,
            summary=self._review_summary(review_result),
        )

    def _emit_lifecycle_event(self, run: SessionRun, event_type: EventType, **payload: Any) -> None:
        emitter = self._ensure_emitter(run)
        if emitter is None:
            return
        emitter.emit(run_lifecycle_event(event_type, **payload))

    def _ensure_emitter(self, run: SessionRun) -> EventEmitter | None:
        if self._emitter is None and self.event_store is not None:
            self._emitter = EventEmitter(
                session_id=run.session_id,
                run_id=run.id,
                event_store=self.event_store,
            )
        elif self._emitter is not None:
            self._emitter.session_id = run.session_id
            self._emitter.run_id = run.id
        return self._emitter

    async def _maybe_await(self, value: Awaitable[PhaseResult] | PhaseResult) -> PhaseResult:
        if inspect.isawaitable(value):
            return await value
        return value

    async def _call_with_timeout(
        self,
        callable_: PhaseCallable,
        context: PhaseContext,
    ) -> PhaseResult:
        pending = self._maybe_await(callable_(context))
        if self.phase_timeout_seconds is None:
            return await pending
        return await asyncio.wait_for(pending, timeout=float(self.phase_timeout_seconds))

    def _ensure_not_cancelled(self, run_id: str) -> None:
        if RunService.is_cancelled(run_id):
            raise RunCancelledError(f"Run {run_id} is cancelled")

    def _is_passed(self, result: Any) -> bool:
        if result is None:
            return False
        if hasattr(result, "passed"):
            try:
                return bool(getattr(result, "passed"))
            except Exception:
                return False
        if isinstance(result, dict):
            if "passed" in result:
                return bool(result["passed"])
            verdict = str(result.get("verdict") or result.get("status") or "").lower()
            return verdict in {"pass", "passed", "success", "ok"}
        verdict = str(getattr(result, "verdict", "") or "").lower()
        if verdict:
            return verdict in {"pass", "passed", "success", "ok"}
        return bool(result)

    def _is_waiting(self, result: Any) -> bool:
        if result is None:
            return False
        if hasattr(result, "action"):
            action = str(getattr(result, "action") or "").strip().lower()
            if action == "refine_waiting":
                return True
            if action == "error":
                return False
        if hasattr(result, "is_complete"):
            try:
                if not bool(getattr(result, "is_complete")):
                    return True
            except Exception:
                return False
        if isinstance(result, dict):
            action = str(result.get("action") or "").strip().lower()
            if action == "refine_waiting":
                return True
            status = str(result.get("status") or "").strip().lower()
            if status == "waiting_input":
                return True
        return False

    def _waiting_reason(self, result: Any) -> str:
        if hasattr(result, "message"):
            message = str(getattr(result, "message") or "").strip()
            if message:
                return message
        if isinstance(result, dict):
            message = str(result.get("message") or "").strip()
            if message:
                return message
            return str(result.get("waiting_reason") or result.get("reason") or "Waiting for user input")
        return "Waiting for user input"

    def _waiting_error(self, result: Any) -> dict[str, Any]:
        return {"waiting_reason": self._waiting_reason(result)}

    def _review_summary(self, result: Any) -> dict[str, Any]:
        if hasattr(result, "summary"):
            summary = getattr(result, "summary")
            if isinstance(summary, dict):
                return summary
        if isinstance(result, dict):
            summary = result.get("summary")
            if isinstance(summary, dict):
                return summary
        return {"result": self._jsonable(result)}

    def _timestamp(self) -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def _jsonable(self, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, dict):
            return {str(key): self._jsonable(val) for key, val in value.items()}
        if isinstance(value, list):
            return [self._jsonable(item) for item in value]
        if hasattr(value, "model_dump"):
            try:
                return self._jsonable(value.model_dump(mode="json"))
            except Exception:
                return self._jsonable(value.model_dump())
        if hasattr(value, "__dict__") and not isinstance(value, type):
            return self._jsonable(
                {key: val for key, val in value.__dict__.items() if not key.startswith("_")}
            )
        return str(value)


__all__ = ["RunCoordinator", "RunCoordinatorPhases", "RunCoordinatorResult"]
