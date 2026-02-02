from sqlalchemy import inspect, text

from app.db.database import Database
from app.db.migrations import migrate_v04_product_doc_pending_pages


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
