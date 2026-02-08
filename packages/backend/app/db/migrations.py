from __future__ import annotations

from sqlalchemy import inspect, text

from .base import Base
from .database import Database, get_database
from .models import (
    Page,
    PageVersion,
    ProductDoc,
    ProductDocHistory,
    ProjectSnapshot,
    ProjectSnapshotDoc,
    ProjectSnapshotPage,
    Session,
    SessionEvent,
    SessionEventSequence,
    SessionRun,
    VersionSource,
)
from ..services.page_version import PageVersionService
from ..services.product_doc import ProductDocService
from ..services.project_snapshot import ProjectSnapshotService


def init_db(database: Database | None = None) -> None:
    db_instance = database or get_database()
    Base.metadata.create_all(bind=db_instance.engine)
    migrate_v04_product_doc_pending_pages(db_instance)
    migrate_v05_version_models(db_instance)
    migrate_v06_indexes(db_instance)
    migrate_v06_session_metadata(db_instance)
    migrate_v07_graph_state(db_instance)
    migrate_v08_run_model(db_instance)
    migrate_v08_event_run_columns(db_instance)


def migrate_v04_product_doc_pages(database: Database | None = None) -> None:
    db_instance = database or get_database()
    Base.metadata.create_all(
        bind=db_instance.engine,
        tables=[
            ProductDoc.__table__,
            Page.__table__,
            PageVersion.__table__,
        ],
    )
    migrate_v04_product_doc_pending_pages(db_instance)


def migrate_v04_product_doc_pending_pages(database: Database | None = None) -> None:
    db_instance = database or get_database()
    engine = db_instance.engine
    inspector = inspect(engine)
    if "product_docs" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("product_docs")}
    if "pending_regeneration_pages" in columns:
        return

    if engine.dialect.name == "postgresql":
        ddl = (
            "ALTER TABLE product_docs "
            "ADD COLUMN pending_regeneration_pages JSON NOT NULL DEFAULT '[]'::json"
        )
    else:
        ddl = (
            "ALTER TABLE product_docs "
            "ADD COLUMN pending_regeneration_pages JSON NOT NULL DEFAULT '[]'"
        )

    with engine.begin() as connection:
        connection.execute(text(ddl))


def migrate_v05_version_models(database: Database | None = None) -> None:
    db_instance = database or get_database()
    engine = db_instance.engine
    Base.metadata.create_all(
        bind=engine,
        tables=[
            ProductDocHistory.__table__,
            ProjectSnapshot.__table__,
            ProjectSnapshotDoc.__table__,
            ProjectSnapshotPage.__table__,
            SessionEvent.__table__,
            SessionEventSequence.__table__,
        ],
    )
    _migrate_v05_product_doc_version(engine)
    _migrate_v05_page_versions(engine)
    _normalize_v05_sources(engine)
    _backfill_v05_product_doc_history(engine)
    _backfill_v05_initial_snapshots(db_instance)
    _apply_v05_retention(db_instance)


def _ensure_index(engine, table_name: str, index_name: str, columns: list[str]) -> None:
    inspector = inspect(engine)
    if table_name not in inspector.get_table_names():
        return
    existing = {idx.get("name") for idx in inspector.get_indexes(table_name)}
    if index_name in existing:
        return
    cols = ", ".join(columns)
    with engine.begin() as connection:
        connection.execute(
            text(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({cols})")
        )


def migrate_v06_indexes(database: Database | None = None) -> None:
    db_instance = database or get_database()
    engine = db_instance.engine
    _ensure_index(engine, "messages", "idx_messages_session_id", ["session_id"])
    _ensure_index(engine, "messages", "idx_messages_session_ts", ["session_id", "timestamp"])
    _ensure_index(engine, "token_usage", "idx_token_usage_session_id", ["session_id"])
    _ensure_index(engine, "token_usage", "idx_token_usage_session_ts", ["session_id", "timestamp"])
    _ensure_index(engine, "plans", "idx_plans_session_id", ["session_id"])
    _ensure_index(engine, "plans", "idx_plans_status", ["status"])
    _ensure_index(engine, "tasks", "idx_tasks_plan_id", ["plan_id"])
    _ensure_index(engine, "tasks", "idx_tasks_status", ["status"])
    _ensure_index(engine, "page_versions", "idx_page_versions_page_created_at", ["page_id", "created_at"])


def migrate_v06_session_metadata(database: Database | None = None) -> None:
    db_instance = database or get_database()
    engine = db_instance.engine
    inspector = inspect(engine)
    if "sessions" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("sessions")}
    column_defs = {
        "product_type": "VARCHAR(50)",
        "complexity": "VARCHAR(20)",
        "skill_id": "VARCHAR(100)",
        "doc_tier": "VARCHAR(20)",
        "style_reference_mode": "VARCHAR(50)",
        "model_classifier": "VARCHAR(100)",
        "model_writer": "VARCHAR(100)",
        "model_expander": "VARCHAR(100)",
        "model_validator": "VARCHAR(100)",
        "model_style_refiner": "VARCHAR(100)",
    }

    with engine.begin() as connection:
        for column, ddl_type in column_defs.items():
            if column in columns:
                continue
            connection.execute(text(f"ALTER TABLE sessions ADD COLUMN {column} {ddl_type}"))


