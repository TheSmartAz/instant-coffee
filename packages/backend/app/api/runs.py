from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import AsyncGenerator, Generator, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from ..config import get_settings
from ..db.database import get_database
from ..db.models import Session as SessionModel
from ..db.models import SessionEvent, SessionRun
from ..db.utils import get_db
from ..events.emitter import EventEmitter
from ..events.models import run_lifecycle_event
from ..events.types import EventType
from ..engine.registry import engine_registry
from ..schemas.run import (
    RunApprovalRequest,
    RunCreate,
    RunContextEvidence,
    RunListResponse,
    RunResponse,
    RunResumeRequest,
    RunStatus,
    RunVerification,
    RunActionAuditEvent,
    VerificationAuditEvent,
    VerificationCommandResult,
    VerificationFixAttempt,
    VerificationRunResult,
    VerificationCheck,
    normalize_execution_mode,
)
from ..services.event_store import EventStoreService
from ..services.memory import ProjectMemoryService
from ..services.run import RunNotFoundError, RunService, RunStateConflictError
from ..services.change_summary import build_change_summary, capture_worktree_files
from ..services.verification_fix import VerificationFixService
from ..services.verification_runner import VerificationRunner
from ..services.visual_verification import VisualVerificationService
from .auth import require_admin_token

router = APIRouter(prefix="/api/runs", tags=["runs"])


class RunEventResponse(BaseModel):
    id: int
    session_id: str
    run_id: Optional[str]
    event_id: Optional[str]
    seq: int
    type: str
    payload: dict
    source: str
    created_at: str


class RunEventsResponse(BaseModel):
    events: list[RunEventResponse]
    last_seq: int
    has_more: bool


TERMINAL_RUN_STATES = {
    RunStatus.COMPLETED.value,
    RunStatus.FAILED.value,
    RunStatus.CANCELLED.value,
}


@dataclass
class _IdempotencyRecord:
    status_code: int
    body: dict
    expires_at: datetime


_IDEMPOTENCY_TTL = timedelta(hours=24)
_STALE_VERIFICATION_FIX_AFTER = timedelta(minutes=30)
_idempotency_guard = Lock()
_idempotency_cache: dict[tuple[str, str], _IdempotencyRecord] = {}
_verification_fix_guard = Lock()
_verification_fix_active: set[str] = set()
_PUBLIC_BUILD_KEYS = {"status", "pages", "dist_path", "error", "source_mode"}
_PUBLIC_PHASE_KEYS = {"phase", "status", "waiting_reason", "error"}
_PUBLIC_EVENT_PAYLOAD_KEYS = {
    "approval_id",
    "approved",
    "command",
    "execution_mode",
    "phase",
    "reason",
    "status",
    "run_id",
    "event_id",
    "message",
    "error",
    "waiting_reason",
}


def _public_dict(value: dict, allowed_keys: set[str]) -> dict:
    return {key: value[key] for key in allowed_keys if key in value}


def _redact_failure(failure: dict) -> dict:
    return {
        key: failure[key]
        for key in ("file", "line", "source", "scope", "check")
        if key in failure
    }


def _redact_verification_run(result: VerificationRunResult | None) -> VerificationRunResult | None:
    if result is None:
        return None
    return VerificationRunResult(
        status=result.status,
        passed=result.passed,
        commands=[
            {
                "name": command.name,
                "command": command.command,
                "scope": command.scope,
                "status": command.status,
                "exit_code": command.exit_code,
                "duration_ms": command.duration_ms,
                "output_summary": "",
                "failures": [_redact_failure(item) for item in command.failures],
            }
            for command in result.commands
        ],
        risk_flags=list(result.risk_flags),
        started_at=result.started_at,
        completed_at=result.completed_at,
    )


def _redact_fix_attempt(attempt: VerificationFixAttempt) -> VerificationFixAttempt:
    return VerificationFixAttempt(
        attempt=attempt.attempt,
        status=attempt.status,
        prompt="",
        failures=[_redact_failure(item) for item in attempt.failures],
        engine=None,
        verification=_redact_verification_run(attempt.verification),
        change_summary=attempt.change_summary,
        error=attempt.error,
        started_at=attempt.started_at,
        completed_at=attempt.completed_at,
    )


def _get_db_session() -> Generator[DbSession, None, None]:
    with get_db() as session:
        yield session


def _ensure_run_api_enabled() -> None:
    settings = get_settings()
    if not settings.run_api_enabled:
        raise HTTPException(status_code=404, detail="Not found")


def _format_timestamp(value: Optional[datetime]) -> str:
    if value is None:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _serialize_event(event: SessionEvent) -> RunEventResponse:
    payload = event.payload or {}
    if not isinstance(payload, dict):
        payload = {}
    else:
        payload = _public_dict(payload, _PUBLIC_EVENT_PAYLOAD_KEYS)
    return RunEventResponse(
        id=event.id,
        session_id=event.session_id,
        run_id=event.run_id,
        event_id=event.event_id,
        seq=event.seq,
        type=event.type,
        payload=payload,
        source=getattr(event.source, "value", event.source),
        created_at=_format_timestamp(event.created_at),
    )


