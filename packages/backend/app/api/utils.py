from __future__ import annotations

from fastapi import Request


def build_preview_url(request: Request, session_id: str) -> str:
    base = str(request.base_url).rstrip("/")
    return f"{base}/api/sessions/{session_id}/preview"


def build_page_preview_url(request: Request, page_id: str) -> str:
    base = str(request.base_url).rstrip("/")
    return f"{base}/api/pages/{page_id}/preview"


def build_thumbnail_url(request: Request, session_id: str) -> str:
    base = str(request.base_url).rstrip("/")
    return f"{base}/api/sessions/{session_id}/thumbnail"


__all__ = ["build_preview_url", "build_page_preview_url", "build_thumbnail_url"]