def migrate_v07_graph_state(database: Database | None = None) -> None:
    db_instance = database or get_database()
    engine = db_instance.engine
    inspector = inspect(engine)
    if "sessions" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("sessions")}
    column_defs = {
        "graph_state": "JSON",
        "build_status": "VARCHAR(20) DEFAULT 'pending'",
        "build_artifacts": "JSON",
        "aesthetic_scores": "JSON",
    }

    with engine.begin() as connection:
        for column, ddl_type in column_defs.items():
            if column in columns:
                continue
            connection.execute(text(f"ALTER TABLE sessions ADD COLUMN {column} {ddl_type}"))
        if "build_status" in column_defs:
            connection.execute(
                text("UPDATE sessions SET build_status = 'pending' WHERE build_status IS NULL")
            )


def migrate_v08_run_model(database: Database | None = None) -> None:
    db_instance = database or get_database()
    engine = db_instance.engine
    inspector = inspect(engine)

    if "session_runs" not in inspector.get_table_names():
        Base.metadata.create_all(bind=engine, tables=[SessionRun.__table__])

    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("session_runs")}
    column_defs = {
        "parent_run_id": "VARCHAR",
        "trigger_source": "VARCHAR(20) NOT NULL DEFAULT 'chat'",
        "status": "VARCHAR(20) NOT NULL DEFAULT 'queued'",
        "input_message": "TEXT",
        "resume_payload": "JSON",
        "checkpoint_thread": "VARCHAR",
        "checkpoint_ns": "VARCHAR",
        "latest_error": "JSON",
        "metrics": "JSON",
        "started_at": "DATETIME",
        "finished_at": "DATETIME",
        "created_at": "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP",
        "updated_at": "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP",
    }

    with engine.begin() as connection:
        for column, ddl_type in column_defs.items():
            if column in columns:
                continue
            connection.execute(text(f"ALTER TABLE session_runs ADD COLUMN {column} {ddl_type}"))

    _ensure_index(
        engine,
        "session_runs",
        "idx_session_runs_session_created",
        ["session_id", "created_at"],
    )
    _ensure_index(engine, "session_runs", "idx_session_runs_status", ["status"])
    _ensure_index(engine, "session_runs", "idx_session_runs_parent", ["parent_run_id"])


def migrate_v08_event_run_columns(database: Database | None = None) -> None:
    db_instance = database or get_database()
    engine = db_instance.engine
    inspector = inspect(engine)

    if "session_events" not in inspector.get_table_names():
        Base.metadata.create_all(bind=engine, tables=[SessionEvent.__table__])

    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("session_events")}
    column_defs = {
        "run_id": "VARCHAR",
        "event_id": "VARCHAR",
    }

    with engine.begin() as connection:
        for column, ddl_type in column_defs.items():
            if column in columns:
                continue
            connection.execute(text(f"ALTER TABLE session_events ADD COLUMN {column} {ddl_type}"))

    _ensure_index(
        engine,
        "session_events",
        "idx_session_event_run_seq",
        ["session_id", "run_id", "seq"],
    )


def _normalize_v05_sources(engine) -> None:
    if engine.dialect.name != "sqlite":
        return
    with engine.begin() as connection:
        for table in (
            "session_events",
            "page_versions",
            "product_doc_histories",
            "project_snapshots",
        ):
            connection.execute(
                text(
                    f"UPDATE {table} "
                    "SET source = lower(source) "
                    "WHERE source IS NOT NULL AND source != lower(source)"
                )
            )


def _migrate_v05_product_doc_version(engine) -> None:
    inspector = inspect(engine)
    if "product_docs" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("product_docs")}
    with engine.begin() as connection:
        if "version" not in columns:
            ddl = "ALTER TABLE product_docs ADD COLUMN version INTEGER NOT NULL DEFAULT 1"
            connection.execute(text(ddl))
        connection.execute(text("UPDATE product_docs SET version = 1 WHERE version IS NULL"))
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "idx_product_doc_session_version "
                "ON product_docs(session_id, version)"
            )
        )


