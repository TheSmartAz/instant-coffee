import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from app.db.database import Database
from app.db.migrations import (
    migrate_v04_product_doc_pending_pages,
    migrate_v06_session_metadata,
    migrate_v08_event_run_columns,
    migrate_v08_run_model,
    migrate_v12_active_run_index,
)


def test_migrate_adds_pending_regeneration_pages(tmp_path) -> None:
    db_path = tmp_path / "migration.db"
    database = Database(f"sqlite:///{db_path}")

    with database.engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE product_docs (
                    id TEXT PRIMARY KEY,
                    session_id TEXT UNIQUE NOT NULL,
                    content TEXT NOT NULL,
                    structured TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at DATETIME,
                    updated_at DATETIME
                )
                """
            )
        )

    migrate_v04_product_doc_pending_pages(database)

    inspector = inspect(database.engine)
    columns = {column["name"] for column in inspector.get_columns("product_docs")}
    assert "pending_regeneration_pages" in columns


def test_migrate_adds_session_metadata_columns(tmp_path) -> None:
    db_path = tmp_path / "session-meta.db"
    database = Database(f"sqlite:///{db_path}")

    with database.engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE sessions (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at DATETIME,
                    updated_at DATETIME,
                    current_version INTEGER
                )
                """
            )
        )

    migrate_v06_session_metadata(database)

    inspector = inspect(database.engine)
    columns = {column["name"] for column in inspector.get_columns("sessions")}
    for column_name in (
        "product_type",
        "complexity",
        "skill_id",
        "doc_tier",
        "style_reference_mode",
        "model_classifier",
        "model_writer",
        "model_expander",
        "model_validator",
        "model_style_refiner",
    ):
        assert column_name in columns


def test_migrate_v08_creates_session_runs_with_indexes(tmp_path) -> None:
    db_path = tmp_path / "session-runs.db"
    database = Database(f"sqlite:///{db_path}")

    with database.engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE sessions (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at DATETIME,
                    updated_at DATETIME,
                    current_version INTEGER
                )
                """
            )
        )

    migrate_v08_run_model(database)

    inspector = inspect(database.engine)
    assert "session_runs" in inspector.get_table_names()

    columns = {column["name"] for column in inspector.get_columns("session_runs")}
    for column_name in (
        "id",
        "session_id",
        "parent_run_id",
        "trigger_source",
        "status",
        "input_message",
        "resume_payload",
        "checkpoint_thread",
        "checkpoint_ns",
        "latest_error",
        "metrics",
        "started_at",
        "finished_at",
        "created_at",
        "updated_at",
    ):
        assert column_name in columns

    indexes = {index["name"] for index in inspector.get_indexes("session_runs")}
    assert "idx_session_runs_session_created" in indexes
    assert "idx_session_runs_status" in indexes
    assert "idx_session_runs_parent" in indexes
    assert "idx_session_runs_one_active" in indexes


def test_migrate_v08_adds_session_event_run_columns_and_index(tmp_path) -> None:
    db_path = tmp_path / "session-events-v08.db"
    database = Database(f"sqlite:///{db_path}")

    with database.engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE sessions (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at DATETIME,
                    updated_at DATETIME,
                    current_version INTEGER
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE session_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    seq INTEGER NOT NULL,
                    type TEXT NOT NULL,
                    payload JSON,
                    source TEXT NOT NULL,
                    created_at DATETIME
                )
                """
            )
        )

    migrate_v08_event_run_columns(database)

    inspector = inspect(database.engine)
    columns = {column["name"] for column in inspector.get_columns("session_events")}
    assert "run_id" in columns
    assert "event_id" in columns

    indexes = {index["name"] for index in inspector.get_indexes("session_events")}
    assert "idx_session_event_run_seq" in indexes


def test_migrate_v08_is_idempotent(tmp_path) -> None:
    db_path = tmp_path / "session-v08-idempotent.db"
    database = Database(f"sqlite:///{db_path}")

    with database.engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE sessions (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at DATETIME,
                    updated_at DATETIME,
                    current_version INTEGER
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE session_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    seq INTEGER NOT NULL,
                    type TEXT NOT NULL,
                    payload JSON,
                    source TEXT NOT NULL,
                    created_at DATETIME
                )
                """
            )
        )

    migrate_v08_run_model(database)
    migrate_v08_event_run_columns(database)
    migrate_v08_run_model(database)
    migrate_v08_event_run_columns(database)

    inspector = inspect(database.engine)
    run_columns = {column["name"] for column in inspector.get_columns("session_runs")}
    assert "status" in run_columns
    assert "metrics" in run_columns

    event_columns = {column["name"] for column in inspector.get_columns("session_events")}
    assert "run_id" in event_columns
    assert "event_id" in event_columns


def test_migrate_v12_fails_duplicate_active_runs_before_unique_index(tmp_path) -> None:
    db_path = tmp_path / "session-runs-v12-duplicates.db"
    database = Database(f"sqlite:///{db_path}")

    with database.engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE sessions (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at DATETIME,
                    updated_at DATETIME,
                    current_version INTEGER
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE session_runs (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    latest_error JSON,
                    finished_at DATETIME,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO sessions (id, title, created_at, updated_at, current_version)
                VALUES ('s1', 'Session 1', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 0)
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO session_runs (id, session_id, status, created_at, updated_at)
                VALUES
                    ('old-active', 's1', 'queued', '2026-01-01 00:00:00', '2026-01-01 00:00:00'),
                    ('latest-active', 's1', 'running', '2026-01-02 00:00:00', '2026-01-02 00:00:00'),
                    ('waiting', 's1', 'waiting_input', '2026-01-03 00:00:00', '2026-01-03 00:00:00')
                """
            )
        )

    migrate_v12_active_run_index(database)

    inspector = inspect(database.engine)
    indexes = {index["name"] for index in inspector.get_indexes("session_runs")}
    assert "idx_session_runs_one_active" in indexes

    with database.engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id, status, latest_error, finished_at
                FROM session_runs
                ORDER BY id
                """
            )
        ).mappings().all()

    runs = {row["id"]: row for row in rows}
    assert runs["latest-active"]["status"] == "running"
    assert runs["waiting"]["status"] == "waiting_input"
    assert runs["old-active"]["status"] == "failed"
    assert runs["old-active"]["finished_at"] is not None
    assert "duplicate_active_run_migration" in runs["old-active"]["latest_error"]

    with pytest.raises(IntegrityError):
        with database.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO session_runs (id, session_id, status, created_at, updated_at)
                    VALUES ('new-active', 's1', 'queued', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """
                )
            )
