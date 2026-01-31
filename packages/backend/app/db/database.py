from __future__ import annotations

from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ..config import get_settings


class Database:
    def __init__(self, url: Optional[str] = None) -> None:
        settings = get_settings()
        resolved_url = url or settings.database_url
        connect_args = {}
        if resolved_url.startswith("sqlite"):
            connect_args = {"check_same_thread": False}
        self.url = resolved_url
        self.engine = create_engine(self.url, connect_args=connect_args, future=True)
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine,
            future=True,
        )

    def session(self):
        return self.SessionLocal()


_database: Optional[Database] = None


def get_database() -> Database:
    global _database
    if _database is None:
        _database = Database()
    return _database


def reset_database() -> None:
    global _database
    _database = None


__all__ = ["Database", "get_database", "reset_database"]
