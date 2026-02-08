import asyncio
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import pytest

from app.schemas.scenario import DataModel, EntityDefinition, FieldDefinition, Relation
from app.services.app_data_store import AppDataStore, TYPE_MAP, schema_name_for_session


class FakeRecord(dict):
    pass


class FakeConnection:
    def __init__(self, db: dict[str, Any]) -> None:
        self.db = db
        self.search_path: str | None = None

    async def execute(self, query: str, *args: Any) -> str:
        normalized = " ".join(query.strip().split())

        if normalized.startswith("SET search_path TO"):
            part = normalized[len("SET search_path TO ") :].split(",", 1)[0].strip()
            self.search_path = part.strip('"')
            return "SET"

        if normalized.startswith("CREATE SCHEMA IF NOT EXISTS"):
            schema = _extract_quoted_identifier(normalized)
            self.db.setdefault("schemas", {}).setdefault(schema, {})
            return "CREATE SCHEMA"

        if normalized.startswith("DROP SCHEMA IF EXISTS"):
            schema = _extract_quoted_identifier(normalized)
            self.db.setdefault("schemas", {}).pop(schema, None)
            return "DROP SCHEMA"

        if normalized.startswith("CREATE TABLE IF NOT EXISTS"):
            if self.search_path is None:
                raise RuntimeError("search_path not set")
            table = normalized.split()[5].strip('"')
            payload = normalized.split("(", 1)[1].rsplit(")", 1)[0]
            cols = [chunk.strip() for chunk in payload.split(",")]
            schema = self.db.setdefault("schemas", {}).setdefault(self.search_path, {})
            tables = schema.setdefault("tables", {})
            table_meta = tables.setdefault(table, {"columns": {}, "rows": [], "next_id": 1})
            for col in cols:
                name = col.split()[0].strip('"')
                if name == "id":
                    udt_name = "int4"
                    data_type = "integer"
                elif name in {"created_at", "updated_at"}:
                    udt_name = "timestamptz"
                    data_type = "timestamp with time zone"
                else:
                    udt_name, data_type = _parse_column_type(col)
                table_meta["columns"].setdefault(name, {"udt_name": udt_name, "data_type": data_type})
            return "CREATE TABLE"

        if normalized.startswith("ALTER TABLE") and "ADD COLUMN IF NOT EXISTS" in normalized:
            if self.search_path is None:
                raise RuntimeError("search_path not set")
            table = normalized.split()[2].strip('"')
            after_add = normalized.split("ADD COLUMN IF NOT EXISTS", 1)[1].strip()
            column_token, type_token = after_add.split(None, 1)
            column = column_token.strip('"')
            pg_type = type_token.split()[0]
            schema = self.db.setdefault("schemas", {}).setdefault(self.search_path, {})
            table_meta = schema.setdefault("tables", {}).setdefault(
                table,
                {"columns": {}, "rows": [], "next_id": 1},
            )
            udt_name, data_type = _map_type(pg_type)
            table_meta["columns"].setdefault(column, {"udt_name": udt_name, "data_type": data_type})
            return "ALTER TABLE"

        raise AssertionError(f"Unsupported execute query: {query}")

    async def fetch(self, query: str, *args: Any):
        normalized = " ".join(query.strip().split())

        if "FROM information_schema.tables" in normalized:
            schema_name = args[0]
            schema = self.db.setdefault("schemas", {}).get(schema_name, {})
            table_names = sorted(schema.get("tables", {}).keys())
            return [FakeRecord({"table_name": name}) for name in table_names]

        if "FROM information_schema.columns" in normalized:
            schema_name = args[0]
            table_name = args[1]
            schema = self.db.setdefault("schemas", {}).get(schema_name, {})
            table = schema.get("tables", {}).get(table_name, {})
            columns = table.get("columns", {})
            records = []
            for name, meta in columns.items():
                records.append(
                    FakeRecord(
                        {
                            "column_name": name,
                            "data_type": meta.get("data_type", "text"),
                            "udt_name": meta.get("udt_name", "text"),
                            "is_nullable": "YES",
                            "column_default": None,
                        }
                    )
                )
            return records

        if normalized.startswith("SELECT * FROM"):
            schema_name, table_name = _extract_schema_and_table(normalized)
            limit = int(args[0])
            offset = int(args[1])
            order_column = normalized.split("ORDER BY", 1)[1].split()[0].strip('"')
            desc = " DESC " in f" {normalized} "
            table = self.db["schemas"][schema_name]["tables"][table_name]
            rows = list(table["rows"])
            rows.sort(key=lambda row: row.get(order_column), reverse=desc)
            sliced = rows[offset : offset + limit]
            return [FakeRecord(dict(row)) for row in sliced]

        if normalized.startswith("SELECT") and "GROUP BY" in normalized and "AS bucket" in normalized:
            schema_name, table_name = _extract_schema_and_table(normalized)
            column = normalized.split("SELECT", 1)[1].split("AS bucket", 1)[0].strip().strip('"')
            table = self.db["schemas"][schema_name]["tables"][table_name]
            counts: dict[Any, int] = {}
            for row in table["rows"]:
                key = row.get(column)
                counts[key] = counts.get(key, 0) + 1
            return [FakeRecord({"bucket": key, "count": value}) for key, value in counts.items()]

        raise AssertionError(f"Unsupported fetch query: {query}")

    async def fetchrow(self, query: str, *args: Any):
        normalized = " ".join(query.strip().split())

        if normalized.startswith("INSERT INTO") and "RETURNING *" in normalized:
            schema_name, table_name = _extract_schema_and_table(normalized)
            table = self.db["schemas"][schema_name]["tables"][table_name]
            record: dict[str, Any] = {
                "id": table["next_id"],
                "created_at": "now",
                "updated_at": "now",
            }
            table["next_id"] += 1
            if "DEFAULT VALUES" not in normalized:
                raw_cols = normalized.split("(", 1)[1].split(")", 1)[0]
                columns = [part.strip().strip('"') for part in raw_cols.split(",")]
                for idx, column in enumerate(columns):
                    value = args[idx]
                    if isinstance(value, str) and value.startswith("{"):
                        try:
                            value = __import__("json").loads(value)
                        except Exception:
                            pass
                    record[column] = value
            table["rows"].append(record)
            return FakeRecord(record)

        if normalized.startswith("DELETE FROM") and "RETURNING" in normalized:
            schema_name, table_name = _extract_schema_and_table(normalized)
            target_id = int(args[0])
            table = self.db["schemas"][schema_name]["tables"][table_name]
            for idx, row in enumerate(table["rows"]):
                if int(row.get("id")) == target_id:
                    table["rows"].pop(idx)
                    return FakeRecord({"id": target_id})
            return None

        if normalized.startswith("SELECT COALESCE(SUM(") and "FROM" in normalized:
            schema_name, table_name = _extract_schema_and_table(normalized)
            column = normalized.split("SUM(", 1)[1].split(")", 1)[0].strip('"')
            table = self.db["schemas"][schema_name]["tables"][table_name]
            values = [row.get(column) for row in table["rows"] if row.get(column) is not None]
            if not values:
                return FakeRecord({"sum_value": Decimal("0"), "avg_value": None, "min_value": None, "max_value": None})
            total = sum(Decimal(str(v)) for v in values)
            avg = total / Decimal(str(len(values)))
            return FakeRecord(
                {
                    "sum_value": total,
                    "avg_value": avg,
                    "min_value": min(values),
                    "max_value": max(values),
                }
            )

        raise AssertionError(f"Unsupported fetchrow query: {query}")

    async def fetchval(self, query: str, *args: Any):
        normalized = " ".join(query.strip().split())
        if normalized.startswith("SELECT COUNT(*) FROM"):
            schema_name, table_name = _extract_schema_and_table(normalized)
            table = self.db["schemas"][schema_name]["tables"][table_name]
            return len(table["rows"])
        raise AssertionError(f"Unsupported fetchval query: {query}")


