"""File operation tools: read, write, edit, multiedit, glob, grep.

All file tools resolve relative paths against the workspace directory.
Write operations are sandboxed to the workspace.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ic.tools.base import (
    BaseTool,
    ToolParam,
    ToolResult,
    ToolCompleteEvent,
    ToolProgressEvent,
)


def _resolve(file_path: str, workspace: Path | None) -> Path:
    """Resolve a file path. Relative paths resolve against workspace."""
    p = Path(file_path).expanduser()
    if not p.is_absolute() and workspace:
        p = workspace / p
    return p.resolve()


def _check_sandbox(path: Path, workspace: Path | None) -> str | None:
    """Check if path is within workspace. Returns error message or None."""
    if workspace is None:
        return None
    try:
        path.resolve().relative_to(workspace.resolve())
        return None
    except ValueError:
        return f"Path {path} is outside workspace {workspace}"


class ReadFile(BaseTool):
    name = "read_file"
    description = "Read the contents of a file. Returns the file content with line numbers."
    is_concurrent_safe = True
    parameters = [
        ToolParam(name="file_path", description="Path to the file (relative to workspace or absolute)"),
        ToolParam(name="offset", type="integer", description="Line number to start from (1-based)", required=False),
        ToolParam(name="limit", type="integer", description="Max number of lines to read", required=False),
    ]

    def __init__(self, workspace: Path | None = None):
        self._workspace = workspace

    async def execute(self, **kwargs: Any) -> ToolResult:
        path = _resolve(kwargs["file_path"], self._workspace)
        if not path.exists():
            return ToolResult(error=f"File not found: {path}", is_error=True)
        if not path.is_file():
            return ToolResult(error=f"Not a file: {path}", is_error=True)
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            lines = text.splitlines()
            offset = int(kwargs.get("offset", 1) or 1)
            limit = kwargs.get("limit")
            if limit:
                limit = int(limit)
            start = max(0, offset - 1)
            end = start + limit if limit else len(lines)
            numbered = [f"{i+start+1:>6}\t{line}" for i, line in enumerate(lines[start:end])]
            return ToolResult(output="\n".join(numbered))
        except Exception as e:
            return ToolResult(error=str(e), is_error=True)


class WriteFile(BaseTool):
    name = "write_file"
    description = "Write content to a file inside the workspace. Creates parent directories if needed."
    parameters = [
        ToolParam(name="file_path", description="Path relative to workspace (e.g. 'src/index.html')"),
        ToolParam(name="content", description="The content to write to the file"),
    ]

    def __init__(self, workspace: Path | None = None, engine: Any = None):
        self._workspace = workspace
        self._engine = engine

    async def execute(self, **kwargs: Any) -> ToolResult:
        path = _resolve(kwargs["file_path"], self._workspace)
        if err := _check_sandbox(path, self._workspace):
            return ToolResult(error=err, is_error=True)
        existed = path.exists()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(kwargs["content"], encoding="utf-8")
            lines = kwargs["content"].count("\n") + 1
            # Record file change
            if self._engine and hasattr(self._engine, "record_file_change"):
                action = "modified" if existed else "created"
                self._engine.record_file_change(
                    str(path), action, f"{lines} lines written"
                )
            return ToolResult(output=f"Wrote {lines} lines to {path}")
        except Exception as e:
            return ToolResult(error=str(e), is_error=True)


class EditFile(BaseTool):
    name = "edit_file"
    description = "Replace an exact string in a file. The old_string must match exactly once."
    parameters = [
        ToolParam(name="file_path", description="Path to the file to edit"),
        ToolParam(name="old_string", description="The exact string to find and replace"),
        ToolParam(name="new_string", description="The replacement string"),
    ]

    def __init__(self, workspace: Path | None = None, engine: Any = None):
        self._workspace = workspace
        self._engine = engine

    async def execute(self, **kwargs: Any) -> ToolResult:
        path = _resolve(kwargs["file_path"], self._workspace)
        if err := _check_sandbox(path, self._workspace):
            return ToolResult(error=err, is_error=True)
        if not path.exists():
            return ToolResult(error=f"File not found: {path}", is_error=True)
        try:
            content = path.read_text(encoding="utf-8")
            old, new = kwargs["old_string"], kwargs["new_string"]
            count = content.count(old)
            if count == 0:
                return ToolResult(error="old_string not found in file", is_error=True)
            if count > 1:
                return ToolResult(error=f"old_string found {count} times. Provide more context.", is_error=True)
            path.write_text(content.replace(old, new, 1), encoding="utf-8")
            # Record file change
            if self._engine and hasattr(self._engine, "record_file_change"):
                self._engine.record_file_change(str(path), "modified", "edited")
            return ToolResult(output=f"Edited {path}")
        except Exception as e:
            return ToolResult(error=str(e), is_error=True)


class GlobFiles(BaseTool):
    name = "glob_files"
    description = "Find files matching a glob pattern in the workspace."
    is_concurrent_safe = True
    parameters = [
        ToolParam(name="pattern", description="Glob pattern (e.g. '**/*.py', 'src/**/*.ts')"),
        ToolParam(name="path", description="Directory to search in (default: workspace)", required=False),
    ]

    def __init__(self, workspace: Path | None = None):
        self._workspace = workspace

    async def execute(self, **kwargs: Any) -> ToolResult:
        base = _resolve(kwargs.get("path", "."), self._workspace)
        try:
            matches = sorted(str(p) for p in base.glob(kwargs["pattern"]) if p.is_file())
            if not matches:
                return ToolResult(output="No files matched.")
            return ToolResult(output="\n".join(matches[:200]))
        except Exception as e:
            return ToolResult(error=str(e), is_error=True)


class GrepFiles(BaseTool):
    name = "grep_files"
    description = "Search file contents using regex in the workspace."
    is_concurrent_safe = True
    parameters = [
        ToolParam(name="pattern", description="Regex pattern to search for"),
        ToolParam(name="path", description="File or directory to search in (default: workspace)", required=False),
        ToolParam(name="glob", description="File glob filter (e.g. '*.py')", required=False),
    ]

    def __init__(self, workspace: Path | None = None):
        self._workspace = workspace

    async def execute(self, **kwargs: Any) -> ToolResult:
        pattern = kwargs["pattern"]
        path = str(_resolve(kwargs.get("path", "."), self._workspace))
        file_glob = kwargs.get("glob")
        try:
            cmd = ["rg", "--no-heading", "-n", "--max-count=50", pattern, path]
            if file_glob:
                cmd.extend(["--glob", file_glob])
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                return ToolResult(output=result.stdout[:10000])
            if result.returncode == 1:
                return ToolResult(output="No matches found.")
            return ToolResult(output=self._python_grep(pattern, path, file_glob))
        except FileNotFoundError:
            return ToolResult(output=self._python_grep(pattern, path, file_glob))
        except Exception as e:
            return ToolResult(error=str(e), is_error=True)

    def _python_grep(self, pattern: str, path: str, file_glob: str | None) -> str:
        base = Path(path).resolve()
        regex = re.compile(pattern)
        results = []
        for fp in base.glob(file_glob or "**/*"):
            if not fp.is_file():
                continue
            try:
                for i, line in enumerate(fp.read_text(errors="replace").splitlines(), 1):
                    if regex.search(line):
                        results.append(f"{fp}:{i}:{line}")
                        if len(results) >= 50:
                            return "\n".join(results)
            except Exception:
                continue
        return "\n".join(results) if results else "No matches found."


@dataclass
class EditOperation:
    """A single edit operation for MultiEdit."""

    old_string: str
    new_string: str


class MultiEditFile(BaseTool):
    """Edit multiple locations in a file at once.

    Applies multiple edits in a single operation to avoid cascading failures.
    Edits are applied in reverse order to prevent offset issues.
    All edits are validated before any changes are made.
    """

    name = "multi_edit_file"
    description = (
        "Edit multiple locations in a file at once. "
        "All edits are validated before any changes are made. "
        "Use this when you need to make multiple changes to the same file."
    )
    parameters = [
        ToolParam(
            name="file_path",
            description="Path to the file to edit (relative to workspace)",
        ),
        ToolParam(
            name="edits",
            description="List of edit operations, each with old_string and new_string",
        ),
    ]

    def __init__(self, workspace: Path | None = None):
        super().__init__()
        self._workspace = workspace

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute (simple interface for backward compatibility)."""
        async for event in self.execute_stream(**kwargs):
            if isinstance(event, ToolCompleteEvent):
                return ToolResult(output=event.output)
        return ToolResult(output="")

    async def execute_stream(self, **kwargs):
        """Execute with streaming progress."""
        path = _resolve(kwargs["file_path"], self._workspace)
        if err := _check_sandbox(path, self._workspace):
            yield ToolCompleteEvent(output=err)
            return

        if not path.exists():
            yield ToolCompleteEvent(output=f"File not found: {path}")
            return

        edits_input = kwargs.get("edits", [])
        if not edits_input:
            yield ToolCompleteEvent(output="No edits provided")
            return

        # Parse edits
        edits = []
        for i, edit in enumerate(edits_input):
            if isinstance(edit, dict):
                old_str = edit.get("old_string", "")
                new_str = edit.get("new_string", "")
                if not old_str:
                    yield ToolCompleteEvent(
                        output=f"Edit {i}: old_string is required"
                    )
                    return
                edits.append(EditOperation(old_str, new_str))

        if not edits:
            yield ToolCompleteEvent(output="No valid edits provided")
            return

        await self._emit_progress(
            f"Validating {len(edits)} edits...",
            10
        )

        # Read file content
        try:
            content = path.read_text(encoding="utf-8")
        except Exception as e:
            yield ToolCompleteEvent(output=f"Error reading file: {e}")
            return

        # Validate all edits first
        await self._emit_progress("Validating edits...", 30)
        validation_results = []
        for i, edit in enumerate(edits):
            count = content.count(edit.old_string)
            if count == 0:
                validation_results.append(
                    f"Edit {i+1}: old_string not found in file"
                )
            elif count > 1:
                validation_results.append(
                    f"Edit {i+1}: old_string found {count} times (must be unique)"
                )

        if validation_results:
            yield ToolCompleteEvent(
                output="Validation failed:\n" + "\n".join(validation_results)
            )
            return

        # Apply edits in reverse order to avoid offset issues
        await self._emit_progress("Applying edits...", 50)
        modified_content = content
        total = len(edits)

        for i, edit in enumerate(reversed(edits)):
            if edit.old_string in modified_content:
                modified_content = modified_content.replace(
                    edit.old_string,
                    edit.new_string,
                    1,
                )
                await self._emit_progress(
                    f"Applied {total-i}/{total} edits...",
                    50 + (i + 1) * 40 // total
                )

        # Write result
        await self._emit_progress("Writing file...", 90)
        try:
            path.write_text(modified_content, encoding="utf-8")
            lines_changed = sum(
                e.new_string.count("\n") - e.old_string.count("\n") for e in edits
            )
            await self._emit_progress("Complete!", 100)
            yield ToolCompleteEvent(
                output=f"Applied {len(edits)} edits to {path} "
                f"({lines_changed:+d} lines change)"
            )
        except Exception as e:
            yield ToolCompleteEvent(output=f"Error writing file: {e}")
