from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
import hashlib
import json
import logging
import re
from typing import Any, AsyncIterator

try:
    import asyncpg
except Exception:  # pragma: no cover - optional dependency
    asyncpg = None

from ..config import get_settings

logger = logging.getLogger(__name__)

TYPE_MAP: dict[str, str] = {
    "string": "TEXT",
    "number": "NUMERIC",
    "boolean": "BOOLEAN",
    "array": "JSONB",
    "object": "JSONB",
}

_SCHEMA_PREFIX = "app_"
_POSTGRES_IDENTIFIER_MAX_LENGTH = 63
_POOL_MAX_CONNECTIONS = 15
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")
_RESERVED_COLUMNS = {"id", "created_at", "updated_at"}
_NUMERIC_COLUMN_TYPES = {
    "int2",
    "int4",
    "int8",
    "float4",
    "float8",
    "numeric",
    "decimal",
    "money",
}


@dataclass(slots=True)
class ParsedField:
    name: str
    pg_type: str
    source_type: str


def _is_postgres_url(value: str | None) -> bool:
    if not value:
        return False
    normalized = value.strip().lower()
    return normalized.startswith("postgres://") or normalized.startswith("postgresql://")


def _slugify_session_id(session_id: str) -> str:
    raw = (session_id or "").strip().lower()
    slug = re.sub(r"[^a-z0-9_]", "_", raw)
    return slug or "session"


def schema_name_for_session(session_id: str) -> str:
    slug = _slugify_session_id(session_id)
    candidate = f"{_SCHEMA_PREFIX}{slug}"
    if len(candidate) <= _POSTGRES_IDENTIFIER_MAX_LENGTH:
        return candidate

    digest = hashlib.sha1(session_id.encode("utf-8")).hexdigest()[:8]
    limit = _POSTGRES_IDENTIFIER_MAX_LENGTH - len(_SCHEMA_PREFIX) - len(digest) - 1
    truncated_slug = slug[: max(limit, 1)].rstrip("_") or "s"
    return f"{_SCHEMA_PREFIX}{truncated_slug}_{digest}"


def _quote_ident(identifier: str) -> str:
    return f'"{identifier}"'


def _validate_identifier(identifier: str, *, kind: str) -> str:
    if not isinstance(identifier, str):
        raise ValueError(f"{kind} identifier must be a string")
    value = identifier.strip()
    if not value:
        raise ValueError(f"{kind} identifier cannot be empty")
    if "." in value:
        raise ValueError(f"{kind} identifier cannot contain '.'")
    if not _IDENTIFIER_RE.fullmatch(value):
        raise ValueError(f"Invalid {kind} identifier: {identifier!r}")
    return value


def _extract_mapping(data_model: Any) -> dict[str, Any]:
    if data_model is None:
        return {}
    if isinstance(data_model, dict):
        return data_model
    if hasattr(data_model, "model_dump"):
        dumped = data_model.model_dump(by_alias=True, exclude_none=True)
        if isinstance(dumped, dict):
            return dumped
    entities = getattr(data_model, "entities", None)
    if isinstance(entities, dict):
        return {"entities": entities}
    return {}


def _parse_fields(entity_name: str, entity_payload: Any) -> list[ParsedField]:
    if isinstance(entity_payload, dict):
        raw_fields = entity_payload.get("fields")
    else:
        raw_fields = getattr(entity_payload, "fields", None)

    parsed: list[ParsedField] = []
    if not isinstance(raw_fields, list):
        return parsed

    for raw_field in raw_fields:
        if isinstance(raw_field, dict):
            field_name = raw_field.get("name")
            field_type = raw_field.get("type")
        else:
            field_name = getattr(raw_field, "name", None)
            field_type = getattr(raw_field, "type", None)
        if not isinstance(field_name, str):
            continue
        field_identifier = _validate_identifier(field_name, kind=f"field ({entity_name})")
        normalized_field_type = str(field_type or "string").strip().lower()
        pg_type = TYPE_MAP.get(normalized_field_type)
        if pg_type is None:
            logger.warning(
                "Unknown data_model field type '%s' on %s.%s; fallback to TEXT",
                normalized_field_type,
                entity_name,
                field_identifier,
            )
            pg_type = "TEXT"
        parsed.append(
            ParsedField(name=field_identifier, pg_type=pg_type, source_type=normalized_field_type)
        )
    return parsed


