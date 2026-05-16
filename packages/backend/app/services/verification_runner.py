from __future__ import annotations

import asyncio
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..schemas.run import VerificationCommandResult, VerificationRunResult


_ALLOWED_COMMANDS = {
    "PYTHONPATH=.:../agent/src python -m pytest -q",
    "npm run lint",
    "npm run build",
    "npx playwright test",
}

_PYTEST_FAILURE_RE = re.compile(r"^(?P<file>[^:\s]+\.py):(?P<line>\d+):")
_TS_FAILURE_RE = re.compile(r"(?P<file>[^()\s]+\.(?:ts|tsx|js|jsx))\((?P<line>\d+),(?P<column>\d+)\):\s*(?P<message>.+)")
_ESLINT_FAILURE_RE = re.compile(r"^\s*(?P<line>\d+):(?P<column>\d+)\s+(?P<severity>error|warning)\s+(?P<message>.+)$")

_FIX_HINTS = {
    "pytest": "Fix the failing Python test or the backend behavior it protects, then rerun backend tests.",
    "typescript": "Fix the TypeScript type or contract mismatch, then rerun the web build.",
    "eslint": "Fix the lint rule violation without weakening lint configuration, then rerun web lint.",
    "playwright": "Fix the browser-visible behavior or selector failure, then rerun the Playwright check.",
    "build": "Fix the build or bundling failure, then rerun the build command.",
    "runner": "Fix the verification runner or environment error before retrying verification.",
    "verification": "Inspect the command summary and fix the failing verification evidence.",
}


def route_failure(*, command: str = "", source: str = "", output: str = "") -> dict[str, str]:
    source = source.lower().strip()
    command = command.lower().strip()
    output_lower = output.lower()
    if source == "pytest" or "pytest" in command:
        route = "pytest"
        kind = "backend_test"
    elif source == "typescript" or "tsc" in output_lower or "error ts" in output_lower:
        route = "typescript"
        kind = "typecheck"
    elif source == "eslint" or "lint" in command:
        route = "eslint"
        kind = "lint"
    elif "playwright" in command or source == "playwright":
        route = "playwright"
        kind = "browser_e2e"
    elif "build" in command:
        route = "build"
        kind = "build"
    elif source == "runner":
        route = "runner"
        kind = "runner"
    else:
        route = "verification"
        kind = "verification"
    return {
        "route": route,
        "kind": kind,
        "fix_hint": _FIX_HINTS[route],
    }


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _summarize_output(stdout: str, stderr: str, *, limit: int = 4000) -> str:
    output = "\n".join(part for part in (stdout.strip(), stderr.strip()) if part)
    if len(output) <= limit:
        return output
    half = limit // 2
    return f"{output[:half]}\n\n... [{len(output) - limit} chars omitted] ...\n\n{output[-half:]}"


def parse_failures(command: str, output: str) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    current_file: str | None = None
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.endswith((".ts", ".tsx", ".js", ".jsx")) and "/" in stripped:
            current_file = stripped
            continue
        pytest_match = _PYTEST_FAILURE_RE.search(stripped)
        if pytest_match:
            routed = route_failure(command=command, source="pytest", output=stripped)
            failures.append(
                {
                    "file": pytest_match.group("file"),
                    "line": int(pytest_match.group("line")),
                    "message": stripped,
                    "source": "pytest",
                    **routed,
                }
            )
            continue
        ts_match = _TS_FAILURE_RE.search(stripped)
        if ts_match:
            routed = route_failure(command=command, source="typescript", output=stripped)
            failures.append(
                {
                    "file": ts_match.group("file"),
                    "line": int(ts_match.group("line")),
                    "column": int(ts_match.group("column")),
                    "message": ts_match.group("message"),
                    "source": "typescript",
                    **routed,
                }
            )
            continue
        eslint_match = _ESLINT_FAILURE_RE.search(line)
        if eslint_match and current_file:
            routed = route_failure(command=command, source="eslint", output=line)
            failures.append(
                {
                    "file": current_file,
                    "line": int(eslint_match.group("line")),
                    "column": int(eslint_match.group("column")),
                    "severity": eslint_match.group("severity"),
                    "message": eslint_match.group("message").strip(),
                    "source": "eslint",
                    **routed,
                }
            )
    if not failures and output and "failed" in output.lower():
        failures.append(
            {
                "message": output.splitlines()[-1][:500],
                "source": "command",
                **route_failure(command=command, output=output),
            }
        )
    return failures[:25]


