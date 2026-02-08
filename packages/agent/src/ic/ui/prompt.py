"""Input prompt with prompt_toolkit."""

from __future__ import annotations

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from pathlib import Path


class Prompt:
    """Interactive input prompt with history."""

    def __init__(self, history_file: Path | None = None):
        history = FileHistory(str(history_file)) if history_file else None
        self._session = PromptSession(
            history=history,
            auto_suggest=AutoSuggestFromHistory(),
            multiline=False,
        )

    async def get_input(self, prompt_text: str = "> ") -> str:
        return await self._session.prompt_async(prompt_text)
