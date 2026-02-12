"""Input prompt with prompt_toolkit — styled input bar with separator."""

from __future__ import annotations

from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.key_binding import KeyBindings


class Prompt:
    """Interactive input prompt with a visible separator line.

    The prompt renders a horizontal rule above the input area so the user
    can immediately tell when the agent is waiting for input — similar to
    Claude Code / Codex.
    """

    def __init__(self, history_file: Path | None = None):
        history = FileHistory(str(history_file)) if history_file else None

        # Custom key bindings — Enter submits, Escape+Enter for newline
        kb = KeyBindings()

        @kb.add("escape", "enter")
        def _newline(event):
            event.current_buffer.insert_text("\n")

        self._session: PromptSession[str] = PromptSession(
            history=history,
            auto_suggest=AutoSuggestFromHistory(),
            multiline=False,
            key_bindings=kb,
        )

        # Status shown in the separator line
        self._status: str = ""

    def set_status(self, status: str) -> None:
        """Update the status hint shown in the separator (e.g. 'Interrupted')."""
        self._status = status

    def _build_prompt(self, prompt_text: str) -> HTML:
        """Build the prompt with a separator line above it."""
        # Get terminal width (fallback 80)
        try:
            import shutil
            cols = shutil.get_terminal_size().columns
        except Exception:
            cols = 80

        if self._status:
            # ── Interrupted ──────────────────────
            tag = f" {self._status} "
            remaining = max(cols - len(tag) - 4, 4)
            left = 2
            right = remaining
            line = f"{'─' * left}{tag}{'─' * right}"
        else:
            line = "─" * cols

        # dim separator + newline + prompt
        return HTML(
            f"<style fg='#555555'>{line}</style>\n"
            f"<style fg='#888888'>{prompt_text}</style>"
        )

    async def get_input(self, prompt_text: str = "> ") -> str:
        """Show the separator + prompt and wait for user input."""
        result = await self._session.prompt_async(self._build_prompt(prompt_text))
        # Clear status after user submits
        self._status = ""
        return result