def _coordinator_state(run: SessionRun) -> dict:
    metrics = run.metrics if isinstance(run.metrics, dict) else {}
    coordinator = metrics.get("coordinator")
    return coordinator if isinstance(coordinator, dict) else {}


def _review_payload(run: SessionRun) -> Optional[dict]:
    state = _coordinator_state(run)
    artifacts = state.get("artifacts")
    if isinstance(artifacts, dict):
        review = artifacts.get("review")
        if isinstance(review, dict):
            return dict(review)
    last_review = state.get("last_review")
    if isinstance(last_review, dict):
        return dict(last_review)
    return None


def _dict_or_empty(value) -> dict:
    return value if isinstance(value, dict) else {}


def _build_artifact(artifacts: dict) -> dict:
    build = artifacts.get("build")
    if isinstance(build, dict):
        return build
    fix = artifacts.get("fix")
    if isinstance(fix, dict) and isinstance(fix.get("build"), dict):
        return fix["build"]
    if any(key in artifacts for key in ("status", "pages", "dist_path", "error")):
        return artifacts
    return {}


def _visual_artifact(artifacts: dict) -> dict:
    visual = artifacts.get("visual_verification")
    return visual if isinstance(visual, dict) else {}


def _public_artifacts(artifacts: dict) -> dict:
    public: dict = {}
    build = _build_artifact(artifacts)
    if build:
        public["build"] = _public_dict(build, _PUBLIC_BUILD_KEYS)
    fix = artifacts.get("fix")
    if isinstance(fix, dict) and isinstance(fix.get("build"), dict):
        public["fix"] = {"build": _public_dict(fix["build"], _PUBLIC_BUILD_KEYS)}
    visual = _visual_artifact(artifacts)
    if visual:
        public["visual_verification"] = {
            key: visual[key]
            for key in (
                "status",
                "passed",
                "quality_score",
                "screenshot_path",
                "reason",
            )
            if key in visual
        }
    return public


def _visual_check_from_artifact(visual: dict) -> VerificationCheck | None:
    if not visual:
        return None
    status = str(visual.get("status") or "unknown")
    raw_passed = visual.get("passed")
    passed = raw_passed if isinstance(raw_passed, bool) else None
    checks = visual.get("checks") if isinstance(visual.get("checks"), list) else []
    errors = visual.get("errors") if isinstance(visual.get("errors"), list) else []
    warnings = visual.get("warnings") if isinstance(visual.get("warnings"), list) else []
    return VerificationCheck(
        name="visual",
        status=status,
        passed=passed,
        details={
            "quality_score": visual.get("quality_score"),
            "screenshot_path": visual.get("screenshot_path"),
            "page": visual.get("page"),
            "check_count": len(checks),
            "error_count": len(errors),
            "warning_count": len(warnings),
            "errors": errors[:10],
            "warnings": warnings[:10],
            "reason": visual.get("reason"),
        },
    )


def _public_phase_history(entries: list | None) -> list[dict]:
    public_entries = []
    for entry in entries or []:
        if isinstance(entry, dict):
            public_entries.append(_public_dict(entry, _PUBLIC_PHASE_KEYS))
    return public_entries


def _review_passed(review: dict) -> Optional[bool]:
    if "passed" in review:
        return bool(review["passed"])
    verdict = review.get("verdict")
    if isinstance(verdict, str):
        return verdict.lower() in {"pass", "passed", "success", "ok"}
    return None


def _verification_profile(
    *,
    run: SessionRun,
    build: dict,
    review_issues: list[dict],
    memory: dict[str, str],
) -> dict:
    commands = [
        {
            "name": "backend targeted tests",
            "command": "PYTHONPATH=.:../agent/src python -m pytest -q",
            "scope": "backend",
        },
        {
            "name": "web lint",
            "command": "npm run lint",
            "scope": "web",
        },
        {
            "name": "web build",
            "command": "npm run build",
            "scope": "web",
        },
    ]
    testing_notes = memory.get("testing_notes", "").lower()
    if "playwright" in testing_notes:
        commands.append(
            {
                "name": "web e2e",
                "command": "npx playwright test",
                "scope": "web",
            }
        )

    risk_flags: list[str] = []
    if run.status == RunStatus.FAILED.value:
        risk_flags.append("run_failed")
    if build.get("error"):
        risk_flags.append("build_error")
    if review_issues:
        severities = {str(issue.get("severity", "")).lower() for issue in review_issues}
        risk_flags.append("review_errors" if "error" in severities else "review_warnings")
    if not build:
        risk_flags.append("build_not_recorded")
    if not memory.get("testing_notes"):
        risk_flags.append("test_memory_missing")

    return {
        "recommended_commands": commands,
        "risk_flags": risk_flags,
        "memory_keys": sorted(memory.keys()),
    }


