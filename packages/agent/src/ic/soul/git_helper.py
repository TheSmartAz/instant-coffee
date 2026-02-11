"""Git helper functions for context injection."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class GitStatus:
    """Git repository status summary."""

    branch: str = ""
    has_changes: bool = False
    staged: list[str] = ()
    modified: list[str] = ()
    untracked: list[str] = ()
    recent_commits: list[str] = ()

    def format(self) -> str:
        """Format as markdown for LLM consumption."""
        lines = []
        if self.branch:
            lines.append(f"**Branch**: `{self.branch}`")

        if self.recent_commits:
            lines.append("**Recent commits**:")
            for commit in self.recent_commits[:5]:
                lines.append(f"  - {commit}")

        if self.has_changes:
            lines.append("**Uncommitted changes**:")
            if self.staged:
                lines.append("  *Staged*:")
                lines.extend(f"    - {f}" for f in self.staged)
            if self.modified:
                lines.append("  *Modified*:")
                lines.extend(f"    - {f}" for f in self.modified)
            if self.untracked:
                lines.append("  *Untracked*:")
                lines.extend(f"    - {f}" for f in self.untracked[:10])  # Limit untracked
                if len(self.untracked) > 10:
                    lines.append(f"    - ... and {len(self.untracked) - 10} more")
        else:
            lines.append("*Working directory clean*")

        return "\n".join(lines)


def is_git_repo(directory: Path) -> bool:
    """Check if directory is inside a git repository."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=directory,
            capture_output=True,
            timeout=2,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def get_git_status(directory: Path, max_commits: int = 5) -> Optional[GitStatus]:
    """Get git status of a directory.

    Returns None if not a git repo or git command fails.
    """
    if not is_git_repo(directory):
        return None

    try:
        # Get current branch
        branch = ""
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=directory,
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            branch = result.stdout.strip()

        # Get status in porcelain format
        staged = []
        modified = []
        untracked = []

        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=directory,
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if not line:
                    continue
                status, path = line[:2], line[3:]
                if status.startswith("??"):
                    untracked.append(path)
                elif "M" in status:
                    if status[0] == "M":
                        staged.append(path)
                    if status[1] == "M" or status == " M":
                        modified.append(path)

        # Get recent commits
        recent_commits = []
        result = subprocess.run(
            ["git", "log", f"-{max_commits}", "--pretty=format:%h %s"],
            cwd=directory,
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            recent_commits = result.stdout.strip().split("\n")

        return GitStatus(
            branch=branch,
            has_changes=bool(staged or modified or untracked),
            staged=staged,
            modified=modified,
            untracked=untracked,
            recent_commits=recent_commits,
        )

    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        return None
