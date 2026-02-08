"""Rich console output for the CLI agent."""

from __future__ import annotations

import json
from typing import Any

from rich.console import Console as RichConsole
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text


class Console:
    """Handles all terminal output with Rich formatting."""

    def __init__(self):
        self._console = RichConsole()
        self._live: Live | None = None
        self._streaming_text = ""

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
        args_display = dict(args)
        for k, v in args_display.items():
            if isinstance(v, str) and len(v) > 200:
                args_display[k] = v[:200] + "..."
        try:
            args_str = json.dumps(args_display, indent=2, ensure_ascii=False)
        except Exception:
            args_str = str(args_display)
        self._console.print(
            Panel(
                Syntax(args_str, "json", theme="monokai", line_numbers=False),
                title=f"[bold yellow]Tool: {name}[/bold yellow]",
                border_style="yellow",
                expand=False,
            )
        )

    def print_tool_result(self, name: str, result: str):
        display = result
        if len(display) > 500:
            display = display[:500] + f"\n... ({len(result)} chars total)"
        self._console.print(
            Panel(
                display,
                title=f"[dim]Result: {name}[/dim]",
                border_style="dim",
                expand=False,
            )
        )

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