def _migrate_v05_page_versions(engine) -> None:
    inspector = inspect(engine)
    if "page_versions" not in inspector.get_table_names():
        return
    columns = {column["name"]: column for column in inspector.get_columns("page_versions")}

    if engine.dialect.name == "sqlite":
        needs_rebuild = False
        if "html" in columns and columns["html"].get("nullable") is False:
            needs_rebuild = True
        if any(
            name not in columns
            for name in (
                "source",
                "is_pinned",
                "is_released",
                "released_at",
                "payload_pruned_at",
                "fallback_used",
                "fallback_excerpt",
            )
        ):
            needs_rebuild = True
        if needs_rebuild:
            _sqlite_rebuild_page_versions(engine, columns)
        _backfill_v05_page_versions(engine)
        return

    with engine.begin() as connection:
        if engine.dialect.name == "postgresql":
            _ensure_postgres_enum(
                connection,
                "version_source",
                ("auto", "manual", "rollback"),
            )
        source_type = "version_source" if engine.dialect.name == "postgresql" else "VARCHAR(10)"
        source_check = (
            ""
            if engine.dialect.name == "postgresql"
            else " CHECK (source IN ('auto', 'manual', 'rollback'))"
        )
        if "source" not in columns:
            ddl = (
                "ALTER TABLE page_versions "
                f"ADD COLUMN source {source_type} NOT NULL DEFAULT 'auto'{source_check}"
            )
            connection.execute(text(ddl))
        if "is_pinned" not in columns:
            ddl = "ALTER TABLE page_versions ADD COLUMN is_pinned BOOLEAN NOT NULL DEFAULT FALSE"
            connection.execute(text(ddl))
        if "is_released" not in columns:
            ddl = "ALTER TABLE page_versions ADD COLUMN is_released BOOLEAN NOT NULL DEFAULT FALSE"
            connection.execute(text(ddl))
        if "released_at" not in columns:
            ddl = "ALTER TABLE page_versions ADD COLUMN released_at TIMESTAMP"
            connection.execute(text(ddl))
        if "payload_pruned_at" not in columns:
            ddl = "ALTER TABLE page_versions ADD COLUMN payload_pruned_at TIMESTAMP"
            connection.execute(text(ddl))
        if "fallback_used" not in columns:
            ddl = "ALTER TABLE page_versions ADD COLUMN fallback_used BOOLEAN NOT NULL DEFAULT FALSE"
            connection.execute(text(ddl))
        if "fallback_excerpt" not in columns:
            ddl = "ALTER TABLE page_versions ADD COLUMN fallback_excerpt TEXT"
            connection.execute(text(ddl))
        if "html" in columns and columns["html"].get("nullable") is False:
            connection.execute(text("ALTER TABLE page_versions ALTER COLUMN html DROP NOT NULL"))

    _backfill_v05_page_versions(engine)


def _ensure_postgres_enum(connection, enum_name: str, values: tuple[str, ...]) -> None:
    ddl = (
        "DO $$ BEGIN "
        f"IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = '{enum_name}') THEN "
        f"CREATE TYPE {enum_name} AS ENUM ({', '.join([repr(v) for v in values])}); "
        "END IF; "
        "END $$;"
    )
    connection.execute(text(ddl))