class FakeAcquire:
    def __init__(self, conn: FakeConnection) -> None:
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakePool:
    def __init__(self) -> None:
        self.db: dict[str, Any] = {"schemas": {}}
        self.closed = False
        self.conn = FakeConnection(self.db)

    def acquire(self):
        return FakeAcquire(self.conn)

    async def close(self) -> None:
        self.closed = True


@dataclass
class UnknownField:
    name: str
    type: str
    required: bool = False


@dataclass
class UnknownEntity:
    fields: list[UnknownField]


@dataclass
class UnknownModel:
    entities: dict[str, UnknownEntity]


def _extract_quoted_identifier(query: str) -> str:
    first = query.index('"')
    second = query.index('"', first + 1)
    return query[first + 1 : second]


def _map_type(pg_type: str) -> tuple[str, str]:
    mapping = {
        "TEXT": ("text", "text"),
        "NUMERIC": ("numeric", "numeric"),
        "BOOLEAN": ("bool", "boolean"),
        "JSONB": ("jsonb", "jsonb"),
        "TIMESTAMPTZ": ("timestamptz", "timestamp with time zone"),
        "SERIAL": ("int4", "integer"),
    }
    return mapping.get(pg_type.upper(), ("text", "text"))


def _parse_column_type(definition: str) -> tuple[str, str]:
    parts = definition.split()
    if len(parts) < 2:
        return "text", "text"
    return _map_type(parts[1])


