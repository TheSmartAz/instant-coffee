from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional, Sequence

from .base import AgentResult, BaseAgent
from .prompts import get_interview_prompt


@dataclass
class InterviewState:
    collected_info: dict = field(default_factory=dict)
    rounds_used: int = 0
    max_rounds: int = 5
    confidence: float = 0.0
    is_complete: bool = False


class InterviewAgent(BaseAgent):
    agent_type = "interview"

    def __init__(self, db, session_id: str, settings, event_emitter=None, agent_id=None, task_id=None) -> None:
        super().__init__(db, session_id, settings, event_emitter=event_emitter, agent_id=agent_id, task_id=task_id)
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
        if self.state.rounds_used >= self.state.max_rounds:
            self.state.is_complete = True
            return AgentResult(
                message="Thanks! I have enough to proceed with generation.",
                is_complete=True,
                confidence=self.state.confidence,
                context=json.dumps(self.state.collected_info),
                rounds_used=self.state.rounds_used,
            )

        messages = self._build_messages(user_message=user_message, history=history)
        response = await self._call_llm(
            messages=messages,
            agent_type=self.agent_type,
            model=self.settings.model,
            temperature=self.settings.temperature,
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

        return AgentResult(
            message=message,
            is_complete=self.state.is_complete,
            confidence=self.state.confidence,
            context=json.dumps(self.state.collected_info),
            rounds_used=self.state.rounds_used,
        )

    def _build_messages(self, *, user_message: str, history: Sequence[dict]) -> list[dict]:
        messages: list[dict] = [{"role": "system", "content": self.system_prompt}]
        if history:
            for item in history:
                role = item.get("role", "user")
                content = item.get("content", "")
                if content:
                    messages.append({"role": role, "content": content})

        user_text = user_message.strip() or "Tell me more about the page you want to build."
        state_context = "\n".join(
            [
                f"Collected info: {json.dumps(self.state.collected_info)}",
                f"Rounds: {self.state.rounds_used}/{self.state.max_rounds}",
                f"Current confidence: {self.state.confidence:.2f}",
                f"User input: {user_text}",
            ]
        )
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

        return {
            "message": message,
            "is_complete": is_complete,
            "confidence": confidence,
            "collected_info": collected_info,
        }

    def should_generate(self) -> bool:
        return bool(self.state.is_complete or self.state.confidence >= 0.8)

    def get_collected_info(self) -> dict:
        return dict(self.state.collected_info or {})


__all__ = ["InterviewAgent", "InterviewState"]
