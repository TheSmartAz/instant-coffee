from __future__ import annotations

from uuid import uuid4


def new_trace_id() -> str:
    return uuid4().hex


class TrackedError(Exception):
    def __init__(self, message: str, *, error_type: str, trace_id: str | None = None) -> None:
        self.error_type = error_type
        self.trace_id = trace_id or new_trace_id()
        super().__init__(message)

    def with_trace(self) -> str:
        return f"{self.args[0]} (trace_id={self.trace_id})"


class HTMLExtractionError(TrackedError):
    def __init__(self, message: str, *, trace_id: str | None = None) -> None:
        super().__init__(message, error_type="html_extraction", trace_id=trace_id)


class TaskTimeoutError(TrackedError):
    def __init__(self, message: str, *, trace_id: str | None = None) -> None:
        super().__init__(message, error_type="timeout", trace_id=trace_id)


class TaskAbortError(TrackedError):
    def __init__(self, message: str, *, trace_id: str | None = None) -> None:
        super().__init__(message, error_type="aborted", trace_id=trace_id)


class PinnedLimitExceeded(Exception):
    def __init__(self, message: str, *, current_pinned: list[int]) -> None:
        self.current_pinned = list(current_pinned)
        super().__init__(message)


__all__ = [
    "new_trace_id",
    "TrackedError",
    "HTMLExtractionError",
    "TaskTimeoutError",
    "TaskAbortError",
    "PinnedLimitExceeded",
]
