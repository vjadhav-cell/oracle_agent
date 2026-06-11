from __future__ import annotations

import base64
import datetime as dt
import decimal
from collections.abc import Iterable
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from schemas.oracle import (
    OracleExecuteSQLInput,
    OracleGetColumnDetailsInput,
    OracleFetchTableInput,
    OracleGetSchemaInput,
    OracleGetTableDetailsInput,
    OracleTestConnectionInput,
    validate_read_only_sql,
)
from utils.config import settings

from utils.errors import ProviderError


class OracleAdapter:
    name = "oracle"

    def __init__(self, tenant_id: str | None = None, connection_string: str | None = None):
        self.tenant_id = tenant_id
        self.connection_string = connection_string or settings.DB_CONNECTION_STRING
        self._engine: Engine | None = None
        self.default_limit = settings.QUERY_LIMIT_SIZE
        self.table_whitelist = self._parse_csv(settings.TABLE_WHITE_LIST)
        self.column_whitelist = self._parse_csv(settings.COLUMN_WHITE_LIST)

    @property
    def enabled(self) -> bool:
        return bool(self.connection_string)

    def _require_engine(self) -> Engine:
        if not self.connection_string:
            raise ProviderError("oracle", "DB_CONNECTION_STRING is not configured", status=503)
        if self._engine is None:
            try:
                self._engine = create_engine(
                    self.connection_string,
                    pool_pre_ping=True,
                    pool_recycle=settings.ORACLE_POOL_RECYCLE,
                    pool_size=settings.ORACLE_POOL_SIZE,
                    max_overflow=settings.ORACLE_MAX_OVERFLOW,
                )
            except Exception as exc:
                raise ProviderError("oracle", str(exc)) from exc
        return self._engine

    @staticmethod
    def _parse_csv(raw: str | None) -> set[str]:
        if not raw:
            return set()
        return {item.strip().upper() for item in raw.split(",") if item.strip()}

    @staticmethod
    def _split_owner_table(table_name: str, owner: str | None = None) -> tuple[str | None, str]:
        if "." in table_name:
            parsed_owner, parsed_table = table_name.split(".", 1)
            return parsed_owner.upper(), parsed_table.upper()
        return owner.upper() if owner else None, table_name.upper()

    @staticmethod
    def _serialize_value(value: Any) -> Any:
        if isinstance(value, (dt.datetime, dt.date, dt.time)):
            return value.isoformat()
        if isinstance(value, decimal.Decimal):
            return int(value) if value == value.to_integral_value() else float(value)
        if isinstance(value, bytes):
            return base64.b64encode(value).decode("ascii")
        if hasattr(value, "read"):
            data = value.read()
            if isinstance(data, bytes):
                return base64.b64encode(data).decode("ascii")
            return data
        return value

    @classmethod
    def _rows_to_dicts(cls, rows: Iterable[Any]) -> list[dict[str, Any]]:
        return [
            {
                key.lower(): cls._serialize_value(value)
                for key, value in row._mapping.items()
            }
            for row in rows
        ]

    def _table_key(self, owner: str | None, table_name: str) -> str:
        return f"{owner}.{table_name}" if owner else table_name

    def _ensure_table_allowed(self, owner: str | None, table_name: str) -> None:
        if not self.table_whitelist:
            return
        table_key = self._table_key(owner, table_name).upper()
        if table_name.upper() not in self.table_whitelist and table_key not in self.table_whitelist:
            raise ProviderError("oracle", f"Table is not allowed: {table_key}", status=403)

    def _filter_allowed_columns(
        self,
        owner: str | None,
        table_name: str,
        columns: list[str] | None,
    ) -> list[str] | None:
        if not columns or not self.column_whitelist:
            return columns

        table_key = self._table_key(owner, table_name).upper()
        allowed: list[str] = []
        for column in columns:
            column_key = f"{table_key}.{column.upper()}"
            if column.upper() in self.column_whitelist or column_key in self.column_whitelist:
                allowed.append(column)
        if not allowed:
            raise ProviderError("oracle", "Requested columns are not allowed", status=403)
        return allowed

    def _execute(self, sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        try:
            with self._require_engine().connect() as conn:
                result = conn.execute(text(sql), params or {})
                return self._rows_to_dicts(result)
        except SQLAlchemyError as exc:
            raise ProviderError("oracle", str(exc)) from exc

    async def connect_to_database(self, connection_string: str | None = None) -> dict[str, Any]:
        adapter = self if not connection_string else OracleAdapter(connection_string=connection_string)
        return await adapter.test_connection(OracleTestConnectionInput())

    async def test_connection(self, data: OracleTestConnectionInput | None = None) -> dict[str, Any]:
        rows = self._execute("SELECT 'CONNECTED' AS status FROM DUAL")
        return {"connected": True, "result": rows}

    async def execute_sql(self, sql_statement: str) -> list[dict[str, Any]]:
        return await self.execute_query(OracleExecuteSQLInput(sql_statement=sql_statement))

    async def execute_query(self, data: OracleExecuteSQLInput) -> list[dict[str, Any]]:
        sql = validate_read_only_sql(data.sql_statement)
        limit = data.limit or self.default_limit
        limited_sql = f"SELECT * FROM ({sql}) WHERE ROWNUM <= :__limit"
        params = dict(data.bind_params)
        params["__limit"] = limit
        return self._execute(limited_sql, params)

    async def get_tables(self, data: OracleGetTableDetailsInput | None = None) -> list[dict[str, Any]]:
        data = data or OracleGetTableDetailsInput()
        params: dict[str, Any] = {"limit": data.limit}

        if data.owner:
            params["owner"] = data.owner
            selects = [
                """
                SELECT owner, table_name, 'TABLE' AS object_type
                FROM all_tables
                WHERE owner = :owner
                """
            ]
            if data.include_views:
                selects.append(
                    """
                    SELECT owner, view_name AS table_name, 'VIEW' AS object_type
                    FROM all_views
                    WHERE owner = :owner
                    """
                )
            source_sql = " UNION ALL ".join(selects)
        else:
            selects = [
                """
                SELECT USER AS owner, table_name, 'TABLE' AS object_type
                FROM user_tables
                """
            ]
            if data.include_views:
                selects.append(
                    """
                    SELECT USER AS owner, view_name AS table_name, 'VIEW' AS object_type
                    FROM user_views
                    """
                )
            source_sql = " UNION ALL ".join(selects)

        sql = f"""
            SELECT *
            FROM (
                SELECT *
                FROM ({source_sql})
                ORDER BY owner, table_name
            )
            WHERE ROWNUM <= :limit
        """
        rows = self._execute(sql, params)
        if self.table_whitelist:
            rows = [
                row for row in rows
                if row["table_name"].upper() in self.table_whitelist
                or f"{row['owner'].upper()}.{row['table_name'].upper()}" in self.table_whitelist
            ]
        return rows

    async def get_columns(self, data: OracleGetColumnDetailsInput) -> list[dict[str, Any]]:
        owner, table_name = self._split_owner_table(data.table_name, data.owner)
        self._ensure_table_allowed(owner, table_name)

        if owner:
            sql = """
            SELECT
                OWNER,
                COLUMN_NAME,
                DATA_TYPE,
                DATA_LENGTH,
                DATA_PRECISION,
                DATA_SCALE,
                NULLABLE,
                COLUMN_ID
            FROM ALL_TAB_COLUMNS
            WHERE OWNER = :owner AND TABLE_NAME = :table_name
            ORDER BY COLUMN_ID
            """
            params = {"owner": owner, "table_name": table_name}
        else:
            sql = """
            SELECT
                USER AS OWNER,
                COLUMN_NAME,
                DATA_TYPE,
                DATA_LENGTH,
                DATA_PRECISION,
                DATA_SCALE,
                NULLABLE,
                COLUMN_ID
            FROM USER_TAB_COLUMNS
            WHERE TABLE_NAME = :table_name
            ORDER BY COLUMN_ID
            """
            params = {"table_name": table_name}

        rows = self._execute(sql, params)
        if self.column_whitelist:
            rows = [
                row for row in rows
                if row["column_name"].upper() in self.column_whitelist
                or f"{self._table_key(owner, table_name)}.{row['column_name']}".upper() in self.column_whitelist
            ]
        return rows

    async def get_schema(self, data: OracleGetSchemaInput | None = None) -> dict[str, Any]:
        data = data or OracleGetSchemaInput()
        tables = await self.get_tables(
            OracleGetTableDetailsInput(
                owner=data.owner,
                include_views=data.include_views,
                limit=data.table_limit,
            )
        )
        schema: dict[str, Any] = {}
        for table in tables:
            owner = table["owner"]
            table_name = table["table_name"]
            table_key = self._table_key(owner, table_name)
            schema[table_key] = {
                "owner": owner,
                "table_name": table_name,
                "object_type": table["object_type"],
                "columns": await self.get_columns(
                    OracleGetColumnDetailsInput(owner=owner, table_name=table_name)
                ),
            }
        return schema

    async def fetch_table(self, data: OracleFetchTableInput) -> dict[str, Any]:
        owner, table_name = self._split_owner_table(data.table_name, data.owner)
        self._ensure_table_allowed(owner, table_name)

        columns = self._filter_allowed_columns(owner, table_name, data.columns)
        selected_columns = ", ".join(columns) if columns else "*"
        table_ref = self._table_key(owner, table_name)
        limit = data.limit or self.default_limit

        inner_sql = f"SELECT {selected_columns} FROM {table_ref}"
        params = dict(data.bind_params)

        if data.where:
            inner_sql = f"{inner_sql} WHERE {data.where}"
        if data.order_by:
            inner_sql = f"{inner_sql} ORDER BY {', '.join(data.order_by)}"
        sql = f"""
            SELECT *
            FROM (
                SELECT inner_query.*, ROWNUM AS __rownum
                FROM ({inner_sql}) inner_query
                WHERE ROWNUM <= :__max_row
            )
            WHERE __rownum > :__offset
        """
        params["__offset"] = data.offset
        params["__max_row"] = data.offset + limit

        rows = self._execute(sql, params)
        for row in rows:
            row.pop("__rownum", None)
        return {
            "owner": owner,
            "table_name": table_name,
            "limit": limit,
            "offset": data.offset,
            "row_count": len(rows),
            "rows": rows,
        }