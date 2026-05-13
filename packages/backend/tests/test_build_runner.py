from __future__ import annotations

import asyncio
import uuid

import pytest

from app.db.database import Database
from app.db.migrations import init_db
from app.db.models import Session as SessionModel
from app.db.utils import get_db, transaction_scope
from app.renderer.builder import BuildError
from app.services.build_runner import BuildRunner


def _create_database(tmp_path, name: str) -> Database:
    db_path = tmp_path / name
    database = Database(f"sqlite:///{db_path}")
    init_db(database)
    return database


def test_fallback_build_payload_wraps_generate_node_failures(tmp_path, monkeypatch) -> None:
    database = _create_database(tmp_path, "build-runner.db")
    session_id = uuid.uuid4().hex
    with transaction_scope(database) as session:
        session.add(SessionModel(id=session_id, title="Build Runner Test"))

    async def boom(_state):
        raise RuntimeError("node exploded")

    monkeypatch.setattr("app.services.build_runner.generate_node", boom)

    with get_db(database) as session:
        runner = BuildRunner(session)

        with pytest.raises(BuildError) as exc_info:
            asyncio.run(runner._fallback_build_payload(session_id, {}))

    assert exc_info.value.stage == "fallback_generate_payload"
    assert "node exploded" in str(exc_info.value)