def _run_verification(
    run: SessionRun,
    *,
    artifacts: dict,
    review: Optional[dict],
    review_summary: Optional[dict],
    review_issues: list[dict],
    memory: dict[str, str],
    redact: bool = True,
) -> RunVerification:
    checks: list[VerificationCheck] = []
    evidence: list[str] = []

    build = _build_artifact(artifacts)
    if build:
        build_status = str(build.get("status") or "unknown")
        build_pages = build.get("pages") if isinstance(build.get("pages"), list) else []
        build_passed = build_status.lower() in {"success", "completed", "ok"}
        if build_status == "unknown" and build_pages:
            build_passed = True
        checks.append(
            VerificationCheck(
                name="build",
                status=build_status,
                passed=build_passed,
                details={
                    "pages": build_pages,
                    "page_count": len(build_pages),
                    "dist_path": build.get("dist_path"),
                    "error": build.get("error"),
                },
            )
        )
        if build_pages:
            evidence.append(f"Build produced {len(build_pages)} page artifact(s).")
        if build.get("dist_path"):
            evidence.append(f"Build output: {build['dist_path']}")
        if build.get("error"):
            evidence.append(f"Build error: {build['error']}")

    visual = _visual_artifact(artifacts)
    visual_check = _visual_check_from_artifact(visual)
    if visual_check is not None:
        checks.append(visual_check)
        score = visual.get("quality_score")
        if score is not None:
            evidence.append(f"Visual quality score: {score}/100.")
        if visual.get("screenshot_path"):
            evidence.append(f"Visual screenshot: {visual['screenshot_path']}")
        if visual.get("reason"):
            evidence.append(f"Visual verification: {visual['reason']}")

    if review is not None:
        passed = _review_passed(review)
        status = "pass" if passed is True else "fail" if passed is False else "unknown"
        summary = _dict_or_empty(review_summary)
        checks.append(
            VerificationCheck(
                name="review",
                status=status,
                passed=passed,
                details={
                    "error_count": summary.get("error_count"),
                    "warning_count": summary.get("warning_count"),
                    "issue_count": len(review_issues),
                    "issues": review_issues[:10],
                },
            )
        )
        evidence.append(
            "Review passed with no blocking issues."
            if passed is True
            else f"Review reported {len(review_issues)} issue(s)."
        )

    known = [check.passed for check in checks if check.passed is not None]
    if known and all(known):
        status = "passed"
        passed: Optional[bool] = True
    elif any(item is False for item in known) or run.status == RunStatus.FAILED.value:
        status = "failed"
        passed = False
    elif run.status in {RunStatus.QUEUED.value, RunStatus.RUNNING.value, RunStatus.WAITING_INPUT.value}:
        status = "in_progress"
        passed = None
    elif run.status == RunStatus.CANCELLED.value:
        status = "cancelled"
        passed = False
    else:
        status = "unknown"
        passed = None

    last_run_payload = artifacts.get("verification_run")
    last_run = None
    if isinstance(last_run_payload, dict):
        try:
            last_run = VerificationRunResult.model_validate(last_run_payload)
        except Exception:
            last_run = None
    if last_run is not None:
        status = last_run.status
        passed = last_run.passed
        if any(check.passed is False for check in checks):
            status = "failed"
            passed = False
    fix_attempts_payload = artifacts.get("verification_fix_attempts")
    fix_attempts: list[VerificationFixAttempt] = []
    if isinstance(fix_attempts_payload, list):
        for item in fix_attempts_payload:
            if not isinstance(item, dict):
                continue
            try:
                fix_attempts.append(VerificationFixAttempt.model_validate(item))
            except Exception:
                continue
    audit_payload = artifacts.get("verification_audit_trail")
    audit_trail: list[VerificationAuditEvent] = []
    if isinstance(audit_payload, list):
        for item in audit_payload:
            if not isinstance(item, dict):
                continue
            try:
                audit_trail.append(VerificationAuditEvent.model_validate(item))
            except Exception:
                continue
    action_audit_payload = artifacts.get("action_audit_trail")
    action_audit_trail: list[RunActionAuditEvent] = []
    if isinstance(action_audit_payload, list):
        for item in action_audit_payload:
            if not isinstance(item, dict):
                continue
            try:
                action_audit_trail.append(RunActionAuditEvent.model_validate(item))
            except Exception:
                continue

    return RunVerification(
        status=status,
        passed=passed,
        checks=checks,
        evidence=evidence,
        summary={
            "run_status": run.status,
            "check_count": len(checks),
            "passed_count": sum(1 for item in known if item is True),
            "failed_count": sum(1 for item in known if item is False),
        },
        profile=_verification_profile(
            run=run,
            build=build,
            review_issues=review_issues,
            memory=memory,
        ),
        last_run=_redact_verification_run(last_run) if redact else last_run,
        fix_attempts=[_redact_fix_attempt(attempt) for attempt in fix_attempts] if redact else fix_attempts,
        audit_trail=audit_trail,
        action_audit_trail=action_audit_trail,
    )


def _context_evidence(db: DbSession | None, session_id: str) -> RunContextEvidence:
    if db is None:
        return RunContextEvidence()
    memory = ProjectMemoryService(db).build_memory_summary(session_id)
    return RunContextEvidence(
        memory_keys=sorted(memory.keys()),
        memory=memory,
    )


