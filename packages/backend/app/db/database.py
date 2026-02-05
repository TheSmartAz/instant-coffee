from __future__ import annotations

from typing import Optional

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from ..config import get_settings


class Database:
    def __init__(self, url: Optional[str] = None) -> None:
        settings = get_settings()
        resolved_url = url or settings.database_url
        connect_args = {}
        if resolved_url.startswith("sqlite"):
            connect_args = {"check_same_thread": False, "timeout": 30}
        self.url = resolved_url
        self.engine = create_engine(
            self.url,
            connect_args=connect_args,
            pool_pre_ping=True,
            future=True,
        )
        if resolved_url.startswith("sqlite"):
            @event.listens_for(self.engine, "connect")
            def _set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
                cursor = dbapi_connection.cursor()
                try:
                    cursor.execute("PRAGMA journal_mode=WAL;")
                    cursor.execute("PRAGMA synchronous=NORMAL;")
                    cursor.execute("PRAGMA busy_timeout=30000;")
                finally:
                    cursor.close()
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
