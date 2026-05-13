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
) -> None:
    try:
        os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
        os.environ["OUTPUT_DIR"] = output_dir
        os.environ["CHAT_USE_RUN_ADAPTER"] = "true"
        os.environ["RUN_API_ENABLED"] = "true"
        refresh_settings()
        reset_database()
        init_db()

        from app.main import create_app

        app = create_app()
        with TestClient(app) as client:
            response = client.post(
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

        with get_db() as session:
            runs = session.query(SessionRun).all()
            run_payloads = [
                {
                    "status": run.status,
                    "metrics": run.metrics,
                }
                for run in runs
            ]

        result_queue.put(
            {
                "ok": True,
                "status_code": response.status_code,
                "text": response.text,
                "body": response.json() if response.headers.get("content-type", "").startswith("application/json") else {},
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