def _extract_schema_and_table(query: str) -> tuple[str, str]:
    marker = "FROM " if "FROM " in query else "INTO "
    target = query.split(marker, 1)[1].split()[0]
    if target.endswith("("):
        target = target[:-1]
    schema, table = target.split(".", 1)
    return schema.strip('"'), table.strip('"')


@pytest.fixture
def fake_store() -> AppDataStore:
    return AppDataStore(dsn="postgresql://example", pool=FakePool())


def test_type_map_has_expected_values():
    assert TYPE_MAP == {
        "string": "TEXT",
        "number": "NUMERIC",
        "boolean": "BOOLEAN",
        "array": "JSONB",
        "object": "JSONB",
    }


def test_schema_name_sanitization_and_truncation():
    name = schema_name_for_session("Session-ABC.123")
    assert name == "app_session_abc_123"

    long_name = schema_name_for_session("X" * 120)
    assert long_name.startswith("app_")
    assert len(long_name) <= 63


def test_create_schema_and_drop_schema(fake_store: AppDataStore):
    async def run():
        schema = await fake_store.create_schema("session-1")
        assert schema == "app_session_1"
        assert "app_session_1" in fake_store.pool.db["schemas"]
        deleted = await fake_store.drop_schema("session-1")
        assert deleted is True
        assert "app_session_1" not in fake_store.pool.db["schemas"]

    asyncio.run(run())


def test_create_tables_type_mapping_and_autocolumns(fake_store: AppDataStore):
    data_model = DataModel(
        entities={
            "Product": EntityDefinition(
                fields=[
                    FieldDefinition(name="name", type="string", required=True),
                    FieldDefinition(name="price", type="number", required=True),
                    FieldDefinition(name="active", type="boolean", required=False),
                    FieldDefinition(name="tags", type="array", required=False),
                    FieldDefinition(name="meta", type="object", required=False),
                ],
                primaryKey="id",
            )
        },
        relations=[],
    )

    async def run():
        summary = await fake_store.create_tables("s1", data_model)
        assert summary["entities_added"] == ["Product"]
        tables = await fake_store.list_tables("s1")
        product = next(table for table in tables["tables"] if table["name"] == "Product")
        column_types = {col["name"]: col["udt_name"] for col in product["columns"]}
        assert column_types["id"] == "int4"
        assert column_types["created_at"] == "timestamptz"
        assert column_types["updated_at"] == "timestamptz"
        assert column_types["name"] == "text"
        assert column_types["price"] == "numeric"
        assert column_types["active"] == "bool"
        assert column_types["tags"] == "jsonb"
        assert column_types["meta"] == "jsonb"

    asyncio.run(run())


def test_unknown_field_type_fallback_to_text(fake_store: AppDataStore):
    model = UnknownModel(
        entities={
            "Thing": UnknownEntity(
                fields=[
                    UnknownField(name="kind", type="mystery"),
                ]
            )
        }
    )

    async def run():
        summary = await fake_store.create_tables("u1", model)
        assert summary["entities_added"] == ["Thing"]
        tables = await fake_store.list_tables("u1")
        thing = next(table for table in tables["tables"] if table["name"] == "Thing")
        types = {col["name"]: col["udt_name"] for col in thing["columns"]}
        assert types["kind"] == "text"

    asyncio.run(run())


