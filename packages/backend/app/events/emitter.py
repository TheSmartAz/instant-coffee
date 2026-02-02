from __future__ import annotations

import logging
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
    PlanCreatedEvent,
    PlanUpdatedEvent,
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
    TaskBlockedEvent,
    TaskDoneEvent,
    TaskFailedEvent,
    TaskProgressEvent,
    TaskRetryingEvent,
    TaskSkippedEvent,
    TaskStartedEvent,
    ToolCallEvent,
    ToolResultEvent,
    TokenUsageEvent,
    VersionCreatedEvent,
)

logger = logging.getLogger(__name__)

EventUnion = Union[
    AgentStartEvent,
    AgentProgressEvent,
    AgentEndEvent,
    ToolCallEvent,
    ToolResultEvent,
    TokenUsageEvent,
    PlanCreatedEvent,
    PlanUpdatedEvent,
    PageCreatedEvent,
    PageVersionCreatedEvent,
    PagePreviewReadyEvent,
    InterviewQuestionEvent,
    InterviewAnswerEvent,
    VersionCreatedEvent,
    SnapshotCreatedEvent,
    HistoryCreatedEvent,
    TaskStartedEvent,
    TaskProgressEvent,
    TaskDoneEvent,
    TaskFailedEvent,
    TaskRetryingEvent,
    TaskSkippedEvent,
    TaskBlockedEvent,
    MultiPageDecisionEvent,
    SitemapProposedEvent,
    ProductDocGeneratedEvent,
    ProductDocUpdatedEvent,
    ProductDocConfirmedEvent,
    ProductDocOutdatedEvent,
    ErrorEvent,
    DoneEvent,
]


class EventEmitter:
    def __init__(
        self,
        *,
        session_id: str | None = None,
        event_store: Optional[EventStoreService] = None,
    ) -> None:
        self._events: List[EventUnion] = []
        self.session_id = session_id
        self._event_store = event_store

    def emit(self, event: EventUnion) -> None:
        """Emit an event."""
        if getattr(event, "session_id", None) is None and self.session_id:
            event.session_id = self.session_id
        if not event.timestamp:
            event.timestamp = datetime.now(timezone.utc)
        self._events.append(event)
        if self._event_store:
            try:
                self._event_store.record_event(event)
            except Exception:
                logger.exception("Failed to persist event")
        logger.debug("Event emitted: %s", getattr(event.type, "value", event.type))

    def get_events(self) -> List[EventUnion]:
        """Get all emitted events."""
        return list(self._events)

    def clear(self) -> None:
        """Clear all events."""
        self._events.clear()

    async def stream(self) -> AsyncGenerator[str, None]:
        """Stream events as SSE."""
        for event in self._events:
            yield event.to_sse()
        yield "data: [DONE]\n\n"

    def events_since(self, index: int) -> tuple[List[EventUnion], int]:
        """Return events since the given index and the new index."""
        if index < 0:
            index = 0
        if index >= len(self._events):
            return [], index
        return self._events[index:], len(self._events)
