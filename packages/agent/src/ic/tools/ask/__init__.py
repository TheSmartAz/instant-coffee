"""AskUser tool — presents multiple-choice questions to the user.

Blocks the agentic loop until the user answers. Answers are returned
as structured text that gets injected into the conversation context.
"""

from __future__ import annotations

import json
from typing import Any

from ic.tools.base import BaseTool, ToolParam, ToolResult
from ic.ui.io import UserIO, Question, Option, Answer


class AskUser(BaseTool):
    name = "ask_user"
    description = (
        "Ask the user one or more multiple-choice questions to clarify "
        "requirements. Each question includes options the user can pick "
        "from, plus free-text input. Use this when the user's request "
        "lacks detail needed to build a good product doc. "
        "2-5 questions per call. The user can skip questions or type "
        "'/go' to proceed with what's been collected."
    )
    parameters = [
        ToolParam(
            name="questions",
            type="array",
            description=(
                "Array of question objects. Each has: "
                "'question' (string), 'options' (array of {label, description}), "
                "and optional 'allow_multiple' (boolean, default false)."
            ),
        ),
    ]

    def __init__(self, user_io: UserIO | None = None):
        self._user_io = user_io

    async def execute(self, **kwargs: Any) -> ToolResult:
        if not self._user_io:
            return ToolResult(
                error="AskUser tool has no UserIO interface configured.",
                is_error=True,
            )

        raw_questions = kwargs.get("questions", [])
        if not raw_questions:
            return ToolResult(error="No questions provided.", is_error=True)

        # Parse questions from LLM output
        questions = _parse_questions(raw_questions)
        if not questions:
            return ToolResult(error="Could not parse questions.", is_error=True)

        # Present to user and collect answers
        answers = await self._user_io.present_questions(questions)

        # Format answers for context injection
        return ToolResult(output=_format_answers(answers))

    def to_openai_schema(self) -> dict[str, Any]:
        """Custom schema since questions have nested structure."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "questions": {
                            "type": "array",
                            "description": "Questions to ask the user",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "question": {
                                        "type": "string",
                                        "description": "The question text",
                                    },
                                    "options": {
                                        "type": "array",
                                        "description": "Choice options",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "label": {"type": "string"},
                                                "description": {
                                                    "type": "string",
                                                    "description": "Brief explanation",
                                                },
                                            },
                                            "required": ["label"],
                                        },
                                        "minItems": 2,
                                        "maxItems": 5,
                                    },
                                    "allow_multiple": {
                                        "type": "boolean",
                                        "description": "Allow selecting multiple options",
                                    },
                                },
                                "required": ["question", "options"],
                            },
                            "minItems": 1,
                            "maxItems": 5,
                        },
                    },
                    "required": ["questions"],
                },
            },
        }


def _parse_questions(raw: list[dict | Any]) -> list[Question]:
    """Parse LLM-generated question dicts into Question objects."""
    questions: list[Question] = []
    for item in raw:
        if isinstance(item, str):
            try:
                item = json.loads(item)
            except (json.JSONDecodeError, TypeError):
                continue
        if not isinstance(item, dict):
            continue

        q_text = item.get("question", "")
        if not q_text:
            continue

        options = []
        for opt in item.get("options", []):
            if isinstance(opt, str):
                options.append(Option(label=opt))
            elif isinstance(opt, dict):
                options.append(Option(
                    label=opt.get("label", ""),
                    description=opt.get("description", ""),
                ))

        questions.append(Question(
            question=q_text,
            options=options,
            allow_multiple=bool(item.get("allow_multiple", False)),
        ))

    return questions


def _format_answers(answers: list[Answer]) -> str:
    """Format answers as readable text for context injection."""
    parts: list[str] = []
    parts.append("User's answers:")
    for a in answers:
        parts.append(f"\nQ: {a.question}")
        if a.skipped:
            parts.append("A: (skipped — use your best judgment)")
        elif a.selected and a.text:
            parts.append(f"A: {', '.join(a.selected)}. Additional: {a.text}")
        elif a.selected:
            parts.append(f"A: {', '.join(a.selected)}")
        elif a.text:
            parts.append(f"A: {a.text}")
        else:
            parts.append("A: (no answer — use your best judgment)")
    return "\n".join(parts)
