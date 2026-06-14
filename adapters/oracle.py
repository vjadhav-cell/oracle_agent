from __future__ import annotations

import base64
import datetime as dt
import decimal
import os
from collections.abc import Iterable
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from schemas.oracle import (
    OracleExecuteSQLInput,
    OracleGetColumnDetailsInput,
    OracleExecuteSQLQueryWithFiltersInput,
    OracleFetchTableInput,
    OracleGetSchemaInput,
    OracleGetTableDetailsInput,
    OracleTestConnectionInput,
    validate_read_only_sql,
)
from utils.errors import ProviderError


class OracleAdapter:
    name = "oracle"

    def __init__(
        self,
        tenant_id: str | None = None,
        connection_string: str | None = None,
    ):
        self.tenant_id = tenant_id
        self.connection_string = connection_string or os.getenv("DB_CONNECTION_STRING")
        self.default_limit = int(os.getenv("QUERY_LIMIT_SIZE", "50"))
        self._engine: Engine | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.connection_string)

    def _engine_or_error(self) -> Engine:
        if not self.connection_string:
            raise ProviderError("oracle", "DB_CONNECTION_STRING is not configured", status=503)

        if self._engine is None:
            self._engine = create_engine(
                self.connection_string,
                pool_pre_ping=True,
                pool_recycle=3600,
            )

        return self._engine

    @staticmethod
    def _serialize_value(value: Any) -> Any:
        if isinstance(value, (dt.date, dt.datetime, dt.time)):
            return value.isoformat()

        if isinstance(value, decimal.Decimal):
            return int(value) if value == value.to_integral_value() else float(value)

        if isinstance(value, bytes):
            return base64.b64encode(value).decode("ascii")

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

    def _run_query(
        self,
        sql: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        try:
            with self._engine_or_error().connect() as conn:
                result = conn.execute(text(sql), params or {})
                return self._rows_to_dicts(result)
        except SQLAlchemyError as exc:
            raise ProviderError("oracle", str(exc))

    @staticmethod
    def _paginated_sql(inner_sql: str) -> str:
        return f"""
            SELECT *
            FROM (
                SELECT inner_query.*, ROWNUM AS mcp_row_num
                FROM ({inner_sql}) inner_query
                WHERE ROWNUM <= :mcp_max_row
            )
            WHERE mcp_row_num > :mcp_offset
        """

    @staticmethod
    def _strip_pagination_column(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for row in rows:
            row.pop("mcp_row_num", None)

        return rows

    async def connect_to_database(
        self,
        connection_string: str | None = None,
    ) -> dict[str, Any]:
        adapter = self if not connection_string else OracleAdapter(
            tenant_id=self.tenant_id,
            connection_string=connection_string,
        )
        result = await adapter.test_connection()
        return {"ok": True, "result": result}

    async def test_connection(
        self,
        data: OracleTestConnectionInput | None = None,
    ) -> dict[str, Any]:
        rows = self._run_query("SELECT 'CONNECTED' AS status FROM DUAL")
        return {"connected": True, "result": rows}

    async def get_tables(
        self,
        data: OracleGetTableDetailsInput | None = None,
    ) -> list[dict[str, Any]]:
        data = data or OracleGetTableDetailsInput()

        table_sql = """
            SELECT table_name, 'TABLE' AS object_type
            FROM user_tables
        """

        view_sql = """
            SELECT view_name AS table_name, 'VIEW' AS object_type
            FROM user_views
        """

        source_sql = table_sql

        if data.include_views:
            source_sql = f"{table_sql} UNION ALL {view_sql}"

        sql = f"""
            SELECT *
            FROM (
                SELECT *
                FROM ({source_sql})
                ORDER BY table_name
            )
            WHERE ROWNUM <= :limit
        """

        return self._run_query(sql, {"limit": data.limit})

    async def get_columns(
        self,
        data: OracleGetColumnDetailsInput,
    ) -> list[dict[str, Any]]:
        sql = """
            SELECT
                column_name,
                data_type,
                data_length,
                data_precision,
                data_scale,
                nullable
            FROM user_tab_columns
            WHERE table_name = :table_name
            ORDER BY column_id
        """

        return self._run_query(sql, {"table_name": data.table_name.upper()})

    async def get_schema(
        self,
        data: OracleGetSchemaInput | None = None,
    ) -> dict[str, Any]:
        data = data or OracleGetSchemaInput()

        tables = await self.get_tables(
            OracleGetTableDetailsInput(
                include_views=data.include_views,
                limit=data.table_limit,
            )
        )

        schema: dict[str, Any] = {}

        for table in tables:
            table_name = table["table_name"]

            schema[table_name] = {
                "table_name": table_name,
                "object_type": table["object_type"],
                "columns": await self.get_columns(
                    OracleGetColumnDetailsInput(table_name=table_name)
                ),
            }

        return schema

    async def fetch_table(
        self,
        data: OracleFetchTableInput,
    ) -> dict[str, Any]:
        columns = ", ".join(data.columns) if data.columns else "*"
        limit = data.limit or self.default_limit

        inner_sql = f"SELECT {columns} FROM {data.table_name}"
        params = dict(data.bind_params)

        if data.where:
            inner_sql = f"{inner_sql} WHERE {data.where}"

        if data.order_by:
            inner_sql = f"{inner_sql} ORDER BY {', '.join(data.order_by)}"

        params["mcp_offset"] = data.offset
        params["mcp_max_row"] = data.offset + limit

        rows = self._strip_pagination_column(
            self._run_query(self._paginated_sql(inner_sql), params)
        )

        return {
            "table_name": data.table_name,
            "limit": limit,
            "offset": data.offset,
            "row_count": len(rows),
            "rows": rows,
        }

    async def execute_sql(
        self,
        sql_statement: str,
    ) -> list[dict[str, Any]]:
        return await self.execute_query(
            OracleExecuteSQLInput(sql_statement=sql_statement)
        )

    async def execute_query(
        self,
        data: OracleExecuteSQLInput,
    ) -> list[dict[str, Any]]:
        sql = validate_read_only_sql(data.sql_statement)
        limit = data.limit or self.default_limit

        params = dict(data.bind_params)
        params["mcp_offset"] = 0
        params["mcp_max_row"] = limit

        return self._strip_pagination_column(
            self._run_query(self._paginated_sql(sql), params)
        )

    async def execute_sql_query_with_filters(
        self,
        data: OracleExecuteSQLQueryWithFiltersInput,
    ) -> list[dict[str, Any]]:
        sql = validate_read_only_sql(data.sql_statement)

        params = dict(data.bind_params)
        where_parts: list[str] = []

        for index, (column, value) in enumerate(data.filters.items()):
            bind_name = f"mcp_filter_{index}"
            where_parts.append(f"{column} = :{bind_name}")
            params[bind_name] = value

        filtered_sql = f"SELECT * FROM ({sql}) filtered_query"

        if where_parts:
            filtered_sql = f"{filtered_sql} WHERE {' AND '.join(where_parts)}"

        if data.order_by:
            filtered_sql = f"{filtered_sql} ORDER BY {', '.join(data.order_by)}"

        limit = data.limit or self.default_limit

        params["mcp_offset"] = data.offset
        params["mcp_max_row"] = data.offset + limit

        return self._strip_pagination_column(
            self._run_query(self._paginated_sql(filtered_sql), params)
        )

    async def execute_query_with_filters(
        self,
        data: OracleExecuteSQLQueryWithFiltersInput,
    ) -> list[dict[str, Any]]:
        return await self.execute_sql_query_with_filters(data)