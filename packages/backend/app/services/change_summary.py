from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Iterable

from ..schemas.run import VerificationChangeSummary
from .verification_fix import utc_iso


_HIGH_RISK_MARKERS = (
    "/auth",
    "/config",
    "/db/",
    "/migrations",
    "/security",
    "/settings",
)
_HIGH_RISK_FILES = {
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "requirements.txt",
    "pyproject.toml",
    "poetry.lock",
    "render.yaml",
}
_MEDIUM_RISK_MARKERS = (
    "/api/",
    "/services/",
    "/agents/",
    "/executor/",
    "/planner/",
    "/components/",
    "/hooks/",
    "/types/",
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def capture_worktree_files(root: Path | None = None) -> set[str]:
    root = root or repo_root()
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return set()
    if result.returncode != 0:
        return set()
    return {_parse_status_path(line) for line in result.stdout.splitlines() if _parse_status_path(line)}


def build_change_summary(
    *,
    before: Iterable[str],
    after: Iterable[str],
    verification_status: str | None,
) -> VerificationChangeSummary:
    changed_files = sorted(set(after) - set(before))
    risk_level, risk_flags = classify_change_risk(changed_files, verification_status=verification_status)
    return VerificationChangeSummary(
        status="captured",
        changed_files=changed_files,
        file_count=len(changed_files),
        risk_level=risk_level,
        risk_flags=risk_flags,
        verification_status=verification_status,
        captured_at=utc_iso(),
    )


def classify_change_risk(
    changed_files: Iterable[str],
    *,
    verification_status: str | None = None,
) -> tuple[str, list[str]]:
    files = sorted(set(changed_files))
    flags: list[str] = []
    level = "low"
    if not files:
        flags.append("no_files_changed")
    for path in files:
        normalized = path.replace("\\", "/")
        basename = normalized.rsplit("/", 1)[-1]
        lowered = f"/{normalized.lower()}"
        if basename in _HIGH_RISK_FILES or any(marker in lowered for marker in _HIGH_RISK_MARKERS):
            level = "high"
            flags.append("sensitive_files_changed")
            break
    if level != "high":
        for path in files:
            lowered = "/" + path.replace("\\", "/").lower()
            if any(marker in lowered for marker in _MEDIUM_RISK_MARKERS):
                level = "medium"
                flags.append("application_code_changed")
                break
    if files and all(_is_test_or_doc(path) for path in files):
        level = "low"
        flags.append("tests_or_docs_only")
    if verification_status and verification_status != "passed":
        flags.append("verification_not_passing")
        if level == "low":
            level = "medium"
    return level, sorted(set(flags))


def _is_test_or_doc(path: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    basename = normalized.rsplit("/", 1)[-1]
    return (
        normalized.startswith("docs/")
        or "/tests/" in normalized
        or basename.startswith("test_")
        or basename.endswith((".md", ".mdx"))
    )


def _parse_status_path(line: str) -> str:
    if not line.strip():
        return ""
    payload = line[3:] if len(line) > 3 else line.strip()
    if " -> " in payload:
        payload = payload.rsplit(" -> ", 1)[-1]
    return payload.strip().strip('"')


__all__ = [
    "build_change_summary",
    "capture_worktree_files",
    "classify_change_risk",
]
