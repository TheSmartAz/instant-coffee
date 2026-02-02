from __future__ import annotations

import json
from dataclasses import dataclass, field
import re
from typing import Optional, Sequence
from uuid import uuid4

from .base import AgentResult, BaseAgent
from .prompts import get_interview_prompt
from ..events.models import InterviewQuestionEvent


@dataclass
class InterviewState:
    collected_info: dict = field(default_factory=dict)
    rounds_used: int = 0
    max_rounds: int = 5
    confidence: float = 0.0
    is_complete: bool = False


class InterviewAgent(BaseAgent):
    agent_type = "interview"

    def __init__(
        self,
        db,
        session_id: str,
        settings,
        event_emitter=None,
        agent_id=None,
        task_id=None,
        emit_lifecycle_events: bool = True,
    ) -> None:
        super().__init__(
            db,
            session_id,
            settings,
            event_emitter=event_emitter,
            agent_id=agent_id,
            task_id=task_id,
            emit_lifecycle_events=emit_lifecycle_events,
        )
        self.system_prompt = get_interview_prompt()
        self.state = InterviewState()

    def reset_state(self) -> None:
        self.state = InterviewState()

    async def process(
        self,
        user_message: str,
        history: Optional[Sequence[dict]] = None,
    ) -> AgentResult:
        history = history or []
        structured = self._extract_structured_answers(user_message)
        post_interview_update = False
        if structured:
            action = structured.get("action")
            answers = structured.get("answers") or []
            post_interview_update = bool(
                structured.get("mode") == "post_interview" or structured.get("post_interview") is True
            )
            self._apply_structured_answers(answers)
            cleaned_text = self._strip_structured_text(user_message)
            if post_interview_update and cleaned_text:
                self.state.collected_info["latest_user_update"] = cleaned_text
            if action == "generate_now":
                self.state.is_complete = True
                self.state.confidence = 1.0
                return AgentResult(
                    message="Got it! Generating the page now.",
                    is_complete=True,
                    confidence=self.state.confidence,
                    context=json.dumps(self.state.collected_info),
                    rounds_used=self.state.rounds_used,
                )
            if action == "skip_batch":
                user_message = (
                    cleaned_text
                    or "User skipped the remaining questions. Continue with the next questions."
                )
            else:
                user_message = cleaned_text or "User submitted answers. Continue the interview if needed."
            if post_interview_update and not cleaned_text:
                self.state.is_complete = True
                self.state.confidence = max(self.state.confidence, 0.95)
                return AgentResult(
                    message="Update received.",
                    is_complete=True,
                    confidence=self.state.confidence,
                    context=json.dumps(self.state.collected_info),
                    rounds_used=self.state.rounds_used,
                    questions=[],
                    missing_info=[],
                )
        if self.state.rounds_used >= self.state.max_rounds:
            self.state.is_complete = True
            return AgentResult(
                message="Thanks! I have enough to proceed with generation.",
                is_complete=True,
                confidence=self.state.confidence,
                context=json.dumps(self.state.collected_info),
                rounds_used=self.state.rounds_used,
            )

        messages = self._build_messages(
            user_message=user_message, history=history, post_interview=post_interview_update
        )
        response = await self._call_llm(
            messages=messages,
            agent_type=self.agent_type,
            model=self.settings.model,
            temperature=self.settings.temperature,
            stream=True,
            context="interview",
        )
        parsed = self._parse_response(response.content or "")

        new_info = parsed.get("collected_info") or {}
        if isinstance(new_info, dict) and new_info:
            self.state.collected_info.update(new_info)

        confidence = parsed.get("confidence")
        if confidence is not None:
            self.state.confidence = confidence

        self.state.is_complete = bool(parsed.get("is_complete", False))
        self.state.rounds_used += 1

        message = parsed.get("message") or "Tell me more about the page you want to build."
        if self.state.rounds_used >= self.state.max_rounds and not self.state.is_complete:
            self.state.is_complete = True
            message = "Thanks! I have enough to proceed with generation."

        questions = parsed.get("questions")
        missing_info = parsed.get("missing_info")
        if post_interview_update:
            self.state.is_complete = True
            self.state.confidence = max(self.state.confidence, 0.95)
            questions = []
            missing_info = []

        if questions and self.event_emitter:
            batch_id = uuid4().hex
            self.event_emitter.emit(
                InterviewQuestionEvent(
                    session_id=self.session_id,
                    batch_id=batch_id,
                    message=message,
                    questions=questions,
                )
            )

        return AgentResult(
            message=message,
            is_complete=self.state.is_complete,
            confidence=self.state.confidence,
            context=json.dumps(self.state.collected_info),
            rounds_used=self.state.rounds_used,
            questions=questions,
            missing_info=missing_info,
        )

    def _build_messages(
        self, *, user_message: str, history: Sequence[dict], post_interview: bool = False
    ) -> list[dict]:
        messages: list[dict] = [{"role": "system", "content": self.system_prompt}]
        if history:
            for item in history:
                role = item.get("role", "user")
                content = item.get("content", "")
                if not content:
                    continue
                if "<INTERVIEW_ANSWERS>" in content:
                    content = self._strip_structured_text(content)
                if content:
                    messages.append({"role": role, "content": content})

        user_text = user_message.strip() or "Tell me more about the page you want to build."
        state_lines = [
            f"Collected info: {json.dumps(self.state.collected_info)}",
            f"Rounds: {self.state.rounds_used}/{self.state.max_rounds}",
            f"Current confidence: {self.state.confidence:.2f}",
            f"User input: {user_text}",
        ]
        if post_interview:
            state_lines.append(
                "Post-interview update: true (do not ask more questions, update collected_info only)."
            )
        state_context = "\n".join(state_lines)
        messages.append({"role": "user", "content": state_context})
        return messages

    def _parse_response(self, content: str) -> dict:
        text = (content or "").strip()
        if not text:
            return {
                "message": "Tell me more about the page you want to build.",
                "is_complete": False,
                "confidence": 0.0,
                "collected_info": {},
            }

        payload = None
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    payload = json.loads(text[start : end + 1])
                except json.JSONDecodeError:
                    payload = None

        if not isinstance(payload, dict):
            return {
                "message": text,
                "is_complete": False,
                "confidence": 0.0,
                "collected_info": {},
                "questions": [],
                "missing_info": [],
            }

        message = payload.get("message") or "Tell me more about the page you want to build."
        confidence = payload.get("confidence")
        try:
            confidence = float(confidence) if confidence is not None else 0.0
        except (TypeError, ValueError):
            confidence = 0.0
        if confidence > 1.0 and confidence <= 100.0:
            confidence = confidence / 100.0
        confidence = min(max(confidence, 0.0), 1.0)

        is_complete = payload.get("is_complete")
        if is_complete is None:
            is_complete = confidence >= 0.8
        else:
            is_complete = bool(is_complete)

        collected_info = payload.get("collected_info")
        if not isinstance(collected_info, dict):
            collected_info = {}

        questions = self._normalize_questions(payload.get("questions"))
        missing_info = payload.get("missing_info") or payload.get("missingInfo") or []
        if not isinstance(missing_info, list):
            missing_info = []

        return {
            "message": message,
            "is_complete": is_complete,
            "confidence": confidence,
            "collected_info": collected_info,
            "questions": questions,
            "missing_info": missing_info,
        }

    def _normalize_questions(self, raw: object) -> list[dict]:
        if not isinstance(raw, list):
            return []
        normalized: list[dict] = []
        for index, item in enumerate(raw):
            if not isinstance(item, dict):
                continue
            raw_id = item.get("id") or item.get("key") or item.get("name") or f"q{index + 1}"
            raw_type = item.get("type") or "text"
            question_type = str(raw_type).lower()
            if question_type not in {"single", "multi", "text"}:
                question_type = "text"
            title = item.get("title") or item.get("question") or ""
            if not title:
                continue
            options = item.get("options")
            if question_type in {"single", "multi"} and not isinstance(options, list):
                question_type = "text"
            normalized_options = []
            if isinstance(options, list):
                for opt_index, option in enumerate(options):
                    if not isinstance(option, dict):
                        continue
                    opt_id = option.get("id") or option.get("value") or f"opt{opt_index + 1}"
                    label = option.get("label") or option.get("text") or opt_id
                    normalized_options.append({"id": str(opt_id), "label": str(label)})
            normalized.append(
                {
                    "id": str(raw_id),
                    "type": question_type,
                    "title": str(title),
                    "options": normalized_options or None,
                    "allow_other": bool(item.get("allow_other") or item.get("allowOther")),
                    "other_placeholder": item.get("other_placeholder")
                    or item.get("otherPlaceholder")
                    or "Enter your other answer",
                    "placeholder": item.get("placeholder") or "Enter your answer",
                }
            )
        return normalized

    def _extract_structured_answers(self, user_message: str) -> dict | None:
        if not user_message:
            return None
        match = re.search(r"<INTERVIEW_ANSWERS>(.*?)</INTERVIEW_ANSWERS>", user_message, re.DOTALL)
        if not match:
            return None
        payload_text = match.group(1).strip()
        if not payload_text:
            return None
        try:
            payload = json.loads(payload_text)
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None
        return payload

    def _strip_structured_text(self, user_message: str) -> str:
        if not user_message:
            return ""
        text = re.sub(
            r"<INTERVIEW_ANSWERS>.*?</INTERVIEW_ANSWERS>",
            "",
            user_message,
            flags=re.DOTALL,
        )
        text = re.sub(r"^Answer summary:.*$", "", text, flags=re.MULTILINE | re.IGNORECASE)
        return text.strip()

    def _apply_structured_answers(self, answers: object) -> None:
        if not isinstance(answers, list):
            return
        for answer in answers:
            if not isinstance(answer, dict):
                continue
            key = answer.get("id") or answer.get("question_id") or answer.get("key")
            if not key:
                continue
            value = answer.get("label") or answer.get("labels") or answer.get("value")
            other = answer.get("other")
            if value is None and other:
                value = other
            self.state.collected_info[str(key)] = value

    def should_generate(self) -> bool:
        return bool(self.state.is_complete or self.state.confidence >= 0.8)

    def get_collected_info(self) -> dict:
        return dict(self.state.collected_info or {})


__all__ = ["InterviewAgent", "InterviewState"]
