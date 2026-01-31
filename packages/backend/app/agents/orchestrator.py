from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import AsyncGenerator, Optional, Sequence

from sqlalchemy.orm import Session as DbSession

from ..config import get_settings
from ..db.models import Session as SessionModel
from ..events.emitter import EventEmitter
from ..events.models import AgentEndEvent, AgentProgressEvent, AgentStartEvent, DoneEvent
from ..services.token_tracker import TokenTrackerService
from ..services.version import VersionService
from .generation import GenerationAgent
from .interview import InterviewAgent
from .refinement import RefinementAgent

logger = logging.getLogger(__name__)


@dataclass
class OrchestratorResponse:
    session_id: str
    phase: str
    message: str
    is_complete: bool
    preview_url: Optional[str] = None
    preview_html: Optional[str] = None
    progress: Optional[int] = None

    def to_payload(self) -> dict:
        payload = {
            "session_id": self.session_id,
            "phase": self.phase,
            "message": self.message,
            "is_complete": self.is_complete,
        }
        if self.preview_url is not None:
            payload["preview_url"] = self.preview_url
        if self.preview_html is not None:
            payload["preview_html"] = self.preview_html
        if self.progress is not None:
            payload["progress"] = self.progress
        return payload


class AgentOrchestrator:
    def __init__(self, db: DbSession, session: SessionModel, event_emitter: EventEmitter | None = None) -> None:
        self.db = db
        self.session = session
        self.settings = get_settings()
        self.event_emitter = event_emitter

    def _token_summary(self) -> dict | None:
        try:
            return TokenTrackerService(self.db).summarize_session(self.session.id)
        except Exception:
            logger.exception("Failed to build token usage summary")
            return None

    def _get_latest_html(self) -> Optional[str]:
        try:
            versions = VersionService(self.db).get_versions(self.session.id, limit=1)
        except Exception:
            logger.exception("Failed to load latest version")
            return None
        if not versions:
            return None
        return versions[0].html

    def _wants_new_generation(self, message: str) -> bool:
        if not message:
            return False
        lower = message.lower()
        english_keywords = [
            "new page",
            "new screen",
            "start over",
            "from scratch",
            "create a new",
            "make a new",
            "regenerate",
            "generate a new",
        ]
        chinese_keywords = [
            "重新",
            "从头",
            "全新",
            "另起",
            "新的页面",
            "重新生成",
        ]
        if any(keyword in lower for keyword in english_keywords):
            return True
        return any(keyword in message for keyword in chinese_keywords)

    def _build_requirements(self, user_message: str, context: Optional[str]) -> str:
        base = user_message.strip() if user_message else ""
        if context:
            return f"{base}\n\nCollected info:\n{context}"
        return base or "Generate a mobile-first HTML page."

    async def stream(
        self,
        *,
        user_message: str,
        output_dir: str,
        skip_interview: bool = False,
    ) -> AsyncGenerator[object, None]:
        emitter = self.event_emitter or EventEmitter(session_id=self.session.id)
        index = 0

        def drain() -> list[object]:
            nonlocal index
            events, index = emitter.events_since(index)
            return events

        if not user_message.strip():
            emitter.emit(DoneEvent(summary="no message"))
            for event in drain():
                yield event
            return

        requirements = user_message
        if not skip_interview:
            interview = InterviewAgent(
                self.db,
                self.session.id,
                self.settings,
                event_emitter=emitter,
                agent_id="interview_1",
            )
            emitter.emit(AgentStartEvent(agent_id="interview_1", agent_type="interview"))
            for event in drain():
                yield event

            interview_result = await interview.process(user_message, history=[])
            emitter.emit(
                AgentProgressEvent(
                    agent_id="interview_1",
                    message=interview_result.message,
                    progress=100,
                )
            )
            emitter.emit(
                AgentEndEvent(
                    agent_id="interview_1",
                    status="success",
                    summary=interview_result.message,
                )
            )
            for event in drain():
                yield event

            if not interview_result.is_complete and not interview.should_generate():
                emitter.emit(DoneEvent(summary="interview_incomplete", token_usage=self._token_summary()))
                for event in drain():
                    yield event
                return
            requirements = self._build_requirements(user_message, interview_result.context)

        agent = GenerationAgent(
            self.db,
            self.session.id,
            self.settings,
            event_emitter=emitter,
            agent_id="generation_1",
        )
        emitter.emit(AgentStartEvent(agent_id="generation_1", agent_type="generation"))
        for event in drain():
            yield event

        for step in agent.progress_steps():
            emitter.emit(
                AgentProgressEvent(
                    agent_id="generation_1",
                    message=step.message,
                    progress=step.progress,
                )
            )
            for event in drain():
                yield event

        _ = await agent.generate(
            requirements=requirements,
            output_dir=output_dir,
            history=[],
        )

        for event in drain():
            yield event

        emitter.emit(AgentEndEvent(agent_id="generation_1", status="success", summary="done"))
        emitter.emit(DoneEvent(summary="complete", token_usage=self._token_summary()))

        for event in drain():
            yield event

    async def stream_responses(
        self,
        *,
        user_message: str,
        output_dir: str,
        history: Sequence[dict] | None = None,
    ) -> AsyncGenerator[OrchestratorResponse, None]:
        history = history or []
        emitter = self.event_emitter or EventEmitter(session_id=self.session.id)
        latest_html = self._get_latest_html()

        if latest_html and not self._wants_new_generation(user_message):
            agent = RefinementAgent(
                self.db,
                self.session.id,
                self.settings,
                event_emitter=emitter,
                agent_id="refinement_1",
            )
            result = await agent.refine(
                user_input=user_message,
                current_html=latest_html,
                output_dir=output_dir,
                history=list(history),
            )
            try:
                VersionService(self.db).create_version(
                    self.session.id,
                    result.html,
                    description="Refined page",
                )
                self.db.commit()
            except Exception:
                self.db.rollback()
            summary = self._token_summary()
            yield OrchestratorResponse(
                session_id=self.session.id,
                phase="refinement",
                message="Refinement complete",
                is_complete=True,
                preview_url=result.preview_url,
                preview_html=result.html,
                progress=100,
            )
            emitter.emit(DoneEvent(summary="complete", token_usage=summary))
            return

        interview = InterviewAgent(
            self.db,
            self.session.id,
            self.settings,
            event_emitter=emitter,
            agent_id="interview_1",
        )
        interview_result = await interview.process(user_message, history=history)
        if not interview_result.is_complete and not interview.should_generate():
            summary = self._token_summary()
            yield OrchestratorResponse(
                session_id=self.session.id,
                phase="interview",
                message=interview_result.message,
                is_complete=False,
            )
            emitter.emit(DoneEvent(summary="interview_incomplete", token_usage=summary))
            return

        requirements = self._build_requirements(user_message, interview_result.context)
        agent = GenerationAgent(
            self.db,
            self.session.id,
            self.settings,
            event_emitter=emitter,
            agent_id="generation_1",
        )
        result = await agent.generate(requirements=requirements, output_dir=output_dir, history=history)
        try:
            VersionService(self.db).create_version(
                self.session.id,
                result.html,
                description="Generated page",
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
        summary = self._token_summary()
        yield OrchestratorResponse(
            session_id=self.session.id,
            phase="generation",
            message="Generation complete",
            is_complete=True,
            preview_url=result.preview_url,
            preview_html=result.html,
            progress=100,
        )
        emitter.emit(DoneEvent(summary="complete", token_usage=summary))


__all__ = ["AgentOrchestrator", "OrchestratorResponse"]
