"""Rich console output for the CLI agent."""

from __future__ import annotations

import json
import time
from typing import Any

from rich.console import Console as RichConsole, RenderableType
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.spinner import Spinner
from rich.syntax import Syntax
from rich.text import Text


def _tool_call_summary(name: str, args: dict[str, Any]) -> str:
    """Build a compact one-line summary for a tool call."""
    if name in ("write_file", "read_file", "edit_file", "multi_edit_file"):
        path = args.get("file_path", args.get("path", ""))
        # Show just the filename, not the full path
        short = path.rsplit("/", 1)[-1] if "/" in path else path
        verb = {"write_file": "Writing", "read_file": "Reading",
                "edit_file": "Editing", "multi_edit_file": "Editing"}
        return f"{verb.get(name, name)} {short}"
    if name == "shell":
        cmd = args.get("command", "")
        if len(cmd) > 60:
            cmd = cmd[:57] + "..."
        return f"Running: {cmd}"
    if name == "glob_files":
        pattern = args.get("pattern", "*")
        return f"Searching files: {pattern}"
    if name == "grep_files":
        pattern = args.get("pattern", "")
        return f'Searching for: "{pattern[:40]}"'
    if name == "think":
        thought = args.get("thought", "")
        if len(thought) > 50:
            thought = thought[:47] + "..."
        return f"Thinking: {thought}"
    if name == "todo":
        return "Updating task list"
    if name == "create_sub_agent":
        task = args.get("task", "")
        if len(task) > 50:
            task = task[:47] + "..."
        return f"Sub-agent: {task}"
    if name == "web_search":
        query = args.get("query", "")
        return f"Searching: {query[:50]}"
    if name == "web_fetch":
        url = args.get("url", "")
        return f"Fetching: {url[:50]}"
    if name == "update_plan":
        return "Updating plan"
    # Fallback: tool name + first string arg
    for v in args.values():
        if isinstance(v, str) and v:
            short = v[:50] + "..." if len(v) > 50 else v
            return f"{name}: {short}"
    return name


def _tool_result_summary(name: str, result: str, is_error: bool) -> str:
    """Build a compact one-line summary for a tool result."""
    if is_error:
        # Show first line of error
        first_line = result.split("\n")[0][:80]
        return f"[red]{name}: {first_line}[/red]"

    if name == "write_file":
        # Result is like "Wrote 847 lines to /path/file" — extract line count
        import re
        m = re.match(r"Wrote (\d+) lines? to (.+)", result)
        if m:
            return f"[dim]Wrote file[/dim] ({m.group(1)} lines)"
        return f"[dim]Wrote file[/dim]"
    if name == "read_file":
        # Result is numbered lines — count them
        lines = result.count("\n") + 1 if result else 0
        return f"[dim]Read file[/dim] ({lines} lines)"
    if name in ("edit_file", "multi_edit_file"):
        return f"[dim]Edited file[/dim]"
    if name == "shell":
        lines = result.strip().split("\n")
        last = lines[-1].strip() if lines else ""
        if len(last) > 60:
            last = last[:57] + "..."
        return f"[dim]Shell done[/dim] — {last}" if last else "[dim]Shell done[/dim]"
    if name == "glob_files":
        count = len(result.strip().split("\n")) if result.strip() else 0
        return f"[dim]Found {count} file(s)[/dim]"
    if name == "grep_files":
        count = len(result.strip().split("\n")) if result.strip() else 0
        return f"[dim]Found {count} match(es)[/dim]"
    if name == "think":
        return "[dim]Done thinking[/dim]"
    if name == "todo":
        return "[dim]Tasks updated[/dim]"
    if name == "create_sub_agent":
        # Show first 80 chars of sub-agent result
        short = result[:80].replace("\n", " ")
        if len(result) > 80:
            short += "..."
        return f"[dim]Sub-agent:[/dim] {short}"
    # Fallback
    size = len(result)
    size_str = f"{size / 1024:.1f}KB" if size > 1024 else f"{size}B"
    return f"[dim]{name} done[/dim] ({size_str})"