def _run_to_response(run: SessionRun, db: DbSession | None = None, *, redact: bool = True) -> RunResponse:
    latest_error = run.latest_error if isinstance(run.latest_error, dict) else None
    metrics = run.metrics if isinstance(run.metrics, dict) else {}
    state = _coordinator_state(run)
    artifacts = state.get("artifacts") if isinstance(state.get("artifacts"), dict) else {}
    phase_history = state.get("phase_history") if isinstance(state.get("phase_history"), list) else []
    context = _context_evidence(db, run.session_id)
    phase_metadata = RunService.get_phase_metadata(run)
    review = _review_payload(run)
    review_summary = None
    review_issues: list[dict] = []
    if isinstance(review, dict):
        summary = review.get("summary")
        if isinstance(summary, dict):
            review_summary = summary
        issues = review.get("issues")
        if isinstance(issues, list):
            review_issues = [issue for issue in issues if isinstance(issue, dict)]

    heartbeat = metrics.get("heartbeat")
    heartbeat_at = None
    if isinstance(heartbeat, dict) and heartbeat.get("at") is not None:
        heartbeat_at = str(heartbeat["at"])

    waiting_reason: Optional[str] = None
    if isinstance(latest_error, dict):
        candidate = latest_error.get("waiting_reason") or latest_error.get("reason")
        if candidate is not None:
            waiting_reason = str(candidate)

    execution_mode = normalize_execution_mode(metrics.get("execution_mode") or metrics.get("approval_mode"))

    return RunResponse(
        run_id=run.id,
        session_id=run.session_id,
        status=RunStatus(run.status),
        created_at=run.created_at,
        updated_at=run.updated_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
        latest_error=None if redact else latest_error,
        metrics=None if redact else metrics,
        execution_mode=execution_mode,
        approval_mode=execution_mode,
        checkpoint_thread=None if redact else run.checkpoint_thread,
        checkpoint_ns=None if redact else run.checkpoint_ns,
        waiting_reason=waiting_reason,
        current_phase=(
            str(state.get("current_phase"))
            if state.get("current_phase") is not None
            else phase_metadata.get("phase")
        ),
        phase_status=(
            str(phase_metadata.get("status"))
            if phase_metadata.get("status") is not None
            else None
        ),
        phase_metadata=_public_dict(phase_metadata, _PUBLIC_PHASE_KEYS) if redact else phase_metadata,
        phase_history=_public_phase_history(phase_history) if redact else list(phase_history),
        artifacts=_public_artifacts(dict(artifacts)) if redact else dict(artifacts),
        fix_attempts=int(state.get("fix_attempts") or 0),
        last_review=review,
        review_summary=review_summary,
        review_issues=review_issues,
        verification=_run_verification(
            run,
            artifacts=dict(artifacts),
            review=review,
            review_summary=review_summary,
            review_issues=review_issues,
            memory=context.memory,
            redact=redact,
        ),
        context=RunContextEvidence(memory_keys=context.memory_keys, memory={}) if redact else context,
        heartbeat_at=heartbeat_at,
    )


def _idempotency_scope(action: str, target_id: str) -> str:
    return f"{action}:{target_id}"


def _idempotency_get(scope: str, key: str) -> Optional[JSONResponse]:
    if not key:
        return None
    now = datetime.now(timezone.utc)
    cache_key = (scope, key)

    with _idempotency_guard:
        expired = [item for item, entry in _idempotency_cache.items() if entry.expires_at <= now]
        for item in expired:
            _idempotency_cache.pop(item, None)

        entry = _idempotency_cache.get(cache_key)
        if entry is None:
            return None
        return JSONResponse(status_code=entry.status_code, content=entry.body)


def _idempotency_set(scope: str, key: str, status_code: int, body: dict) -> None:
    if not key:
        return
    now = datetime.now(timezone.utc)
    with _idempotency_guard:
        _idempotency_cache[(scope, key)] = _IdempotencyRecord(
            status_code=status_code,
            body=body,
            expires_at=now + _IDEMPOTENCY_TTL,
        )


def _try_acquire_verification_fix(run_id: str) -> bool:
    with _verification_fix_guard:
        if run_id in _verification_fix_active:
            return False
        _verification_fix_active.add(run_id)
        return True


def _release_verification_fix(run_id: str) -> None:
    with _verification_fix_guard:
        _verification_fix_active.discard(run_id)


def _store_verification_fix_attempt(
    *,
    run: SessionRun,
    attempt: VerificationFixAttempt,
    existing_attempts: list[dict],
) -> None:
    metrics = dict(run.metrics) if isinstance(run.metrics, dict) else {}
    coordinator = dict(metrics.get("coordinator") or {})
    artifacts = dict(coordinator.get("artifacts") or {})
    stored_attempts = list(existing_attempts)
    attempt_payload = attempt.model_dump(mode="json")
    if stored_attempts and stored_attempts[-1].get("attempt") == attempt.attempt:
        stored_attempts[-1] = attempt_payload
    else:
        stored_attempts.append(attempt_payload)
    artifacts["verification_fix_attempts"] = stored_attempts
    if attempt.verification is not None:
        artifacts["verification_run"] = attempt.verification.model_dump(mode="json")
    coordinator["artifacts"] = artifacts
    coordinator["fix_attempts"] = max(int(coordinator.get("fix_attempts") or 0), len(stored_attempts))
    metrics["coordinator"] = coordinator
    run.metrics = metrics


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_iso() -> str:
    return _utc_now().isoformat().replace("+00:00", "Z")


