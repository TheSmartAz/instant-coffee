import os
import multiprocessing
import queue
import traceback

import pytest
from fastapi.testclient import TestClient

from app.config import refresh_settings
from app.db.database import reset_database
from app.db.migrations import init_db
from app.db.models import SessionRun
from app.db.utils import get_db


def _smoke_timeout_seconds() -> float:
    raw = os.getenv("REAL_CHAT_ADAPTER_SMOKE_TIMEOUT", "180")
    try:
        value = float(raw)
    except ValueError:
        return 180.0
    return max(value, 1.0)


def _run_real_smoke_child(
    db_path: str,
    output_dir: str,
    timeout_seconds: float,
    result_queue,
    run_fix: bool = False,
) -> None:
    try:
        os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
        os.environ["OUTPUT_DIR"] = output_dir
        os.environ["CHAT_USE_RUN_ADAPTER"] = "true"
        os.environ["RUN_API_ENABLED"] = "true"
        os.environ["ADMIN_TOKEN"] = "real-smoke-admin"
        refresh_settings()
        reset_database()
        init_db()

        from app.main import create_app

        app = create_app()
        with TestClient(app) as client:
            chat_response = client.post(
                "/api/chat",
                json={
                    "message": (
                        "Create a simple single-page mobile landing page for a coffee cart. "
                        "Use one index page, no external assets, and proceed without questions."
                    ),
                    "generate_now": True,
                    "interview": False,
                },
                timeout=timeout_seconds,
            )
            run_id = None
            with get_db() as session:
                run = session.query(SessionRun).first()
                run_id = run.id if run is not None else None
            verification_response = (
                client.post(
                    f"/api/runs/{run_id}/verification",
                    headers={"X-Admin-Token": "real-smoke-admin"},
                    timeout=timeout_seconds,
                )
                if run_id
                else None
            )
            fix_response = None
            if run_fix and verification_response is not None and verification_response.status_code == 200:
                verification_body = verification_response.json()
                last_run = verification_body.get("verification", {}).get("last_run")
                if isinstance(last_run, dict) and last_run.get("passed") is False:
                    fix_response = client.post(
                        f"/api/runs/{run_id}/fix-verification",
                        headers={"X-Admin-Token": "real-smoke-admin"},
                        timeout=timeout_seconds,
                    )

        with get_db() as session:
            runs = session.query(SessionRun).all()
            run_payloads = [
                {
                    "id": run.id,
                    "status": run.status,
                    "metrics": run.metrics,
                }
                for run in runs
            ]

        result_queue.put(
            {
                "ok": True,
                "status_code": chat_response.status_code,
                "text": chat_response.text,
                "body": (
                    chat_response.json()
                    if chat_response.headers.get("content-type", "").startswith("application/json")
                    else {}
                ),
                "verification_status_code": verification_response.status_code if verification_response is not None else None,
                "verification_text": verification_response.text if verification_response is not None else "",
                "verification_body": (
                    verification_response.json()
                    if verification_response is not None
                    and verification_response.headers.get("content-type", "").startswith("application/json")
                    else {}
                ),
                "fix_status_code": fix_response.status_code if fix_response is not None else None,
                "fix_text": fix_response.text if fix_response is not None else "",
                "fix_body": (
                    fix_response.json()
                    if fix_response is not None
                    and fix_response.headers.get("content-type", "").startswith("application/json")
                    else {}
                ),
                "runs": run_payloads,
            }
        )
    except BaseException:
        result_queue.put({"ok": False, "traceback": traceback.format_exc()})