class Console:
    """Handles all terminal output with Rich formatting."""

    def __init__(self):
        self._console = RichConsole()
        self._live: Live | None = None
        self._streaming_text = ""
        self._spinner_live: Live | None = None
        self._spinner_message = ""
        self._spinner_start = 0.0
        self._spinner_refresh_task: Any = None

    def print_welcome(self, model: str):
        self._console.print()
        self._console.print(
            Panel(
                f"[bold]IC Agent[/bold] - AI Coding Assistant\n"
                f"Model: [cyan]{model}[/cyan]\n"
                f"Type [bold]/help[/bold] for commands, [bold]/quit[/bold] to exit",
                border_style="blue",
            )
        )
        self._console.print()

    def start_streaming(self):
        self._streaming_text = ""
        self._live = Live(
            Text(""),
            console=self._console,
            refresh_per_second=15,
            vertical_overflow="visible",
        )
        self._live.start()

    def stream_text(self, delta: str):
        self._streaming_text += delta
        if self._live:
            try:
                md = Markdown(self._streaming_text)
                self._live.update(md)
            except Exception:
                self._live.update(Text(self._streaming_text))

    def end_streaming(self):
        if self._live:
            try:
                if self._streaming_text.strip():
                    md = Markdown(self._streaming_text)
                    self._live.update(md)
            except Exception:
                pass
            self._live.stop()
            self._live = None
        self._streaming_text = ""

    def print_tool_call(self, name: str, args: dict[str, Any]):
        """Show a compact one-liner for a tool call (activity feed style)."""
        summary = _tool_call_summary(name, args)
        self._console.print(f"  [yellow]⏳[/yellow] [dim]{summary}[/dim]")

    def print_tool_result(self, name: str, result: str):
        """Show a compact one-liner for a tool result."""
        is_error = result.startswith("Error")
        summary = _tool_result_summary(name, result, is_error)
        if is_error:
            self._console.print(f"  [red]✗[/red] {summary}")
        else:
            self._console.print(f"  [green]✓[/green] {summary}")

    def print_sub_agent_start(self, task: str):
        self._console.print()
        self._console.print(
            Panel(
                f"[italic]{task}[/italic]",
                title="[bold magenta]Sub-Agent Started[/bold magenta]",
                border_style="magenta",
            )
        )

    def print_sub_agent_end(self, result: str):
        display = result[:300] + "..." if len(result) > 300 else result
        self._console.print(
            Panel(
                display,
                title="[bold magenta]Sub-Agent Completed[/bold magenta]",
                border_style="green",
            )
        )
        self._console.print()

    def start_spinner(self, message: str = "Thinking..."):
        """Show a spinner with a status message and elapsed time."""
        self.stop_spinner()
        self._spinner_message = message
        self._spinner_start = time.monotonic()
        self._spinner_live = Live(
            self._build_spinner_renderable(),
            console=self._console,
            refresh_per_second=4,
            transient=True,
        )
        self._spinner_live.start()
        # Start a background refresh for elapsed time
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            self._spinner_refresh_task = loop.create_task(self._refresh_spinner())
        except RuntimeError:
            self._spinner_refresh_task = None

    def _build_spinner_renderable(self) -> Text:
        elapsed = time.monotonic() - self._spinner_start
        if elapsed < 5:
            return Text.from_markup(f"[cyan]⠋[/cyan] [dim]{self._spinner_message}[/dim]")
        else:
            return Text.from_markup(
                f"[cyan]⠋[/cyan] [dim]{self._spinner_message}[/dim] "
                f"[dim]({elapsed:.0f}s)[/dim]"
            )

    async def _refresh_spinner(self):
        """Periodically update spinner to show elapsed time."""
        import asyncio
        try:
            while self._spinner_live:
                await asyncio.sleep(1)
                if self._spinner_live:
                    self._spinner_live.update(self._build_spinner_renderable())
        except asyncio.CancelledError:
            pass

    def stop_spinner(self):
        """Stop the spinner if running."""
        if hasattr(self, "_spinner_refresh_task") and self._spinner_refresh_task:
            self._spinner_refresh_task.cancel()
            self._spinner_refresh_task = None
        if self._spinner_live:
            self._spinner_live.stop()
            self._spinner_live = None

    def print_tool_progress(self, tool_name: str, message: str, percent: int | None):
        """Show tool execution progress."""
        if percent is not None:
            self._console.print(f"  [dim]{tool_name}:[/dim] [cyan]{message}[/cyan] [dim]({percent}%)[/dim]")
        else:
            self._console.print(f"  [dim]{tool_name}:[/dim] [cyan]{message}[/cyan]")

    def print_error(self, msg: str):
        self._console.print(f"[bold red]Error:[/bold red] {msg}")

    def print_info(self, msg: str):
        self._console.print(f"[dim]{msg}[/dim]")

    def print_usage(self, usage: dict[str, int]):
        prompt = usage.get("prompt_tokens", 0)
        completion = usage.get("completion_tokens", 0)
        total = prompt + completion
        self._console.print(
            f"[dim]Tokens: {total:,} (prompt: {prompt:,}, completion: {completion:,})[/dim]"
        )