def _parse_data_model(data_model: Any) -> dict[str, list[ParsedField]]:
    mapping = _extract_mapping(data_model)
    entities = mapping.get("entities") if isinstance(mapping, dict) else None
    if not isinstance(entities, dict):
        return {}

    parsed: dict[str, list[ParsedField]] = {}
    for raw_entity_name, entity_payload in entities.items():
        if not isinstance(raw_entity_name, str):
            continue
        entity_name = _validate_identifier(raw_entity_name, kind="table")
        parsed[entity_name] = _parse_fields(entity_name, entity_payload)
    return parsed


def _build_order_by(order_by: str | None, allowed_columns: set[str]) -> tuple[str, str]:
    if not order_by:
        return "id", "ASC"

    value = order_by.strip()
    if not value:
        return "id", "ASC"

    direction = "ASC"
    column = value
    if value.startswith("-"):
        direction = "DESC"
        column = value[1:].strip()
    elif ":" in value:
        raw_column, raw_direction = value.split(":", 1)
        column = raw_column.strip()
        normalized_direction = raw_direction.strip().lower()
        if normalized_direction in {"asc", "desc"}:
            direction = normalized_direction.upper()

    column = _validate_identifier(column, kind="order_by")
    if column not in allowed_columns:
        raise ValueError(f"Unsupported order_by column: {column}")
    return column, direction


