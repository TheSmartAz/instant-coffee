from sqlalchemy import inspect, text

from app.db.database import Database
from app.db.migrations import (
    migrate_v04_product_doc_pending_pages,
    migrate_v06_session_metadata,
    migrate_v08_event_run_columns,
    migrate_v08_run_model,
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