@pytest.mark.skipif(
    os.getenv("RUN_REAL_CHAT_ADAPTER_SMOKE") != "true",
    reason="Set RUN_REAL_CHAT_ADAPTER_SMOKE=true to run the real provider smoke test.",
)
def test_real_chat_run_adapter_smoke(tmp_path) -> None:
    if not (os.getenv("DEEPSEEK_API_KEY") or os.getenv("DEFAULT_KEY")):
        pytest.skip("DEEPSEEK_API_KEY or DEFAULT_KEY is required for real provider smoke.")

    timeout_seconds = _smoke_timeout_seconds()
    db_path = str(tmp_path / "real-chat-adapter-smoke.db")
    output_dir = str(tmp_path / "output")
    ctx = multiprocessing.get_context("spawn")
    result_queue = ctx.Queue()
    process = ctx.Process(
        target=_run_real_smoke_child,
        args=(db_path, output_dir, timeout_seconds, result_queue),
    )
    process.start()
    process.join(timeout_seconds + 5)
    if process.is_alive():
        process.terminate()
        process.join(5)
        if process.is_alive():
            process.kill()
            process.join(5)
        pytest.fail(f"Real chat adapter smoke exceeded {timeout_seconds:g}s and was terminated")

    try:
        result = result_queue.get(timeout=1)
    except queue.Empty:
        pytest.fail(f"Real chat adapter smoke exited without a result, exitcode={process.exitcode}")

    assert result["ok"] is True, result.get("traceback")
    assert result["status_code"] == 200, result["text"]
    body = result["body"]
    assert body["session_id"]
    assert body.get("message")
    assert len(result["runs"]) == 1
    run = result["runs"][0]
    assert run["status"] in {"completed", "waiting_input", "failed"}
    assert isinstance(run["metrics"], dict)
    assert "coordinator" in run["metrics"]
    assert result["verification_status_code"] == 200, result["verification_text"]
    verification = result["verification_body"]["verification"]
    assert verification["last_run"] is not None
    assert verification["last_run"]["status"] in {"passed", "failed"}
    assert verification["action_audit_trail"]


@pytest.mark.skipif(
    os.getenv("RUN_REAL_VERIFICATION_FIX_DOGFOOD") != "true",
    reason="Set RUN_REAL_VERIFICATION_FIX_DOGFOOD=true to run real automatic-fix dogfood.",
)
@pytest.mark.skipif(
    os.getenv("ALLOW_REAL_FIX_WORKTREE_EDIT") != "true",
    reason="Set ALLOW_REAL_FIX_WORKTREE_EDIT=true to acknowledge real fix may edit the live worktree.",
)
def test_real_chat_run_adapter_verification_fix_dogfood(tmp_path) -> None:
    if not (os.getenv("DEEPSEEK_API_KEY") or os.getenv("DEFAULT_KEY")):
        pytest.skip("DEEPSEEK_API_KEY or DEFAULT_KEY is required for real automatic-fix dogfood.")

    timeout_seconds = _smoke_timeout_seconds()
    db_path = str(tmp_path / "real-verification-fix-dogfood.db")
    output_dir = str(tmp_path / "output")
    ctx = multiprocessing.get_context("spawn")
    result_queue = ctx.Queue()
    process = ctx.Process(
        target=_run_real_smoke_child,
        args=(db_path, output_dir, timeout_seconds, result_queue, True),
    )
    process.start()
    process.join(timeout_seconds + 5)
    if process.is_alive():
        process.terminate()
        process.join(5)
        if process.is_alive():
            process.kill()
            process.join(5)
        pytest.fail(f"Real verification-fix dogfood exceeded {timeout_seconds:g}s and was terminated")

    try:
        result = result_queue.get(timeout=1)
    except queue.Empty:
        pytest.fail(f"Real verification-fix dogfood exited without a result, exitcode={process.exitcode}")

    assert result["ok"] is True, result.get("traceback")
    assert result["status_code"] == 200, result["text"]
    assert result["verification_status_code"] == 200, result["verification_text"]
    verification = result["verification_body"]["verification"]
    last_run = verification["last_run"]
    assert last_run is not None
    if last_run["passed"] is not False:
        pytest.skip("Real verification passed; automatic-fix dogfood requires a failed verification run.")

    assert result["fix_status_code"] == 200, result["fix_text"]
    fixed_verification = result["fix_body"]["verification"]
    assert fixed_verification["fix_attempts"]
    attempt = fixed_verification["fix_attempts"][-1]
    assert attempt["status"] in {"passed", "failed", "error"}
    assert attempt["prompt"] == ""
    assert attempt["engine"] is None
    assert "action_audit_trail" in fixed_verification
