import os
import signal
from contextlib import contextmanager

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


@contextmanager
def _deadline(seconds: float):
    if not hasattr(signal, "SIGALRM"):
        yield
        return

    def _raise_timeout(_signum, _frame):
        raise TimeoutError(f"Real chat adapter smoke exceeded {seconds:g}s")

    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.setitimer(signal.ITIMER_REAL, seconds)
    signal.signal(signal.SIGALRM, _raise_timeout)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        if previous_timer[0] > 0:
            signal.setitimer(signal.ITIMER_REAL, previous_timer[0], previous_timer[1])


@pytest.mark.skipif(
    os.getenv("RUN_REAL_CHAT_ADAPTER_SMOKE") != "true",
    reason="Set RUN_REAL_CHAT_ADAPTER_SMOKE=true to run the real provider smoke test.",
)
def test_real_chat_run_adapter_smoke(tmp_path, monkeypatch) -> None:
    if not (os.getenv("DEEPSEEK_API_KEY") or os.getenv("DEFAULT_KEY")):
        pytest.skip("DEEPSEEK_API_KEY or DEFAULT_KEY is required for real provider smoke.")

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'real-chat-adapter-smoke.db'}")
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "output"))
    monkeypatch.setenv("CHAT_USE_RUN_ADAPTER", "true")
    monkeypatch.setenv("RUN_API_ENABLED", "true")
    refresh_settings()
    reset_database()
    init_db()

    from app.main import create_app

    app = create_app()
    timeout_seconds = _smoke_timeout_seconds()
    with TestClient(app) as client:
        with _deadline(timeout_seconds):
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

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["session_id"]
    assert body.get("message")

    with get_db() as session:
        runs = session.query(SessionRun).all()
        assert len(runs) == 1
        run = runs[0]
        assert run.status in {"completed", "waiting_input", "failed"}
        assert isinstance(run.metrics, dict)
        assert "coordinator" in run.metrics
