"""Shared OrchestratorResponse dataclass.

Used by EngineOrchestrator and the chat API to communicate
orchestration results without depending on the legacy agents package.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class OrchestratorResponse:
    session_id: str
    phase: str
    message: str
    is_complete: bool
    preview_url: Optional[str] = None
    preview_html: Optional[str] = None
    progress: Optional[int] = None
    questions: Optional[list[dict]] = None
    action: Optional[str] = None
    product_doc_updated: Optional[bool] = None
    affected_pages: Optional[list[str]] = None
    active_page_slug: Optional[str] = None

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
        if self.questions is not None:
            payload["questions"] = self.questions
        if self.action is not None:
            payload["action"] = self.action
        if self.product_doc_updated is not None:
            payload["product_doc_updated"] = self.product_doc_updated
        if self.affected_pages is not None:
            payload["affected_pages"] = self.affected_pages
        if self.active_page_slug is not None:
            payload["active_page_slug"] = self.active_page_slug
        return payload


__all__ = ["OrchestratorResponse"]
