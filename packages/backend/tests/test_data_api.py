import uuid
from typing import Any

from fastapi.testclient import TestClient

from app.config import refresh_settings
from app.db.database import reset_database
from app.db.migrations import init_db
from app.db.models import Session as SessionModel
from app.db.utils import get_db


class FakeAppDataStore:
    def __init__(self) -> None:
        self.enabled = True
        self.drop_calls: list[str] = []
        self.schemas: dict[str, dict[str, Any]] = {}

    async def list_tables(self, session_id: str) -> dict[str, Any]:
        schema = self.schemas.get(session_id)
        if schema is None:
            raise ValueError("Table not found")
        return {
            "schema": f"app_{session_id}",
            "tables": [
                {
                    "name": table_name,
                    "columns": [
                        {"name": col, "udt_name": meta["type"], "data_type": meta["type"]}
                        for col, meta in table["columns"].items()
                    ],
                }
                for table_name, table in schema.items()
            ],
        }

    async def query_table(
        self,
        session_id: str,
        table: str,
        *,
        limit: int = 50,
        offset: int = 0,
        order_by: str | None = None,
    ) -> dict[str, Any]:
        table_meta = self._table(session_id, table)
        if order_by and ";" in order_by:
            raise ValueError("Invalid order_by identifier")

        actual_limit = min(max(int(limit), 1), 200)
        actual_offset = max(int(offset), 0)

        records = list(table_meta["rows"])
        order_column = "id"
        reverse = False
        if order_by:
            value = order_by.strip()
            if value.startswith("-"):
                reverse = True
                order_column = value[1:]
            else:
                order_column = value
            if order_column not in table_meta["columns"] and order_column not in {"id", "created_at", "updated_at"}:
                raise ValueError("Unsupported order_by column")
        records.sort(key=lambda row: row.get(order_column), reverse=reverse)
        page = records[actual_offset : actual_offset + actual_limit]
        return {
            "rows": page,
            "total": len(records),
            "limit": actual_limit,
            "offset": actual_offset,
            "order_by": {"column": order_column, "direction": "DESC" if reverse else "ASC"},
        }

    async def insert_record(self, session_id: str, table: str, data: dict[str, Any]) -> dict[str, Any]:
        table_meta = self._table(session_id, table)
        allowed = set(table_meta["columns"]) | {"id", "created_at", "updated_at"}
        for key in data.keys():
            if "." in key:
                raise ValueError("column identifier cannot contain '.'")
            if key not in allowed:
                raise ValueError(f"Unknown column '{key}'")

        record = {
            "id": table_meta["next_id"],
            "created_at": "now",
            "updated_at": "now",
        }
        table_meta["next_id"] += 1
        record.update(data)
        table_meta["rows"].append(record)
        return record

    async def delete_record(self, session_id: str, table: str, row_id: int) -> bool:
        table_meta = self._table(session_id, table)
        for idx, row in enumerate(table_meta["rows"]):
            if row["id"] == row_id:
                table_meta["rows"].pop(idx)
                return True
        return False

    async def get_table_stats(self, session_id: str, table: str) -> dict[str, Any]:
        table_meta = self._table(session_id, table)
        numeric: dict[str, dict[str, Any]] = {}
        for column, info in table_meta["columns"].items():
            if info["type"] == "numeric":
                values = [row[column] for row in table_meta["rows"] if row.get(column) is not None]
                if values:
                    numeric[column] = {
                        "sum": sum(values),
                        "avg": sum(values) / len(values),
                        "min": min(values),
                        "max": max(values),
                    }
        return {
            "table": table,
            "count": len(table_meta["rows"]),
            "numeric": numeric,
            "boolean": {},
        }

    async def drop_schema(self, session_id: str) -> bool:
        self.drop_calls.append(session_id)
        self.schemas.pop(session_id, None)
        return True

    async def initialize_pool(self) -> None:
        return None

    async def close_pool(self) -> None:
        return None

    def _table(self, session_id: str, table: str) -> dict[str, Any]:
        if "." in table:
            raise ValueError("table identifier cannot contain '.'")
        schema = self.schemas.get(session_id)
        if schema is None or table not in schema:
            raise ValueError("Table not found")
        return schema[table]



