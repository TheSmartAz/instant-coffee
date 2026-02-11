from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator, List, Optional, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from ..services.event_store import EventStoreService

from .models import (
    AgentEndEvent,
    AgentProgressEvent,
    AgentStartEvent,
    BaseEvent,
    DoneEvent,
    ErrorEvent,
    PageCreatedEvent,
    PagePreviewReadyEvent,
    PageVersionCreatedEvent,
    HistoryCreatedEvent,
    InterviewAnswerEvent,
    InterviewQuestionEvent,
    ProductDocConfirmedEvent,
    ProductDocGeneratedEvent,
    ProductDocOutdatedEvent,
    ProductDocUpdatedEvent,
    SnapshotCreatedEvent,
    MultiPageDecisionEvent,
    SitemapProposedEvent,
    ToolCallEvent,
    ToolResultEvent,
    TextDeltaEvent,
    TokenUsageEvent,
    VersionCreatedEvent,
    WorkflowEvent,
)

logger = logging.getLogger(__name__)

EventUnion = Union[
    AgentStartEvent,
    AgentProgressEvent,
    AgentEndEvent,
    ToolCallEvent,
    ToolResultEvent,
    TokenUsageEvent,
    WorkflowEvent,
    PageCreatedEvent,
    PageVersionCreatedEvent,
    PagePreviewReadyEvent,
    InterviewQuestionEvent,
    InterviewAnswerEvent,
    VersionCreatedEvent,
    SnapshotCreatedEvent,
    HistoryCreatedEvent,
    MultiPageDecisionEvent,
    SitemapProposedEvent,
    ProductDocGeneratedEvent,
    ProductDocUpdatedEvent,
    ProductDocConfirmedEvent,
    ProductDocOutdatedEvent,
    TextDeltaEvent,
    ErrorEvent,
    DoneEvent,
]


class EventEmitter:
    def __init__(
        self,
        *,
        session_id: str | None = None,
        run_id: str | None = None,
        event_store: Optional[EventStoreService] = None,
        max_events: int | None = None,
    ) -> None:
        self._events: List[EventUnion] = []
        self._offset = 0
        self.session_id = session_id
        self.run_id = run_id
        self._event_store = event_store
        if max_events is None and event_store is not None:
            max_events = 2000
        self._max_events = max_events

    def emit(self, event: EventUnion) -> None:
        """Emit an event."""
        if getattr(event, "session_id", None) is None and self.session_id:
            event.session_id = self.session_id
        if getattr(event, "run_id", None) is None and self.run_id:
            event.run_id = self.run_id
        if getattr(event, "event_id", None) is None:
            event.event_id = uuid.uuid4().hex
        if not event.timestamp:
            event.timestamp = datetime.now(timezone.utc)
        self._events.append(event)
        if self._max_events is not None and len(self._events) > self._max_events:
            overflow = len(self._events) - self._max_events
            if overflow > 0:
                del self._events[:overflow]
                self._offset += overflow
        if self._event_store:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            def _record() -> None:
                try:
                    self._event_store.record_event(event)
                except Exception:
                    logger.exception("Failed to persist event")

            use_executor = bool(
                loop
                and loop.is_running()
                and getattr(self._event_store, "_use_separate_session", True)
            )
            if use_executor:
                loop.run_in_executor(None, _record)
            else:
                _record()
        logger.debug("Event emitted: %s", getattr(event.type, "value", event.type))

    def get_events(self) -> List[EventUnion]:
        """Get all emitted events."""
        return list(self._events)

    def clear(self) -> None:
        """Clear all events."""
        self._events.clear()
        self._offset = 0

    async def stream(self) -> AsyncGenerator[str, None]:
        """Stream events as SSE."""
        for event in self._events:
            yield event.to_sse()
        yield "data: [DONE]\n\n"

    def events_since(self, index: int) -> tuple[List[EventUnion], int]:
        """Return events since the given index and the new index."""
        if index < 0:
            index = 0
        if index < self._offset:
            index = self._offset
        relative = index - self._offset
        if relative >= len(self._events):
            return [], self._offset + len(self._events)
        return self._events[relative:], self._offset + len(self._events)
