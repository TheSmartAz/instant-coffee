from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

import pytest

from app.db.database import Database
from app.db.migrations import init_db
from app.db.models import Session as SessionModel
from app.db.utils import get_db, transaction_scope
from app.renderer.builder import BuildError
from app.services.build_runner import BuildRunner
from app.config import refresh_settings


def _create_database(tmp_path, name: str) -> Database:
    db_path = tmp_path / name
    database = Database(f"sqlite:///{db_path}")
    init_db(database)
    return database


def test_build_runner_requires_react_workspace_source(tmp_path, monkeypatch) -> None:
    output_dir = tmp_path / "output"
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))
    from app.config import refresh_settings

    refresh_settings()
    database = _create_database(tmp_path, "build-runner.db")
    session_id = uuid.uuid4().hex
    with transaction_scope(database) as session:
        session.add(SessionModel(id=session_id, title="Build Runner Test"))

    with get_db(database) as session:
        runner = BuildRunner(session)

        with pytest.raises(BuildError) as exc_info:
            asyncio.run(runner._build(session_id, {}))

    assert exc_info.value.stage == "workspace_source"
    assert "src/App.tsx" in str(exc_info.value)

    monkeypatch.delenv("OUTPUT_DIR", raising=False)
    refresh_settings()


def test_build_runner_prefers_workspace_source_mode(tmp_path, monkeypatch) -> None:
    output_dir = tmp_path / "output"
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))
    from app.config import refresh_settings

    refresh_settings()
    database = _create_database(tmp_path, "build-runner-source.db")
    session_id = uuid.uuid4().hex
    with transaction_scope(database) as session:
        session.add(SessionModel(id=session_id, title="Build Runner Source Test"))

    workspace = output_dir / session_id / "src"
    workspace.mkdir(parents=True)
    (workspace / "App.tsx").write_text(
        "export default function App() { return <main>Source mode</main> }\n",
        encoding="utf-8",
    )

    async def fake_build_from_workspace_source(self, source_dir, *, pages=None):
        assert source_dir == output_dir / session_id
        return {"status": "success", "pages": ["index.html"], "dist_path": "/tmp/dist"}

    monkeypatch.setattr(
        "app.services.build_runner.ReactSSGBuilder.build_from_workspace_source",
        fake_build_from_workspace_source,
    )

    with get_db(database) as session:
        runner = BuildRunner(session)
        result = asyncio.run(runner._build(session_id, {}))

    assert result["source_mode"] == "workspace"

    monkeypatch.delenv("OUTPUT_DIR", raising=False)
    refresh_settings()


def test_build_runner_uses_configured_output_dir_for_builder_base(tmp_path, monkeypatch) -> None:
    output_dir = tmp_path / "configured-output"
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))
    refresh_settings()
    database = _create_database(tmp_path, "build-runner-base-dir.db")
    session_id = uuid.uuid4().hex
    with transaction_scope(database) as session:
        session.add(SessionModel(id=session_id, title="Build Runner Base Dir Test"))

    workspace = output_dir / session_id / "src"
    workspace.mkdir(parents=True)
    (workspace / "App.tsx").write_text(
        "export default function App() { return <main>Source mode</main> }\n",
        encoding="utf-8",
    )

    captured: dict[str, Path] = {}

    async def fake_build_from_workspace_source(self, source_dir, *, pages=None):
        captured["base_dir"] = self.base_dir
        captured["source_dir"] = source_dir
        return {"status": "success", "pages": ["index.html"], "dist_path": "/tmp/dist"}

    monkeypatch.setattr(
        "app.services.build_runner.ReactSSGBuilder.build_from_workspace_source",
        fake_build_from_workspace_source,
    )

    with get_db(database) as session:
        runner = BuildRunner(session)
        result = asyncio.run(runner._build(session_id, {}))

    assert captured["base_dir"] == output_dir.resolve()
    assert captured["source_dir"] == output_dir / session_id
    assert result["source_mode"] == "workspace"

    monkeypatch.delenv("OUTPUT_DIR", raising=False)
    refresh_settings()
