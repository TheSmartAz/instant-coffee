from sqlalchemy import inspect, text

from app.db.database import Database
from app.db.migrations import migrate_v04_product_doc_pending_pages, migrate_v06_session_metadata


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
