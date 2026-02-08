"""WebUserIO — bridges the agent's blocking ask_user tool with async SSE.

Implements the agent ``UserIO`` protocol.  When the engine calls
``present_questions``, this class:

1. Emits an ``InterviewQuestionEvent`` via the backend ``EventEmitter``.
2. Creates an ``asyncio.Future`` and awaits it.
3. When the user submits an answer (via a new chat message), the chat API
   calls ``resolve_answer()`` which sets the future's result and unblocks
   the engine.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from ..events.emitter import EventEmitter
from ..events.models import InterviewQuestionEvent

logger = logging.getLogger(__name__)


@dataclass
class _PendingQuestion:
    batch_id: str
    future: asyncio.Future
    questions: list[dict[str, Any]]


class WebUserIO:
    """UserIO implementation for the web backend."""

    def __init__(self, emitter: EventEmitter, session_id: str) -> None:
        self._emitter = emitter
        self._session_id = session_id
        self._pending: Optional[_PendingQuestion] = None

    @property
    def has_pending(self) -> bool:
        return self._pending is not None

    @property
    def pending_batch_id(self) -> Optional[str]:
        return self._pending.batch_id if self._pending else None

    async def present_questions(
        self, questions: list[Any]
    ) -> list[Any]:
        """Emit questions via SSE and block until the user answers."""
        batch_id = uuid.uuid4().hex
        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()

        serialized = _serialize_questions(questions)

        self._pending = _PendingQuestion(
            batch_id=batch_id,
            future=future,
            questions=serialized,
        )

        self._emitter.emit(
            InterviewQuestionEvent(
                session_id=self._session_id,
                batch_id=batch_id,
                message=None,
                questions=serialized,
            )
        )

        logger.info(
            "WebUserIO: emitted %d questions (batch=%s), awaiting answer",
            len(serialized),
            batch_id,
        )

        try:
            answers = await future
        finally:
            self._pending = None

        return _deserialize_answers(answers, questions)

    async def confirm(self, message: str) -> bool:
        """Ask a yes/no confirmation via the question mechanism."""
        answers = await self.present_questions(
            [
                _make_confirm_question(message),
            ]
        )
        if not answers:
            return True
        first = answers[0]
        selected = getattr(first, "selected", []) if hasattr(first, "selected") else []
        text = getattr(first, "text", "") if hasattr(first, "text") else str(first)
        if selected:
            return selected[0].lower() in {"yes", "confirm", "ok"}
        return text.lower() in {"yes", "y", "confirm", "ok", ""}

    def resolve_answer(self, answer_payload: Any) -> bool:
        """Unblock the pending future with the user's answer.

        Returns True if there was a pending question to resolve.
        """
        if self._pending is None:
            logger.warning("resolve_answer called but no pending question")
            return False
        if self._pending.future.done():
            logger.warning("resolve_answer called but future already done")
            return False
        self._pending.future.set_result(answer_payload)
        logger.info("WebUserIO: resolved answer for batch=%s", self._pending.batch_id)
        return True


def _serialize_questions(questions: list[Any]) -> list[dict[str, Any]]:
    """Convert agent Question dataclasses to JSON-serializable dicts."""
    result = []
    for q in questions:
        if isinstance(q, dict):
            result.append(q)
            continue
        entry: dict[str, Any] = {"question": getattr(q, "question", str(q))}
        options = getattr(q, "options", [])
        if options:
            entry["options"] = [
                {"label": getattr(o, "label", str(o)), "description": getattr(o, "description", "")}
                for o in options
            ]
        entry["allow_multiple"] = getattr(q, "allow_multiple", False)
        result.append(entry)
    return result


def _deserialize_answers(raw: Any, original_questions: list[Any]) -> list[Any]:
    """Convert raw answer payload back to agent Answer-like objects."""
    try:
        from ic.ui.io import Answer
    except ImportError:
        return raw if isinstance(raw, list) else [raw]

    if isinstance(raw, str):
        return [Answer(question=getattr(original_questions[0], "question", ""), text=raw)]

    if isinstance(raw, dict):
        answers_list = raw.get("answers", [raw])
    elif isinstance(raw, list):
        answers_list = raw
    else:
        return [Answer(question="", text=str(raw))]

    results = []
    for i, item in enumerate(answers_list):
        q_text = ""
        if i < len(original_questions):
            q_text = getattr(original_questions[i], "question", "")
        if isinstance(item, dict):
            results.append(
                Answer(
                    question=item.get("question", q_text),
                    selected=item.get("selected", []),
                    text=item.get("text", ""),
                    skipped=item.get("skipped", False),
                )
            )
        else:
            results.append(Answer(question=q_text, text=str(item)))
    return results


def _make_confirm_question(message: str) -> Any:
    """Create a confirmation question compatible with the agent protocol."""
    try:
        from ic.ui.io import Question, Option

        return Question(
            question=message,
            options=[
                Option(label="Yes", description="Confirm"),
                Option(label="No", description="Cancel"),
            ],
            allow_multiple=False,
        )
    except ImportError:
        return {
            "question": message,
            "options": [
                {"label": "Yes", "description": "Confirm"},
                {"label": "No", "description": "Cancel"},
            ],
            "allow_multiple": False,
        }
