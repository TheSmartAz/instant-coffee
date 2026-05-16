from __future__ import annotations

from datetime import datetime, timezone
import inspect
from typing import Any, Awaitable, Callable

from ..schemas.run import VerificationFixAttempt, VerificationRunResult


FixExecutor = Callable[[str], Awaitable[dict[str, Any] | None]]
AttemptStartedCallback = Callable[[VerificationFixAttempt], Awaitable[None] | None]


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def collect_verification_failures(result: VerificationRunResult | None) -> list[dict[str, Any]]:
    if result is None:
        return []
    failures: list[dict[str, Any]] = []
    for command in result.commands:
        for failure in command.failures:
            payload = dict(failure)
            payload.setdefault("command", command.command)
            payload.setdefault("scope", command.scope)
            payload.setdefault("check", command.name)
            failures.append(payload)
        if command.status != "passed" and not command.failures:
            failures.append(
                {
                    "command": command.command,
                    "scope": command.scope,
                    "check": command.name,
                    "message": command.output_summary[:1000],
                    "source": "verification",
                }
            )
    return failures[:25]


def build_verification_fix_prompt(result: VerificationRunResult, *, run_id: str) -> str:
    failures = collect_verification_failures(result)
    return (
        "The automatic verification pass failed for this run. Fix the failures below, "
        "then leave the project in a state where the same verification commands pass.\n"
        "Do not ask clarification questions. Make the smallest code changes needed and preserve existing behavior.\n\n"
        f"Run ID: {run_id}\n"
        f"Verification status: {result.status}\n\n"
        "Failures:\n"
        f"{_format_failures(failures)}\n\n"
        "Verification commands that must pass:\n"
        f"{_format_commands(result)}\n"
    )


def _format_failures(failures: list[dict[str, Any]]) -> str:
    if not failures:
        return "- No structured failures were parsed. Inspect command output summaries."
    lines: list[str] = []
    for failure in failures:
        location = str(failure.get("file") or "").strip()
        if failure.get("line") is not None:
            location = f"{location}:{failure['line']}" if location else f"line {failure['line']}"
        message = str(failure.get("message") or failure.get("source") or "verification failure").strip()
        command = str(failure.get("command") or "").strip()
        prefix = f"- {location}: " if location else "- "
        suffix = f" [{command}]" if command else ""
        lines.append(f"{prefix}{message}{suffix}")
    return "\n".join(lines)


def _format_commands(result: VerificationRunResult) -> str:
    lines = []
    for command in result.commands:
        lines.append(f"- ({command.scope}) {command.command}")
    return "\n".join(lines) if lines else "- No commands recorded."


class VerificationFixService:
    def __init__(
        self,
        *,
        max_attempts: int = 2,
        executor: FixExecutor | None = None,
    ) -> None:
        self.max_attempts = max(1, int(max_attempts))
        self.executor = executor

    async def run_fix(
        self,
        *,
        run_id: str,
        last_run: VerificationRunResult,
        existing_attempts: list[dict[str, Any]],
        verifier: Callable[[], Awaitable[VerificationRunResult]],
        on_started: AttemptStartedCallback | None = None,
    ) -> VerificationFixAttempt:
        attempt_number = len(existing_attempts) + 1
        if attempt_number > self.max_attempts:
            raise ValueError(f"Verification fix attempts exhausted after {self.max_attempts} attempt(s)")
        if last_run.passed:
            raise ValueError("Last verification run already passed")

        prompt = build_verification_fix_prompt(last_run, run_id=run_id)
        failures = collect_verification_failures(last_run)
        started_at = utc_iso()
        running_attempt = VerificationFixAttempt(
            attempt=attempt_number,
            status="running",
            prompt=prompt,
            failures=failures,
            started_at=started_at,
        )
        if on_started is not None:
            maybe_awaitable = on_started(running_attempt)
            if inspect.isawaitable(maybe_awaitable):
                await maybe_awaitable
        try:
            engine_result = await self.executor(prompt) if self.executor is not None else None
            verification = await verifier()
            return VerificationFixAttempt(
                attempt=attempt_number,
                status="passed" if verification.passed else "failed",
                prompt=prompt,
                failures=failures,
                engine=engine_result,
                verification=verification,
                started_at=started_at,
                completed_at=utc_iso(),
            )
        except Exception as exc:
            return VerificationFixAttempt(
                attempt=attempt_number,
                status="error",
                prompt=prompt,
                failures=failures,
                error=f"{type(exc).__name__}: {exc}",
                started_at=started_at,
                completed_at=utc_iso(),
            )


__all__ = [
    "VerificationFixService",
    "build_verification_fix_prompt",
    "collect_verification_failures",
]
