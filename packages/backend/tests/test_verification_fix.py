import asyncio

from app.schemas.run import VerificationRunResult
from app.services.change_summary import build_change_summary, classify_change_risk
from app.services.verification_fix import (
    VerificationFixService,
    build_verification_fix_prompt,
    collect_verification_failures,
)


def test_build_verification_fix_prompt_includes_failures_and_commands() -> None:
    result = VerificationRunResult(
        status="failed",
        passed=False,
        commands=[
            {
                "name": "backend targeted tests",
                "command": "PYTHONPATH=.:../agent/src python -m pytest -q",
                "scope": "backend",
                "status": "failed",
                "output_summary": "app/api/runs.py:42: AssertionError",
                "failures": [
                    {
                        "file": "app/api/runs.py",
                        "line": 42,
                        "message": "AssertionError",
                        "source": "pytest",
                    }
                ],
            }
        ],
    )

    failures = collect_verification_failures(result)
    prompt = build_verification_fix_prompt(result, run_id="run-123")

    assert failures[0]["command"] == "PYTHONPATH=.:../agent/src python -m pytest -q"
    assert failures[0]["scope"] == "backend"
    assert "run-123" in prompt
    assert "app/api/runs.py:42" in prompt
    assert "AssertionError" in prompt
    assert "PYTHONPATH=.:../agent/src python -m pytest -q" in prompt


def test_verification_fix_service_reports_running_before_final_status() -> None:
    result = VerificationRunResult(
        status="failed",
        passed=False,
        commands=[
            {
                "name": "web lint",
                "command": "npm run lint",
                "scope": "web",
                "status": "failed",
                "output_summary": "lint failed",
                "failures": [{"message": "lint failed", "source": "eslint"}],
            }
        ],
    )
    started_statuses: list[str] = []

    async def executor(prompt: str):
        assert "lint failed" in prompt
        return {"message": "fixed"}

    async def verifier():
        return VerificationRunResult(status="passed", passed=True, commands=[])

    async def on_started(attempt):
        started_statuses.append(attempt.status)

    attempt = asyncio.run(
        VerificationFixService(executor=executor).run_fix(
            run_id="run-123",
            last_run=result,
            existing_attempts=[],
            verifier=verifier,
            on_started=on_started,
        )
    )

    assert started_statuses == ["running"]
    assert attempt.status == "passed"


def test_change_summary_reports_only_new_files_since_baseline() -> None:
    summary = build_change_summary(
        before={"packages/backend/app/api/runs.py", "docs/coding-agent-capabilities.md"},
        after={
            "packages/backend/app/api/runs.py",
            "docs/coding-agent-capabilities.md",
            "packages/backend/app/services/change_summary.py",
            "packages/backend/tests/test_verification_fix.py",
        },
        verification_status="passed",
    )

    assert summary.changed_files == [
        "packages/backend/app/services/change_summary.py",
        "packages/backend/tests/test_verification_fix.py",
    ]
    assert summary.file_count == 2
    assert summary.risk_level == "medium"
    assert summary.verification_status == "passed"


def test_change_summary_risk_classification_handles_sensitive_and_failed_verification() -> None:
    risk_level, flags = classify_change_risk(
        ["packages/backend/app/api/auth.py", "packages/backend/requirements.txt"],
        verification_status="failed",
    )

    assert risk_level == "high"
    assert "sensitive_files_changed" in flags
    assert "verification_not_passing" in flags
