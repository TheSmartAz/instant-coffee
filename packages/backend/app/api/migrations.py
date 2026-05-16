from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/migrations", tags=["migrations"])

__all__ = ["router"]
