from __future__ import annotations

from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy.orm import Session as DbSession

from .database import Database, get_database


@contextmanager
def get_db(database: Optional[Database] = None) -> Generator[DbSession, None, None]:
    db_instance = database or get_database()
    session = db_instance.session()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def transaction_scope(database: Optional[Database] = None) -> Generator[DbSession, None, None]:
    db_instance = database or get_database()
    session = db_instance.session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


__all__ = ["get_db", "transaction_scope"]
