from __future__ import annotations

from fastapi import Request


def build_preview_url(request: Request, session_id: str) -> str:
    base = str(request.base_url).rstrip("/")
    return f"{base}/api/sessions/{session_id}/preview"


__all__ = ["build_preview_url"]