def _create_app(tmp_path, monkeypatch, store: FakeAppDataStore):
    db_path = tmp_path / "data_api.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("DEFAULT_BASE_URL", "http://localhost")
    monkeypatch.setenv("DEFAULT_KEY", "test-key")
    refresh_settings()
    reset_database()
    init_db()

    import app.services.app_data_store as store_module

    monkeypatch.setattr(store_module, "get_app_data_store", lambda: store)
    monkeypatch.setattr("app.api.data.get_app_data_store", lambda: store)
    monkeypatch.setattr("app.api.sessions.get_app_data_store", lambda: store)

    from app.main import create_app

    return create_app()


def _seed_session(session_id: str) -> None:
    with get_db() as db:
        db.add(SessionModel(id=session_id, title="Data API Session"))
        db.commit()


def _seed_store(store: FakeAppDataStore, session_id: str) -> None:
    store.schemas[session_id] = {
        "Product": {
            "columns": {
                "name": {"type": "text"},
                "price": {"type": "numeric"},
            },
            "rows": [
                {"id": 1, "name": "A", "price": 10, "created_at": "now", "updated_at": "now"},
                {"id": 2, "name": "B", "price": 20, "created_at": "now", "updated_at": "now"},
            ],
            "next_id": 3,
        }
    }


def test_data_api_tables_query_insert_delete_stats(tmp_path, monkeypatch):
    store = FakeAppDataStore()
    app = _create_app(tmp_path, monkeypatch, store)
    session_id = uuid.uuid4().hex
    _seed_session(session_id)
    _seed_store(store, session_id)

    with TestClient(app) as client:
        tables_resp = client.get(f"/api/sessions/{session_id}/data/tables")
        assert tables_resp.status_code == 200
        tables_payload = tables_resp.json()
        assert tables_payload["tables"][0]["name"] == "Product"

        query_resp = client.get(
            f"/api/sessions/{session_id}/data/Product",
            params={"limit": 500, "offset": 0, "order_by": "-id"},
        )
        assert query_resp.status_code == 200
        query_payload = query_resp.json()
        assert query_payload["limit"] == 200
        assert query_payload["total"] == 2
        assert [row["id"] for row in query_payload["records"]] == [2, 1]

        insert_resp = client.post(
            f"/api/sessions/{session_id}/data/Product",
            json={"name": "C", "price": 30},
        )
        assert insert_resp.status_code == 200
        assert insert_resp.json()["record"]["id"] == 3

        stats_resp = client.get(f"/api/sessions/{session_id}/data/Product/stats")
        assert stats_resp.status_code == 200
        stats_payload = stats_resp.json()
        assert stats_payload["count"] == 3
        assert stats_payload["numeric"]["price"]["sum"] == 60

        delete_resp = client.delete(f"/api/sessions/{session_id}/data/Product/2")
        assert delete_resp.status_code == 200
        assert delete_resp.json()["deleted"] is True

        delete_missing = client.delete(f"/api/sessions/{session_id}/data/Product/999")
        assert delete_missing.status_code == 404


def test_data_api_validation_and_errors(tmp_path, monkeypatch):
    store = FakeAppDataStore()
    app = _create_app(tmp_path, monkeypatch, store)
    session_id = uuid.uuid4().hex
    _seed_session(session_id)
    _seed_store(store, session_id)

    with TestClient(app) as client:
        missing_session = client.get(f"/api/sessions/{uuid.uuid4().hex}/data/tables")
        assert missing_session.status_code == 404

        missing_table = client.get(f"/api/sessions/{session_id}/data/Unknown")
        assert missing_table.status_code == 404

        bad_order = client.get(
            f"/api/sessions/{session_id}/data/Product",
            params={"order_by": "name;DROP TABLE"},
        )
        assert bad_order.status_code == 400

        bad_body = client.post(
            f"/api/sessions/{session_id}/data/Product",
            json=[{"name": "x"}],
        )
        assert bad_body.status_code == 422

        cross_schema = client.get(f"/api/sessions/{session_id}/data/public.Product")
        assert cross_schema.status_code == 404


def test_session_delete_triggers_app_data_schema_cleanup(tmp_path, monkeypatch):
    store = FakeAppDataStore()
    app = _create_app(tmp_path, monkeypatch, store)
    session_id = uuid.uuid4().hex
    _seed_session(session_id)
    _seed_store(store, session_id)

    with TestClient(app) as client:
        response = client.delete(f"/api/sessions/{session_id}")
        assert response.status_code == 200
        assert response.json()["deleted"] is True

    assert store.drop_calls == [session_id]