class AppDataStore:
    def __init__(
        self,
        *,
        dsn: str | None = None,
        min_size: int = 1,
        max_size: int = 15,
        command_timeout: float = 30.0,
        pool: Any | None = None,
    ) -> None:
        settings = get_settings()
        self._dsn = (dsn or settings.database_url or "").strip()
        self._min_size = max(1, min(int(min_size), _POOL_MAX_CONNECTIONS))
        self._max_size = max(self._min_size, min(int(max_size), _POOL_MAX_CONNECTIONS))
        self._command_timeout = float(command_timeout)
        self._pool = pool
        self._model_whitelist: dict[str, dict[str, set[str]]] = {}

    @property
    def enabled(self) -> bool:
        return self._pool is not None

    @property
    def pool(self) -> Any | None:
        return self._pool

    async def initialize_pool(self) -> None:
        if self._pool is not None:
            return
        if not _is_postgres_url(self._dsn):
            logger.info("AppDataStore pool disabled: DATABASE_URL is not PostgreSQL")
            return
        if asyncpg is None:
            logger.warning("AppDataStore pool disabled: asyncpg is not installed")
            return
        self._pool = await asyncpg.create_pool(
            dsn=self._dsn,
            min_size=self._min_size,
            max_size=self._max_size,
            command_timeout=self._command_timeout,
        )

    async def close_pool(self) -> None:
        if self._pool is None:
            return
        await self._pool.close()
        self._pool = None

    def schema_name(self, session_id: str) -> str:
        return schema_name_for_session(session_id)

    def _require_pool(self) -> Any:
        if self._pool is None:
            raise RuntimeError("AppDataStore pool is not initialized")
        return self._pool

    @asynccontextmanager
    async def _schema_connection(
        self,
        session_id: str,
        *,
        ensure_schema: bool = False,
    ) -> AsyncIterator[tuple[Any, str]]:
        pool = self._require_pool()
        schema = self.schema_name(session_id)
        quoted_schema = _quote_ident(schema)
        async with pool.acquire() as conn:
            if ensure_schema:
                await conn.execute(f"CREATE SCHEMA IF NOT EXISTS {quoted_schema}")
            await conn.execute(f"SET search_path TO {quoted_schema}, public")
            yield conn, schema

    async def create_schema(self, session_id: str) -> str:
        pool = self._require_pool()
        schema = self.schema_name(session_id)
        quoted_schema = _quote_ident(schema)
        async with pool.acquire() as conn:
            await conn.execute(f"CREATE SCHEMA IF NOT EXISTS {quoted_schema}")
        return schema

    async def drop_schema(self, session_id: str) -> bool:
        pool = self._require_pool()
        schema = self.schema_name(session_id)
        quoted_schema = _quote_ident(schema)
        async with pool.acquire() as conn:
            await conn.execute(f"DROP SCHEMA IF EXISTS {quoted_schema} CASCADE")
        self._model_whitelist.pop(schema, None)
        return True

    async def list_tables(self, session_id: str) -> dict[str, Any]:
        pool = self._require_pool()
        schema = self.schema_name(session_id)
        async with pool.acquire() as conn:
            table_rows = await conn.fetch(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = $1
                AND table_type = 'BASE TABLE'
                ORDER BY table_name
                """,
                schema,
            )
            table_names = [str(row["table_name"]) for row in table_rows]

            tables: list[dict[str, Any]] = []
            for table_name in table_names:
                column_rows = await conn.fetch(
                    """
                    SELECT column_name, data_type, udt_name, is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_schema = $1 AND table_name = $2
                    ORDER BY ordinal_position
                    """,
                    schema,
                    table_name,
                )
                tables.append(
                    {
                        "name": table_name,
                        "columns": [
                            {
                                "name": str(col["column_name"]),
                                "data_type": str(col["data_type"]),
                                "udt_name": str(col["udt_name"]),
                                "nullable": str(col["is_nullable"]).upper() == "YES",
                                "default": col["column_default"],
                            }
                            for col in column_rows
                        ],
                    }
                )

        return {"schema": schema, "tables": tables}

    async def create_tables(self, session_id: str, data_model: Any) -> dict[str, Any]:
        model = _parse_data_model(data_model)
        summary: dict[str, Any] = {
            "schema": self.schema_name(session_id),
            "entities_added": [],
            "columns_added": {},
            "columns_deprecated": {},
        }

        whitelist: dict[str, set[str]] = {}
        async with self._schema_connection(session_id, ensure_schema=True) as (conn, schema):
            existing_table_rows = await conn.fetch(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = $1
                AND table_type = 'BASE TABLE'
                """,
                schema,
            )
            existing_tables = {str(row["table_name"]) for row in existing_table_rows}

            for table_name, parsed_fields in model.items():
                quoted_table = _quote_ident(table_name)
                mapped_fields = [field for field in parsed_fields if field.name not in _RESERVED_COLUMNS]
                model_columns = {field.name for field in mapped_fields}
                whitelist[table_name] = set(model_columns) | set(_RESERVED_COLUMNS)

                if table_name not in existing_tables:
                    column_sql = [
                        '"id" SERIAL PRIMARY KEY',
                        '"created_at" TIMESTAMPTZ NOT NULL DEFAULT NOW()',
                        '"updated_at" TIMESTAMPTZ NOT NULL DEFAULT NOW()',
                    ]
                    for field in mapped_fields:
                        column_sql.append(f'{_quote_ident(field.name)} {field.pg_type}')
                    await conn.execute(
                        f"CREATE TABLE IF NOT EXISTS {quoted_table} ({', '.join(column_sql)})"
                    )
                    summary["entities_added"].append(table_name)
                    summary["columns_added"][table_name] = sorted(model_columns)
                    continue

                existing_column_rows = await conn.fetch(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = $1
                    AND table_name = $2
                    """,
                    schema,
                    table_name,
                )
                existing_columns = {str(row["column_name"]) for row in existing_column_rows}

                added_columns: list[str] = []
                for field in mapped_fields:
                    if field.name in existing_columns:
                        continue
                    await conn.execute(
                        f"ALTER TABLE {quoted_table} ADD COLUMN IF NOT EXISTS {_quote_ident(field.name)} {field.pg_type}"
                    )
                    added_columns.append(field.name)
                if added_columns:
                    summary["columns_added"][table_name] = sorted(added_columns)

                deprecated_columns = sorted(
                    column
                    for column in existing_columns
                    if column not in _RESERVED_COLUMNS and column not in model_columns
                )
                if deprecated_columns:
                    summary["columns_deprecated"][table_name] = deprecated_columns

        if summary["entities_added"]:
            summary["entities_added"].sort()

        self._model_whitelist[self.schema_name(session_id)] = whitelist
        logger.info("AppDataStore migration summary: %s", summary)
        return summary

    async def _get_table_columns(self, conn: Any, schema: str, table: str) -> dict[str, dict[str, str]]:
        rows = await conn.fetch(
            """
            SELECT column_name, data_type, udt_name
            FROM information_schema.columns
            WHERE table_schema = $1
            AND table_name = $2
            """,
            schema,
            table,
        )
        return {
            str(row["column_name"]): {
                "data_type": str(row["data_type"]),
                "udt_name": str(row["udt_name"]),
            }
            for row in rows
        }

    def _get_allowed_columns(self, schema: str, table: str, columns: set[str]) -> set[str]:
        whitelist = self._model_whitelist.get(schema)
        if whitelist is None:
            raise ValueError(f"Data model whitelist is not initialized for schema '{schema}'")
        allowed = whitelist.get(table)
        if allowed is None:
            raise ValueError(f"Unknown table '{table}' for schema '{schema}'")
        return set(allowed) & set(columns)

    async def insert_record(self, session_id: str, table: str, data: dict[str, Any]) -> dict[str, Any]:
        table_name = _validate_identifier(table, kind="table")
        payload = data or {}
        if not isinstance(payload, dict):
            raise ValueError("insert payload must be a JSON object")

        async with self._schema_connection(session_id) as (conn, schema):
            column_meta = await self._get_table_columns(conn, schema, table_name)
            if not column_meta:
                raise ValueError(f"Table '{table_name}' not found")

            allowed_columns = self._get_allowed_columns(schema, table_name, set(column_meta.keys()))

            insert_columns: list[str] = []
            placeholders: list[str] = []
            values: list[Any] = []

            for raw_key, raw_value in payload.items():
                column = _validate_identifier(raw_key, kind="column")
                if column in _RESERVED_COLUMNS:
                    continue
                if column not in allowed_columns:
                    raise ValueError(f"Unknown column '{column}' for table '{table_name}'")
                insert_columns.append(column)
                column_udt = column_meta[column]["udt_name"]
                if column_udt == "jsonb" and raw_value is not None:
                    values.append(json.dumps(raw_value, ensure_ascii=False))
                    placeholders.append(f"${len(values)}::jsonb")
                else:
                    values.append(raw_value)
                    placeholders.append(f"${len(values)}")

            quoted_schema = _quote_ident(schema)
            quoted_table = _quote_ident(table_name)
            if insert_columns:
                quoted_columns = ", ".join(_quote_ident(column) for column in insert_columns)
                values_sql = ", ".join(placeholders)
                query = (
                    f"INSERT INTO {quoted_schema}.{quoted_table} ({quoted_columns}) "
                    f"VALUES ({values_sql}) RETURNING *"
                )
                record = await conn.fetchrow(query, *values)
            else:
                query = f"INSERT INTO {quoted_schema}.{quoted_table} DEFAULT VALUES RETURNING *"
                record = await conn.fetchrow(query)
            return dict(record) if record is not None else {}

    async def query_table(
        self,
        session_id: str,
        table: str,
        *,
        limit: int = 50,
        offset: int = 0,
        order_by: str | None = None,
    ) -> dict[str, Any]:
        table_name = _validate_identifier(table, kind="table")
        resolved_limit = max(1, min(int(limit), 200))
        resolved_offset = max(0, int(offset))

        async with self._schema_connection(session_id) as (conn, schema):
            column_meta = await self._get_table_columns(conn, schema, table_name)
            if not column_meta:
                raise ValueError(f"Table '{table_name}' not found")
            allowed_columns = self._get_allowed_columns(schema, table_name, set(column_meta.keys()))
            order_column, direction = _build_order_by(order_by, allowed_columns)

            query = (
                f"SELECT * FROM {_quote_ident(schema)}.{_quote_ident(table_name)} "
                f"ORDER BY {_quote_ident(order_column)} {direction} LIMIT $1 OFFSET $2"
            )
            rows = await conn.fetch(query, resolved_limit, resolved_offset)
            return {
                "rows": [dict(row) for row in rows],
                "limit": resolved_limit,
                "offset": resolved_offset,
                "order_by": {"column": order_column, "direction": direction},
            }

    async def delete_record(self, session_id: str, table: str, row_id: int) -> bool:
        table_name = _validate_identifier(table, kind="table")
        async with self._schema_connection(session_id) as (conn, schema):
            await self._get_table_columns(conn, schema, table_name)
            query = (
                f"DELETE FROM {_quote_ident(schema)}.{_quote_ident(table_name)} "
                f"WHERE {_quote_ident('id')} = $1 RETURNING {_quote_ident('id')}"
            )
            deleted = await conn.fetchrow(query, int(row_id))
            return deleted is not None

    async def get_table_stats(self, session_id: str, table: str) -> dict[str, Any]:
        table_name = _validate_identifier(table, kind="table")
        async with self._schema_connection(session_id) as (conn, schema):
            column_meta = await self._get_table_columns(conn, schema, table_name)
            if not column_meta:
                raise ValueError(f"Table '{table_name}' not found")

            quoted_target = f"{_quote_ident(schema)}.{_quote_ident(table_name)}"
            total = await conn.fetchval(f"SELECT COUNT(*) FROM {quoted_target}")

            numeric_stats: dict[str, dict[str, Any]] = {}
            boolean_stats: dict[str, dict[str, int]] = {}

            for column_name, meta in column_meta.items():
                udt = meta.get("udt_name", "")
                if udt in _NUMERIC_COLUMN_TYPES:
                    aggregates = await conn.fetchrow(
                        (
                            f"SELECT COALESCE(SUM({_quote_ident(column_name)}), 0) AS sum_value, "
                            f"AVG({_quote_ident(column_name)}) AS avg_value, "
                            f"MIN({_quote_ident(column_name)}) AS min_value, "
                            f"MAX({_quote_ident(column_name)}) AS max_value "
                            f"FROM {quoted_target}"
                        )
                    )
                    numeric_stats[column_name] = {
                        "sum": aggregates["sum_value"],
                        "avg": aggregates["avg_value"],
                        "min": aggregates["min_value"],
                        "max": aggregates["max_value"],
                    }
                elif udt == "bool":
                    grouped = await conn.fetch(
                        (
                            f"SELECT {_quote_ident(column_name)} AS bucket, COUNT(*) AS count "
                            f"FROM {quoted_target} GROUP BY {_quote_ident(column_name)}"
                        )
                    )
                    distribution: dict[str, int] = {}
                    for row in grouped:
                        bucket = row["bucket"]
                        key = "null" if bucket is None else str(bool(bucket)).lower()
                        distribution[key] = int(row["count"])
                    boolean_stats[column_name] = distribution

            return {
                "table": table_name,
                "count": int(total or 0),
                "numeric": numeric_stats,
                "boolean": boolean_stats,
            }


_app_data_store: AppDataStore | None = None


def get_app_data_store() -> AppDataStore:
    global _app_data_store
    if _app_data_store is None:
        settings = get_settings()
        _app_data_store = AppDataStore(
            dsn=settings.database_url,
            min_size=settings.app_data_pg_pool_min_size,
            max_size=settings.app_data_pg_pool_max_size,
            command_timeout=settings.app_data_pg_pool_command_timeout,
        )
    return _app_data_store


async def initialize_app_data_store() -> AppDataStore:
    store = get_app_data_store()
    await store.initialize_pool()
    return store


async def close_app_data_store() -> None:
    global _app_data_store
    if _app_data_store is None:
        return
    await _app_data_store.close_pool()
    _app_data_store = None


def reset_app_data_store() -> None:
    global _app_data_store
    _app_data_store = None


__all__ = [
    "TYPE_MAP",
    "AppDataStore",
    "get_app_data_store",
    "initialize_app_data_store",
    "close_app_data_store",
    "reset_app_data_store",
    "schema_name_for_session",
]