def _parse_utc(value: object) -> Optional[datetime]:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _audit_event(
    *,
    type_: str,
    status: str,
    message: str = "",
    attempt: int | None = None,
    result: VerificationRunResult | None = None,
) -> dict:
    failure_count = None
    command_count = None
    risk_flags: list[str] = []
    if result is not None:
        command_count = len(result.commands)
        failure_count = sum(len(command.failures) for command in result.commands)
        risk_flags = list(result.risk_flags)
    return {
        "type": type_,
        "status": status,
        "message": message,
        "attempt": attempt,
        "command_count": command_count,
        "failure_count": failure_count,
        "risk_flags": risk_flags,
        "at": _utc_iso(),
    }


def _append_verification_audit(
    *,
    artifacts: dict,
    event: dict,
    limit: int = 50,
) -> None:
    events = artifacts.get("verification_audit_trail")
    if not isinstance(events, list):
        events = []
    events.append(event)
    artifacts["verification_audit_trail"] = events[-limit:]


def _append_action_audit(
    *,
    artifacts: dict,
    event: dict,
    limit: int = 100,
) -> None:
    events = artifacts.get("action_audit_trail")
    if not isinstance(events, list):
        events = []
    payload = {
        "type": str(event.get("type") or "action"),
        "category": str(event.get("category") or "system"),
        "status": str(event.get("status") or "unknown"),
        "summary": str(event.get("summary") or ""),
        "attempt": event.get("attempt") if isinstance(event.get("attempt"), int) else None,
        "command": str(event["command"]) if event.get("command") is not None else None,
        "scope": str(event["scope"]) if event.get("scope") is not None else None,
        "exit_code": event.get("exit_code") if isinstance(event.get("exit_code"), int) else None,
        "duration_ms": event.get("duration_ms") if isinstance(event.get("duration_ms"), int) else None,
        "file_count": event.get("file_count") if isinstance(event.get("file_count"), int) else None,
        "risk_level": str(event["risk_level"]) if event.get("risk_level") is not None else None,
        "risk_flags": [str(flag) for flag in event.get("risk_flags") or []],
        "at": str(event.get("at") or _utc_iso()),
    }
    events.append(payload)
    artifacts["action_audit_trail"] = events[-limit:]


def _verification_command_action(command: VerificationCommandResult) -> dict:
    return {
        "type": "verification_command",
        "category": "shell",
        "status": command.status,
        "summary": command.name,
        "command": command.command,
        "scope": command.scope,
        "exit_code": command.exit_code,
        "duration_ms": command.duration_ms,
    }


def _append_verification_command_actions(*, artifacts: dict, result: VerificationRunResult) -> None:
    for command in result.commands:
        _append_action_audit(artifacts=artifacts, event=_verification_command_action(command))


def _mark_stale_running_verification_fixes(artifacts: dict) -> bool:
    attempts = artifacts.get("verification_fix_attempts")
    if not isinstance(attempts, list):
        return False
    changed = False
    now = _utc_now()
    for item in attempts:
        if not isinstance(item, dict) or item.get("status") != "running":
            continue
        started_at = _parse_utc(item.get("started_at"))
        if started_at is None or now - started_at <= _STALE_VERIFICATION_FIX_AFTER:
            continue
        item["status"] = "stale_error"
        item["error"] = "Verification fix attempt was still running after recovery timeout."
        item["completed_at"] = _utc_iso()
        _append_verification_audit(
            artifacts=artifacts,
            event=_audit_event(
                type_="verification_fix_recovered",
                status="stale_error",
                message="Recovered stale running verification fix attempt.",
                attempt=int(item.get("attempt") or 0) or None,
            ),
        )
        changed = True
    if changed:
        artifacts["verification_fix_attempts"] = attempts
    return changed


@router.post("", response_model=RunResponse, status_code=201)
def create_run(
    payload: RunCreate,
    db: DbSession = Depends(_get_db_session),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    _ensure_run_api_enabled()
    key = (idempotency_key or "").strip()
    scope = _idempotency_scope("create", payload.session_id)
    cached = _idempotency_get(scope, key)
    if cached is not None:
        return cached

    service = RunService(db)
    service.fail_stale_runs(
        session_id=payload.session_id,
        stale_after_seconds=get_settings().run_stale_timeout_seconds,
    )
    active_run = service.get_latest_active_run(payload.session_id)
    if active_run is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Run {active_run.id} is already {active_run.status}",
        )
    try:
        run = service.create_run(
            session_id=payload.session_id,
            message=payload.message,
            generate_now=payload.generate_now,
            execution_mode=payload.execution_mode,
            approval_mode=payload.approval_mode,
            style_reference=(
                payload.style_reference.model_dump(mode="json")
                if payload.style_reference is not None
                else None
            ),
            target_pages=payload.target_pages,
        )
    except RunStateConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        detail = str(exc)
        if detail == "Session not found":
            raise HTTPException(status_code=404, detail=detail) from exc
        raise HTTPException(status_code=422, detail=detail) from exc

    db.commit()
    response = _run_to_response(run, db)
    body = response.model_dump(mode="json")
    _idempotency_set(scope, key, 201, body)
    return body


