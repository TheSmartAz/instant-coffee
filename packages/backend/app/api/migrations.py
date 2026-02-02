from __future__ import annotations

from fastapi import APIRouter

from ..db.data_migration_v04 import migrate_existing_sessions
from ..db.database import get_database

router = APIRouter(prefix="/api/migrations", tags=["migrations"])


@router.post("/v04")
def migrate_v04() -> dict:
    result = migrate_existing_sessions(get_database())
    return {"success": True, "result": result}


__all__ = ["router"]