def test_insert_query_delete_and_stats(fake_store: AppDataStore):
    model = DataModel(
        entities={
            "Order": EntityDefinition(
                fields=[
                    FieldDefinition(name="price", type="number", required=True),
                    FieldDefinition(name="paid", type="boolean", required=False),
                    FieldDefinition(name="items", type="array", required=False),
                ],
                primaryKey="id",
            )
        },
        relations=[],
    )

    async def run():
        await fake_store.create_tables("s2", model)
        created1 = await fake_store.insert_record("s2", "Order", {"price": 10, "paid": True, "items": [1, 2]})
        created2 = await fake_store.insert_record("s2", "Order", {"price": 20, "paid": False})
        assert created1["id"] == 1
        assert created2["id"] == 2

        page = await fake_store.query_table("s2", "Order", limit=500, offset=0, order_by="-id")
        assert page["limit"] == 200
        assert [row["id"] for row in page["rows"]] == [2, 1]

        stats = await fake_store.get_table_stats("s2", "Order")
        assert stats["count"] == 2
        assert str(stats["numeric"]["price"]["sum"]) == "30"
        assert stats["boolean"]["paid"]["true"] == 1
        assert stats["boolean"]["paid"]["false"] == 1

        deleted = await fake_store.delete_record("s2", "Order", 1)
        assert deleted is True
        page_after = await fake_store.query_table("s2", "Order")
        assert [row["id"] for row in page_after["rows"]] == [2]

    asyncio.run(run())


def test_sql_injection_like_identifiers_blocked(fake_store: AppDataStore):
    model = DataModel(
        entities={
            "Task": EntityDefinition(
                fields=[FieldDefinition(name="title", type="string", required=True)],
                primaryKey="id",
            )
        },
        relations=[],
    )

    async def run():
        await fake_store.create_tables("sec", model)
        with pytest.raises(ValueError):
            await fake_store.query_table("sec", "Task;DROP")
        with pytest.raises(ValueError):
            await fake_store.query_table("sec", "Task", order_by="title;DROP")
        with pytest.raises(ValueError):
            await fake_store.insert_record("sec", "Task", {"title.bad": "x"})
        with pytest.raises(ValueError):
            await fake_store.insert_record("sec", "Task", {"title": "x", "other": "y"})

    asyncio.run(run())


def test_data_model_evolution_add_entity_and_field(fake_store: AppDataStore):
    initial = DataModel(
        entities={
            "Project": EntityDefinition(
                fields=[FieldDefinition(name="name", type="string", required=True)],
                primaryKey="id",
            )
        },
        relations=[],
    )
    evolved = DataModel(
        entities={
            "Project": EntityDefinition(
                fields=[
                    FieldDefinition(name="name", type="string", required=True),
                    FieldDefinition(name="budget", type="number", required=False),
                ],
                primaryKey="id",
            ),
            "Sprint": EntityDefinition(
                fields=[FieldDefinition(name="title", type="string", required=True)],
                primaryKey="id",
            ),
        },
        relations=[],
    )

    async def run():
        await fake_store.create_tables("evo", initial)
        summary = await fake_store.create_tables("evo", evolved)
        assert summary["entities_added"] == ["Sprint"]
        assert summary["columns_added"]["Project"] == ["budget"]
        await fake_store.insert_record("evo", "Project", {"name": "A", "budget": 12})
        rows = await fake_store.query_table("evo", "Project")
        assert rows["rows"][0]["name"] == "A"
        assert rows["rows"][0]["budget"] == 12

    asyncio.run(run())


def test_removed_fields_marked_deprecated(fake_store: AppDataStore):
    initial = DataModel(
        entities={
            "Card": EntityDefinition(
                fields=[
                    FieldDefinition(name="title", type="string", required=True),
                    FieldDefinition(name="legacy", type="string", required=False),
                ],
                primaryKey="id",
            )
        },
        relations=[],
    )
    reduced = DataModel(
        entities={
            "Card": EntityDefinition(
                fields=[FieldDefinition(name="title", type="string", required=True)],
                primaryKey="id",
            )
        },
        relations=[],
    )

    async def run():
        await fake_store.create_tables("dep", initial)
        summary = await fake_store.create_tables("dep", reduced)
        assert summary["columns_deprecated"]["Card"] == ["legacy"]

    asyncio.run(run())


def test_cross_schema_identifier_rejected(fake_store: AppDataStore):
    model = DataModel(
        entities={
            "Item": EntityDefinition(
                fields=[FieldDefinition(name="name", type="string", required=True)],
                primaryKey="id",
            )
        },
        relations=[],
    )

    async def run():
        await fake_store.create_tables("cross", model)
        with pytest.raises(ValueError):
            await fake_store.query_table("cross", "public.Item")

    asyncio.run(run())


def test_pool_configuration_cap_and_close():
    store = AppDataStore(
        dsn="postgresql://example",
        min_size=50,
        max_size=999,
        pool=FakePool(),
    )
    assert store._min_size == 15
    assert store._max_size == 15

    async def run():
        await store.close_pool()
        assert store.pool is None

    asyncio.run(run())
