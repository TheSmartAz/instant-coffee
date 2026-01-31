from __future__ import annotations

from .base import Base
from .database import Database, get_database


def init_db(database: Database | None = None) -> None:
    db_instance = database or get_database()
    Base.metadata.create_all(bind=db_instance.engine)


__all__ = ["init_db"]
