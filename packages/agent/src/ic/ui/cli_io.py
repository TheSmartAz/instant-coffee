"""CLI implementation of UserIO using Rich + prompt_toolkit."""

from __future__ import annotations

from rich.console import Console as RichConsole
from rich.panel import Panel
from rich.text import Text

from ic.ui.io import (
    UserIO,
    Question,
    Answer,
    Option,
    GLOBAL_ESCAPE_COMMANDS,
)


class CLIUserIO:
    """Renders questions as numbered lists in the terminal."""

    def __init__(self, console: RichConsole | None = None):
        self._console = console or RichConsole()

    async def present_questions(
        self, questions: list[Question]
    ) -> list[Answer]:
        answers: list[Answer] = []
        escaped = False

        for i, q in enumerate(questions):
            if escaped:
                answers.append(Answer(question=q.question, skipped=True))
                continue

            answer = await self._ask_one(q, i + 1, len(questions))
            if answer is None:
                # Global escape triggered
                escaped = True
                answers.append(Answer(question=q.question, skipped=True))
                continue
            answers.append(answer)

        return answers

    async def confirm(self, message: str) -> bool:
        self._console.print()
        self._console.print(f"  {message}")
        try:
            resp = input("  [Y/n]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return False
        return resp in ("", "y", "yes")

    async def _ask_one(
        self, q: Question, num: int, total: int
    ) -> Answer | None:
        """Ask a single question. Returns None on global escape."""
        # Build display
        lines = Text()
        lines.append(f"\n  {num}/{total}. ", style="bold")
        lines.append(q.question, style="bold")
        lines.append("\n")

        for j, opt in enumerate(q.options):
            lines.append(f"\n     [{j + 1}] ", style="cyan bold")
            lines.append(opt.label)
            if opt.description:
                lines.append(f" - {opt.description}", style="dim")

        lines.append(f"\n     [{len(q.options) + 1}] ", style="cyan bold")
        lines.append("Other (type your answer)", style="italic")
        lines.append("\n")

        self._console.print(
            Panel(
                lines,
                title="[bold blue]Agent needs more info[/bold blue]",
                border_style="blue",
                expand=False,
                padding=(0, 1),
            )
        )

        multi_hint = " (comma-separated)" if q.allow_multiple else ""
        prompt_text = f"  Answer{multi_hint} (number, text, Enter=skip, /go=proceed): "

        try:
            raw = input(prompt_text).strip()
        except (EOFError, KeyboardInterrupt):
            return Answer(question=q.question, skipped=True)

        # Global escape
        if raw.lower() in GLOBAL_ESCAPE_COMMANDS:
            self._console.print("  [dim]Skipping remaining questions...[/dim]")
            return None

        # Skip
        if not raw:
            return Answer(question=q.question, skipped=True)

        # Parse answer
        return self._parse_answer(q, raw)

    def _parse_answer(self, q: Question, raw: str) -> Answer:
        """Parse user input into an Answer."""
        selected: list[str] = []
        text = ""

        if q.allow_multiple:
            parts = [p.strip() for p in raw.split(",")]
        else:
            parts = [raw.strip()]

        for part in parts:
            if part.isdigit():
                idx = int(part) - 1
                if 0 <= idx < len(q.options):
                    selected.append(q.options[idx].label)
                elif idx == len(q.options):
                    # "Other" selected — need text input
                    try:
                        text = input("  Your answer: ").strip()
                    except (EOFError, KeyboardInterrupt):
                        pass
                else:
                    text = part  # treat as free text
            else:
                text = part  # free text answer

        return Answer(
            question=q.question,
            selected=selected,
            text=text,
        )