@router.get("", response_model=RunListResponse)
def list_runs(
    session_id: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
    db: DbSession = Depends(_get_db_session),
):
    _ensure_run_api_enabled()
    service = RunService(db)
    runs = service.list_runs(session_id, limit=limit)
    return RunListResponse(
        runs=[_run_to_response(run, db) for run in runs],
        total=service.count_runs(session_id),
    )


@router.get("/{run_id}", response_model=RunResponse)
def get_run(run_id: str, db: DbSession = Depends(_get_db_session)):
    _ensure_run_api_enabled()
    service = RunService(db)
    try:
        run = service.get_run(run_id)
    except RunNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc
    return _run_to_response(run, db)


@router.post("/{run_id}/resume", response_model=RunResponse)
def resume_run(
    run_id: str,
    payload: RunResumeRequest,
    db: DbSession = Depends(_get_db_session),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    _ensure_run_api_enabled()
    key = (idempotency_key or "").strip()
    scope = _idempotency_scope("resume", run_id)
    cached = _idempotency_get(scope, key)
    if cached is not None:
        return cached

    service = RunService(db)
    try:
        run = service.resume_run(run_id, payload.resume_payload)
    except RunNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc
    except RunStateConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    db.commit()
    response = _run_to_response(run, db)
    body = response.model_dump(mode="json")
    _idempotency_set(scope, key, 200, body)
    return body


@router.post("/{run_id}/cancel", response_model=RunResponse)
def cancel_run(
    run_id: str,
    response: Response,
    db: DbSession = Depends(_get_db_session),
):
    _ensure_run_api_enabled()
    service = RunService(db)
    try:
        run, accepted = service.cancel_run(run_id)
    except RunNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc

    if accepted:
        EventEmitter(
            session_id=run.session_id,
            run_id=run.id,
            event_store=EventStoreService(db),
        ).emit(
            run_lifecycle_event(
                EventType.RUN_CANCELLED,
                phase="done",
                status=RunStatus.CANCELLED.value,
            )
        )
    db.commit()
    response.status_code = 202 if accepted else 200
    return _run_to_response(run, db)


@router.post("/{run_id}/approvals/{approval_id}", response_model=RunResponse)
def resolve_run_approval(
    run_id: str,
    approval_id: str,
    payload: RunApprovalRequest,
    db: DbSession = Depends(_get_db_session),
):
    _ensure_run_api_enabled()
    service = RunService(db)
    try:
        run = service.get_run(run_id)
    except RunNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc

    if run.status not in {RunStatus.RUNNING.value, RunStatus.WAITING_INPUT.value}:
        raise HTTPException(status_code=409, detail=f"Run is {run.status}")

    resolved = engine_registry.resolve_shell_approval(
        run.session_id,
        approval_id,
        payload.approved,
    )
    if not resolved:
        raise HTTPException(status_code=404, detail="Approval request not found or expired")

    db.commit()
    return _run_to_response(run, db)


@router.post("/{run_id}/verification", response_model=RunResponse)
async def run_verification(
    run_id: str,
    db: DbSession = Depends(_get_db_session),
    _: None = Depends(require_admin_token),
):
    _ensure_run_api_enabled()
    service = RunService(db)
    try:
        run = service.get_run(run_id)
    except RunNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc

    response = _run_to_response(run, db)
    metrics = dict(run.metrics) if isinstance(run.metrics, dict) else {}
    coordinator = dict(metrics.get("coordinator") or {})
    artifacts = dict(coordinator.get("artifacts") or {})
    _append_verification_audit(
        artifacts=artifacts,
        event=_audit_event(
            type_="verification_started",
            status="running",
            message="Manual verification started.",
        ),
    )
    _append_action_audit(
        artifacts=artifacts,
        event={
            "type": "verification_run_started",
            "category": "verification",
            "status": "running",
            "summary": "Manual verification started.",
        },
    )
    coordinator["artifacts"] = artifacts
    metrics["coordinator"] = coordinator
    run.metrics = metrics
    db.add(run)
    db.commit()
    db.refresh(run)

    result = await VerificationRunner().run_profile(response.verification.profile)
    build = _build_artifact(dict(artifacts))
    dist_path = build.get("dist_path") if isinstance(build.get("dist_path"), str) else None
    visual_result = (
        await VisualVerificationService().verify_dist(
            session_id=run.session_id,
            dist_path=dist_path,
        )
        if dist_path
        else None
    )

    metrics = dict(run.metrics) if isinstance(run.metrics, dict) else {}
    coordinator = dict(metrics.get("coordinator") or {})
    artifacts = dict(coordinator.get("artifacts") or {})
    artifacts["verification_run"] = result.model_dump(mode="json")
    _append_verification_command_actions(artifacts=artifacts, result=result)
    if visual_result is not None:
        artifacts["visual_verification"] = visual_result
    _append_verification_audit(
        artifacts=artifacts,
        event=_audit_event(
            type_="verification_completed",
            status=result.status,
            message="Manual verification completed.",
            result=result,
        ),
    )
    if visual_result is not None:
        visual_status = str(visual_result.get("status") or "unknown")
        visual_message = str(
            visual_result.get("reason")
            or (
                f"Visual quality score {visual_result.get('quality_score')}/100."
                if visual_result.get("quality_score") is not None
                else "Visual verification completed."
            )
        )
        _append_verification_audit(
            artifacts=artifacts,
            event={
                "type": "visual_verification_completed",
                "status": visual_status,
                "message": visual_message,
                "attempt": None,
                "command_count": None,
                "failure_count": len(visual_result.get("errors") or [])
                if isinstance(visual_result.get("errors"), list)
                else None,
                "risk_flags": [],
                "at": _utc_iso(),
            },
        )
        _append_action_audit(
            artifacts=artifacts,
            event={
                "type": "visual_verification",
                "category": "visual",
                "status": visual_status,
                "summary": visual_message,
            },
        )
    coordinator["artifacts"] = artifacts
    metrics["coordinator"] = coordinator
    run.metrics = metrics
    db.add(run)
    db.commit()
    db.refresh(run)
    return _run_to_response(run, db)


async def _execute_verification_fix(
    *,
    db: DbSession,
    run: SessionRun,
    prompt: str,
) -> dict:
    from ..api.chat import _create_orchestrator, _run_orchestrator_once

    settings = get_settings()
    session = db.get(SessionModel, run.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    emitter = EventEmitter(
        session_id=run.session_id,
        run_id=run.id,
        event_store=EventStoreService(db),
    )
    orchestrator = _create_orchestrator(db, session, emitter)
    response, message = await _run_orchestrator_once(
        orchestrator=orchestrator,
        user_message=prompt,
        output_dir=settings.output_dir,
        history=[],
        trigger_interview=False,
        generate_now=True,
    )
    if response is not None and hasattr(response, "to_payload"):
        payload = response.to_payload()
        if isinstance(payload, dict):
            return payload
    return {"message": message}


@router.post("/{run_id}/fix-verification", response_model=RunResponse)
async def fix_verification(
    run_id: str,
    db: DbSession = Depends(_get_db_session),
    _: None = Depends(require_admin_token),
):
    _ensure_run_api_enabled()
    service = RunService(db)
    try:
        run = service.get_run(run_id)
    except RunNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc

    response = _run_to_response(run, db, redact=False)
    last_run = response.verification.last_run
    if last_run is None:
        raise HTTPException(status_code=409, detail="Run verification before requesting an automatic fix")
    if last_run.passed:
        raise HTTPException(status_code=409, detail="Last verification already passed")

    metrics = dict(run.metrics) if isinstance(run.metrics, dict) else {}
    coordinator = dict(metrics.get("coordinator") or {})
    artifacts = dict(coordinator.get("artifacts") or {})
    if _mark_stale_running_verification_fixes(artifacts):
        coordinator["artifacts"] = artifacts
        metrics["coordinator"] = coordinator
        run.metrics = metrics
        db.add(run)
        db.commit()
        db.refresh(run)
        metrics = dict(run.metrics) if isinstance(run.metrics, dict) else {}
        coordinator = dict(metrics.get("coordinator") or {})
        artifacts = dict(coordinator.get("artifacts") or {})
    existing_attempts = (
        list(artifacts.get("verification_fix_attempts"))
        if isinstance(artifacts.get("verification_fix_attempts"), list)
        else []
    )
    if not _try_acquire_verification_fix(run.id):
        raise HTTPException(status_code=409, detail="Verification fix is already running for this run")

    worktree_before = capture_worktree_files()

    async def execute(prompt: str) -> dict | None:
        return await _execute_verification_fix(db=db, run=run, prompt=prompt)

    async def verify_again() -> VerificationRunResult:
        refreshed = _run_to_response(run, db)
        return await VerificationRunner().run_profile(refreshed.verification.profile)

    async def persist_started(attempt: VerificationFixAttempt) -> None:
        _store_verification_fix_attempt(run=run, attempt=attempt, existing_attempts=existing_attempts)
        metrics = dict(run.metrics) if isinstance(run.metrics, dict) else {}
        coordinator = dict(metrics.get("coordinator") or {})
        stored_artifacts = dict(coordinator.get("artifacts") or {})
        _append_verification_audit(
            artifacts=stored_artifacts,
            event=_audit_event(
                type_="verification_fix_started",
                status="running",
                message="Automatic verification fix started.",
                attempt=attempt.attempt,
            ),
        )
        _append_action_audit(
            artifacts=stored_artifacts,
            event={
                "type": "verification_fix_prompt",
                "category": "agent_prompt",
                "status": "prepared",
                "summary": f"Prepared automatic fix prompt with {len(attempt.failures)} failure item(s).",
                "attempt": attempt.attempt,
            },
        )
        _append_action_audit(
            artifacts=stored_artifacts,
            event={
                "type": "verification_fix_started",
                "category": "agent",
                "status": "running",
                "summary": "Automatic verification fix started.",
                "attempt": attempt.attempt,
            },
        )
        coordinator["artifacts"] = stored_artifacts
        metrics["coordinator"] = coordinator
        run.metrics = metrics
        db.add(run)
        db.commit()
        db.refresh(run)
        existing_attempts[:] = (
            list(_coordinator_state(run).get("artifacts", {}).get("verification_fix_attempts") or [])
        )

    try:
        attempt = await VerificationFixService(executor=execute).run_fix(
            run_id=run.id,
            last_run=last_run,
            existing_attempts=existing_attempts,
            verifier=verify_again,
            on_started=persist_started,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    finally:
        _release_verification_fix(run.id)

    worktree_after = capture_worktree_files()
    attempt.change_summary = build_change_summary(
        before=worktree_before,
        after=worktree_after,
        verification_status=attempt.verification.status if attempt.verification is not None else attempt.status,
    )

    existing_attempts = list(_coordinator_state(run).get("artifacts", {}).get("verification_fix_attempts") or [])
    _store_verification_fix_attempt(run=run, attempt=attempt, existing_attempts=existing_attempts)
    metrics = dict(run.metrics) if isinstance(run.metrics, dict) else {}
    coordinator = dict(metrics.get("coordinator") or {})
    artifacts = dict(coordinator.get("artifacts") or {})
    if attempt.verification is not None:
        _append_verification_command_actions(artifacts=artifacts, result=attempt.verification)
    if attempt.change_summary is not None:
        _append_action_audit(
            artifacts=artifacts,
            event={
                "type": "verification_fix_change_summary",
                "category": "edit",
                "status": attempt.change_summary.status,
                "summary": (
                    f"{attempt.change_summary.file_count} file(s) changed; "
                    f"{attempt.change_summary.risk_level} risk."
                ),
                "attempt": attempt.attempt,
                "file_count": attempt.change_summary.file_count,
                "risk_level": attempt.change_summary.risk_level,
                "risk_flags": attempt.change_summary.risk_flags,
            },
        )
    _append_action_audit(
        artifacts=artifacts,
        event={
            "type": "verification_fix_completed",
            "category": "agent",
            "status": attempt.status,
            "summary": attempt.error or "Automatic verification fix completed.",
            "attempt": attempt.attempt,
        },
    )
    _append_verification_audit(
        artifacts=artifacts,
        event=_audit_event(
            type_="verification_fix_completed",
            status=attempt.status,
            message=attempt.error or "Automatic verification fix completed.",
            attempt=attempt.attempt,
            result=attempt.verification,
        ),
    )
    coordinator["artifacts"] = artifacts
    metrics["coordinator"] = coordinator
    run.metrics = metrics
    db.add(run)
    db.commit()
    db.refresh(run)
    return _run_to_response(run, db)


@router.get("/{run_id}/events", response_model=RunEventsResponse)
async def get_run_events(
    run_id: str,
    request: Request,
    since_seq: Optional[int] = Query(None, ge=0),
    limit: int = Query(1000, ge=1, le=5000),
    db: DbSession = Depends(_get_db_session),
):
    _ensure_run_api_enabled()
    run_service = RunService(db)
    try:
        run = run_service.get_run(run_id)
    except RunNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc

    accept = (request.headers.get("accept") or "").lower()
    wants_sse = "text/event-stream" in accept
    if wants_sse:
        return StreamingResponse(
            _stream_run_events(
                request=request,
                run_id=run_id,
                session_id=run.session_id,
                since_seq=since_seq,
            ),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    event_store = EventStoreService(db)
    events = event_store.get_events_by_run(
        run.session_id,
        run_id,
        since_seq=since_seq,
        limit=limit + 1,
    )
    has_more = len(events) > limit
    if has_more:
        events = events[:limit]

    serialized = [_serialize_event(event) for event in events]
    last_seq = serialized[-1].seq if serialized else (since_seq or 0)
    return RunEventsResponse(events=serialized, last_seq=last_seq, has_more=has_more)


async def _stream_run_events(
    *,
    request: Request,
    run_id: str,
    session_id: str,
    since_seq: Optional[int],
) -> AsyncGenerator[str, None]:
    database = get_database()
    last_seq = since_seq
    done = False
    last_keepalive = asyncio.get_running_loop().time()

    while True:
        if await request.is_disconnected():
            return

        with database.session() as db:
            run = db.get(SessionRun, run_id)
            if run is None:
                return
            event_store = EventStoreService(db)
            events = event_store.get_events_by_run(
                session_id,
                run_id,
                since_seq=last_seq,
                limit=200,
            )
            if run.status in TERMINAL_RUN_STATES:
                done = True

        if events:
            last_seq = events[-1].seq
            for event in events:
                payload = _serialize_event(event).model_dump(mode="json")
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.05)
            continue

        if done:
            break

        now = asyncio.get_running_loop().time()
        if now - last_keepalive >= 15:
            yield ": keepalive\n\n"
            last_keepalive = now
        await asyncio.sleep(0.5)

    yield "data: [DONE]\n\n"


__all__ = ["router"]
