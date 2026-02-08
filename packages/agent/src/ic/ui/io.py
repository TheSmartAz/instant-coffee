"""Abstract user interaction interface.

Defines the UserIO protocol so CLI and web can share the same tool logic.
CLI renders as numbered list + text; web renders as form components.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class Option:
    """A single choice option."""
    label: str
    description: str = ""


@dataclass
class Question:
    """A question with multiple-choice options."""
    question: str
    options: list[Option] = field(default_factory=list)
    allow_multiple: bool = False


@dataclass
class Answer:
    """User's answer to a question."""
    question: str
    selected: list[str] = field(default_factory=list)
    text: str = ""
    skipped: bool = False


GLOBAL_ESCAPE_COMMANDS = {"/go", "/build", "/skip"}


@runtime_checkable
class UserIO(Protocol):
    """Abstract interface for user interaction.

    CLI implements this with numbered lists + prompt_toolkit.
    Web implements this with form components via WebSocket/SSE.
    """

    async def present_questions(
        self, questions: list[Question]
    ) -> list[Answer]:
        """Present questions and collect answers.

        Returns a list of Answer objects, one per question.
        If the user triggers a global escape, remaining answers
        will have skipped=True.
        """
        ...

    async def confirm(self, message: str) -> bool:
        """Ask for yes/no confirmation."""
        ...
