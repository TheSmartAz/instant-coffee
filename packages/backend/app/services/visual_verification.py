from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


class VisualVerificationService:
    """Runs a Playwright mobile smoke check against built static output."""

    def __init__(self, repo_root: Path | None = None, *, timeout_seconds: int = 60) -> None:
        self.repo_root = repo_root or _repo_root()
        self.timeout_seconds = timeout_seconds

    async def verify_dist(
        self,
        *,
        session_id: str,
        dist_path: str | None,
        page: str = "index.html",
    ) -> dict[str, Any]:
        started_at = _utc_iso()
        if not dist_path:
            return {
                "status": "skipped",
                "passed": None,
                "reason": "No build dist_path is available.",
                "started_at": started_at,
                "completed_at": _utc_iso(),
            }

        web_dir = self.repo_root / "packages" / "web"
        script = web_dir / "scripts" / "visual-check.mjs"
        if not script.exists():
            return {
                "status": "skipped",
                "passed": None,
                "reason": "Visual check script is missing.",
                "started_at": started_at,
                "completed_at": _utc_iso(),
            }
        if not (web_dir / "node_modules" / "playwright").exists():
            return {
                "status": "skipped",
                "passed": None,
                "reason": "Playwright is not installed in packages/web.",
                "started_at": started_at,
                "completed_at": _utc_iso(),
            }

        out_dir = Path(dist_path).expanduser().resolve().parent / "visual-check"
        command = [
            "node",
            str(script),
            "--dist",
            str(Path(dist_path).expanduser().resolve()),
            "--page",
            page,
            "--out",
            str(out_dir),
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *command,
                cwd=str(web_dir),
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
                return {
                    "status": "failed",
                    "passed": False,
                    "reason": f"Visual check timed out after {self.timeout_seconds}s.",
                    "started_at": started_at,
                    "completed_at": _utc_iso(),
                }
        except Exception as exc:
            return {
                "status": "failed",
                "passed": False,
                "reason": f"{type(exc).__name__}: {exc}",
                "started_at": started_at,
                "completed_at": _utc_iso(),
            }

        stdout = stdout_b.decode("utf-8", errors="replace").strip()
        stderr = stderr_b.decode("utf-8", errors="replace").strip()
        try:
            payload = json.loads(stdout)
            if not isinstance(payload, dict):
                raise ValueError("visual check output was not an object")
        except Exception:
            payload = {
                "status": "failed",
                "passed": False,
                "reason": "Visual check returned invalid JSON.",
                "stdout": stdout[-2000:],
                "stderr": stderr[-2000:],
            }

        payload.setdefault("status", "passed" if payload.get("passed") else "failed")
        payload.setdefault("passed", payload.get("status") == "passed")
        payload["exit_code"] = proc.returncode
        if stderr:
            payload["stderr"] = stderr[-2000:]
        payload["started_at"] = started_at
        payload["completed_at"] = _utc_iso()
        return payload


__all__ = ["VisualVerificationService"]