class VerificationRunner:
    def __init__(self, repo_root: Path | None = None, *, timeout_seconds: int = 180) -> None:
        self.repo_root = repo_root or Path(__file__).resolve().parents[4]
        self.timeout_seconds = timeout_seconds

    def _workdir(self, scope: str) -> Path:
        if scope == "backend":
            return self.repo_root / "packages" / "backend"
        if scope == "web":
            return self.repo_root / "packages" / "web"
        return self.repo_root

    async def run_profile(self, profile: dict[str, Any]) -> VerificationRunResult:
        started_at = _utc_iso()
        results: list[VerificationCommandResult] = []
        commands = profile.get("recommended_commands")
        if not isinstance(commands, list):
            commands = []

        for item in commands:
            if not isinstance(item, dict):
                continue
            command = str(item.get("command") or "")
            if command not in _ALLOWED_COMMANDS:
                results.append(
                    VerificationCommandResult(
                        name=str(item.get("name") or "verification"),
                        command=command,
                        scope=str(item.get("scope") or "repo"),
                        status="skipped",
                        output_summary="Command is not in the verification allowlist.",
                    )
                )
                continue
            results.append(await self._run_command(item))

        passed = bool(results) and all(result.status == "passed" for result in results)
        risk_flags = [str(flag) for flag in profile.get("risk_flags") or []]
        if any(result.status == "failed" for result in results):
            risk_flags.append("verification_failed")
        if any(result.status == "timeout" for result in results):
            risk_flags.append("verification_timeout")

        return VerificationRunResult(
            status="passed" if passed else "failed",
            passed=passed,
            commands=results,
            risk_flags=sorted(set(risk_flags)),
            started_at=started_at,
            completed_at=_utc_iso(),
        )

    async def _run_command(self, item: dict[str, Any]) -> VerificationCommandResult:
        command = str(item.get("command") or "")
        scope = str(item.get("scope") or "repo")
        started = time.perf_counter()
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                cwd=str(self._workdir(scope)),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout_b, stderr_b = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=self.timeout_seconds,
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return VerificationCommandResult(
                    name=str(item.get("name") or command),
                    command=command,
                    scope=scope,
                    status="timeout",
                    exit_code=None,
                    duration_ms=int((time.perf_counter() - started) * 1000),
                    output_summary=f"Command timed out after {self.timeout_seconds}s.",
                )
        except Exception as exc:
            return VerificationCommandResult(
                name=str(item.get("name") or command),
                command=command,
                scope=scope,
                status="failed",
                duration_ms=int((time.perf_counter() - started) * 1000),
                output_summary=f"{type(exc).__name__}: {exc}",
                failures=[{"message": str(exc), "source": "runner", **route_failure(command=command, source="runner")}],
            )

        stdout = stdout_b.decode("utf-8", errors="replace")
        stderr = stderr_b.decode("utf-8", errors="replace")
        summary = _summarize_output(stdout, stderr)
        return VerificationCommandResult(
            name=str(item.get("name") or command),
            command=command,
            scope=scope,
            status="passed" if proc.returncode == 0 else "failed",
            exit_code=proc.returncode,
            duration_ms=int((time.perf_counter() - started) * 1000),
            output_summary=summary,
            failures=parse_failures(command, summary) if proc.returncode else [],
        )


__all__ = ["VerificationRunner", "parse_failures", "route_failure"]