def _sqlite_rebuild_page_versions(engine, columns: dict) -> None:
    target_columns = [
        "id",
        "page_id",
        "version",
        "html",
        "description",
        "source",
        "is_pinned",
        "is_released",
        "released_at",
        "payload_pruned_at",
        "fallback_used",
        "fallback_excerpt",
        "created_at",
    ]
    select_exprs = []
    for column in target_columns:
        if column in columns:
            select_exprs.append(column)
            continue
        if column == "source":
            select_exprs.append("'auto'")
        elif column in {"is_pinned", "is_released", "fallback_used"}:
            select_exprs.append("0")
        else:
            select_exprs.append("NULL")

    create_sql = """
        CREATE TABLE page_versions_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            page_id VARCHAR NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
            version INTEGER NOT NULL,
            html TEXT,
            description VARCHAR(500),
            source VARCHAR(10) NOT NULL DEFAULT 'auto' CHECK (source IN ('auto', 'manual', 'rollback')),
            is_pinned BOOLEAN NOT NULL DEFAULT FALSE,
            is_released BOOLEAN NOT NULL DEFAULT FALSE,
            released_at TIMESTAMP,
            payload_pruned_at TIMESTAMP,
            fallback_used BOOLEAN NOT NULL DEFAULT FALSE,
            fallback_excerpt TEXT,
            created_at TIMESTAMP,
            CONSTRAINT uq_page_versions_page_version UNIQUE (page_id, version)
        )
    """
    insert_sql = (
        "INSERT INTO page_versions_new ("
        + ", ".join(target_columns)
        + ") SELECT "
        + ", ".join(select_exprs)
        + " FROM page_versions"
    )

    with engine.connect() as connection:
        connection.execute(text("PRAGMA foreign_keys=OFF"))
        with connection.begin():
            connection.execute(text(create_sql))
            connection.execute(text(insert_sql))
            connection.execute(text("DROP TABLE page_versions"))
            connection.execute(text("ALTER TABLE page_versions_new RENAME TO page_versions"))
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS "
                    "idx_page_versions_page_id ON page_versions(page_id)"
                )
            )
        connection.execute(text("PRAGMA foreign_keys=ON"))


def _backfill_v05_page_versions(engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE page_versions SET source = 'auto' WHERE source IS NULL")
        )
        connection.execute(
            text("UPDATE page_versions SET is_pinned = FALSE WHERE is_pinned IS NULL")
        )
        connection.execute(
            text("UPDATE page_versions SET is_released = FALSE WHERE is_released IS NULL")
        )
        connection.execute(
            text("UPDATE page_versions SET fallback_used = FALSE WHERE fallback_used IS NULL")
        )


def _backfill_v05_product_doc_history(engine) -> None:
    inspector = inspect(engine)
    if "product_docs" not in inspector.get_table_names():
        return
    if "product_doc_histories" not in inspector.get_table_names():
        return
    ddl = """
        INSERT INTO product_doc_histories (
            product_doc_id,
            version,
            content,
            structured,
            source,
            is_pinned,
            is_released,
            released_at,
            created_at
        )
        SELECT
            pd.id,
            pd.version,
            pd.content,
            pd.structured,
            'auto',
            FALSE,
            FALSE,
            NULL,
            COALESCE(pd.updated_at, pd.created_at, CURRENT_TIMESTAMP)
        FROM product_docs pd
        WHERE NOT EXISTS (
            SELECT 1 FROM product_doc_histories h
            WHERE h.product_doc_id = pd.id AND h.version = pd.version
        )
    """
    with engine.begin() as connection:
        connection.execute(text(ddl))


def _backfill_v05_initial_snapshots(database: Database) -> None:
    with database.session() as session:
        sessions = session.query(Session.id).all()
        for (session_id,) in sessions:
            existing = (
                session.query(ProjectSnapshot)
                .filter(ProjectSnapshot.session_id == session_id)
                .first()
            )
            if existing is not None:
                continue
            try:
                ProjectSnapshotService(session).create_snapshot(
                    session_id=session_id,
                    source=VersionSource.AUTO,
                    label=None,
                )
                session.commit()
            except Exception:
                session.rollback()


def _apply_v05_retention(database: Database) -> None:
    with database.session() as session:
        product_docs = session.query(ProductDoc.id).all()
        for (doc_id,) in product_docs:
            try:
                ProductDocService(session).apply_retention_policy(doc_id)
                session.commit()
            except Exception:
                session.rollback()

        pages = session.query(Page.id).all()
        for (page_id,) in pages:
            try:
                PageVersionService(session).apply_retention_policy(page_id)
                session.commit()
            except Exception:
                session.rollback()

        sessions = session.query(Session.id).all()
        for (session_id,) in sessions:
            try:
                ProjectSnapshotService(session).apply_retention_policy(session_id)
                session.commit()
            except Exception:
                session.rollback()


def downgrade_v04_product_doc_pages(database: Database | None = None) -> None:
    db_instance = database or get_database()
    Base.metadata.drop_all(
        bind=db_instance.engine,
        tables=[
            PageVersion.__table__,
            Page.__table__,
            ProductDoc.__table__,
        ],
    )


__all__ = [
    "init_db",
    "migrate_v04_product_doc_pages",
    "migrate_v04_product_doc_pending_pages",
    "migrate_v05_version_models",
    "migrate_v06_session_metadata",
    "migrate_v07_graph_state",
    "migrate_v08_run_model",
    "migrate_v08_event_run_columns",
    "downgrade_v04_product_doc_pages",
]
