from __future__ import annotations

from typing import Optional

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from ..config import get_settings


class Database:
    def __init__(self, url: Optional[str] = None) -> None:
        settings = get_settings()
        resolved_url = url or settings.database_url
        # Railway/Render may provide postgres:// which SQLAlchemy 2.0 doesn't accept
        if resolved_url.startswith("postgres://"):
            resolved_url = resolved_url.replace("postgres://", "postgresql://", 1)
        connect_args = {}
        engine_kwargs: dict = {
            "pool_pre_ping": True,
            "future": True,
        }
        if resolved_url.startswith("sqlite"):
            connect_args = {"check_same_thread": False, "timeout": 30}
        elif resolved_url.startswith("postgresql"):
            # Fail fast when DB connectivity degrades instead of hanging requests.
            connect_args = {"connect_timeout": 5}
            pool_min = max(2, int(settings.app_data_pg_pool_min_size))
            pool_max = max(pool_min + 1, int(settings.app_data_pg_pool_max_size))
            engine_kwargs.update(
                {
                    "pool_size": pool_min,
                    "max_overflow": max(1, pool_max - pool_min),
                    "pool_timeout": 5,
                    "pool_recycle": 1800,
                    "pool_use_lifo": True,
                }
            )
        self.url = resolved_url
        engine_kwargs["connect_args"] = connect_args
        self.engine = create_engine(
            self.url,
            **engine_kwargs,
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
