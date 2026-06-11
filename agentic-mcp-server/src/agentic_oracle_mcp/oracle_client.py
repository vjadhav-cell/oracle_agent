"""Oracle database access used by MCP tools."""

from __future__ import annotations

import datetime as dt
import decimal
import re
from contextlib import contextmanager
from typing import Any, Callable, Iterator, Mapping

from .config import OracleSettings


READ_ONLY_PREFIXES = {"select", "with"}
IDENTIFIER_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_$#]*$")


class OracleToolError(RuntimeError):
    """Raised when an MCP tool cannot complete safely."""


ConnectionFactory = Callable[[], Any]


class OracleClient:
    """Small Oracle helper with lazy connection-pool initialization."""

    def __init__(
        self,
        settings: OracleSettings | None = None,
        *,
        connection_factory: ConnectionFactory | None = None,
    ) -> None:
        self.settings = settings or OracleSettings.from_env()
        self._connection_factory = connection_factory
        self._pool: Any | None = None
        self._driver: Any | None = None
        self._thick_mode_initialized = False

    def test_connection(self) -> dict[str, Any]:
        sql = (
            "select sys_context('USERENV', 'CURRENT_SCHEMA') as current_schema, "
            "sys_context('USERENV', 'DB_NAME') as database_name from dual"
        )
        result = self.query(sql, fetch_limit=1)
        row = result["rows"][0] if result["rows"] else {}
        return {
            "ok": True,
            "current_schema": row.get("CURRENT_SCHEMA"),
            "database_name": row.get("DATABASE_NAME"),
        }

    def query(
        self,
        sql: str,
        parameters: Mapping[str, Any] | None = None,
        *,
        fetch_limit: int | None = None,
    ) -> dict[str, Any]:
        return self.execute_sql(
            sql,
            parameters,
            fetch_limit=fetch_limit,
            read_only=True,
            commit=False,
        )

    def execute_sql(
        self,
        sql: str,
        parameters: Mapping[str, Any] | None = None,
        *,
        fetch_limit: int | None = None,
        read_only: bool = True,
        commit: bool = False,
    ) -> dict[str, Any]:
        statement = _normalize_sql(sql)
        if read_only and not _is_read_only_statement(statement):
            raise OracleToolError("Only SELECT or WITH queries are allowed by this tool")

        if not read_only and not self.settings.allow_dml:
            raise OracleToolError("Set ORACLE_ALLOW_DML=true to enable non-read-only SQL")

        limit = fetch_limit or self.settings.default_fetch_limit
        if limit < 1:
            raise OracleToolError("fetch_limit must be greater than 0")

        bind_parameters = dict(parameters or {})
        with self.connection() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute(statement, bind_parameters)
                if cursor.description:
                    rows = cursor.fetchmany(limit + 1)
                    truncated = len(rows) > limit
                    if truncated:
                        rows = rows[:limit]
                    columns = [description[0] for description in cursor.description]
                    return {
                        "columns": columns,
                        "rows": [_row_to_dict(columns, row) for row in rows],
                        "row_count": len(rows),
                        "truncated": truncated,
                    }

                rowcount = cursor.rowcount if cursor.rowcount is not None else 0
                if commit:
                    connection.commit()
                else:
                    connection.rollback()
                return {
                    "columns": [],
                    "rows": [],
                    "row_count": rowcount,
                    "committed": commit,
                    "truncated": False,
                }
            finally:
                cursor.close()

    def list_tables(
        self,
        *,
        owner: str | None = None,
        name_like: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        query_limit = limit or self.settings.default_fetch_limit
        sql = """
            select owner, table_name, tablespace_name, num_rows
            from (
                select owner, table_name, tablespace_name, num_rows
                from all_tables
                where (:owner is null or owner = upper(:owner))
                  and (:name_like is null or table_name like upper(:name_like))
                order by owner, table_name
            )
            where rownum <= :limit
        """
        return self.query(
            sql,
            {"owner": owner, "name_like": name_like, "limit": query_limit},
            fetch_limit=query_limit,
        )

    def describe_table(self, table_name: str, *, owner: str | None = None) -> dict[str, Any]:
        table = _validated_identifier(table_name, "table_name")
        owner_filter = _validated_identifier(owner, "owner") if owner else None
        sql = """
            select owner,
                   table_name,
                   column_name,
                   data_type,
                   data_length,
                   data_precision,
                   data_scale,
                   nullable,
                   column_id
            from all_tab_columns
            where table_name = upper(:table_name)
              and (:owner is null or owner = upper(:owner))
            order by owner, table_name, column_id
        """
        return self.query(sql, {"table_name": table, "owner": owner_filter})

    def sample_table(
        self,
        table_name: str,
        *,
        owner: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        table = _validated_identifier(table_name, "table_name")
        owner_prefix = ""
        if owner:
            owner_prefix = f"{_validated_identifier(owner, 'owner')}."

        sample_limit = limit or min(self.settings.default_fetch_limit, 10)
        sql = f"select * from {owner_prefix}{table} where rownum <= :limit"
        return self.query(sql, {"limit": sample_limit}, fetch_limit=sample_limit)

    @contextmanager
    def connection(self) -> Iterator[Any]:
        if self._connection_factory is not None:
            connection = self._connection_factory()
            _apply_call_timeout(connection, self.settings.call_timeout_ms)
            try:
                yield connection
            finally:
                _close_quietly(connection)
            return

        pool = self._get_pool()
        connection = pool.acquire()
        _apply_call_timeout(connection, self.settings.call_timeout_ms)
        try:
            yield connection
        finally:
            _close_quietly(connection)

    def _get_pool(self) -> Any:
        if self._pool is None:
            driver = self._get_driver()
            kwargs = self.settings.connect_kwargs()
            self._pool = driver.create_pool(
                **kwargs,
                min=self.settings.pool_min,
                max=self.settings.pool_max,
                increment=self.settings.pool_increment,
            )
        return self._pool

    def _get_driver(self) -> Any:
        if self._driver is not None:
            return self._driver

        try:
            import oracledb  # type: ignore[import-not-found]
        except ImportError as exc:
            raise OracleToolError(
                "The python-oracledb package is not installed. Install this project first."
            ) from exc

        if self.settings.thick_mode and not self._thick_mode_initialized:
            init_kwargs: dict[str, str] = {}
            if self.settings.client_lib_dir:
                init_kwargs["lib_dir"] = self.settings.client_lib_dir
            oracledb.init_oracle_client(**init_kwargs)
            self._thick_mode_initialized = True

        self._driver = oracledb
        return self._driver


def _normalize_sql(sql: str) -> str:
    statement = sql.strip()
    if statement.endswith(";"):
        statement = statement[:-1].strip()
    if not statement:
        raise OracleToolError("SQL must not be empty")
    if ";" in statement:
        raise OracleToolError("Only one SQL statement can be executed at a time")
    return statement


def _is_read_only_statement(sql: str) -> bool:
    first_word = sql.lstrip().split(None, 1)[0].lower()
    return first_word in READ_ONLY_PREFIXES


def _validated_identifier(identifier: str | None, field_name: str) -> str:
    if not identifier or not IDENTIFIER_RE.match(identifier):
        raise OracleToolError(
            f"{field_name} must be a simple Oracle identifier using letters, numbers, _, $, or #"
        )
    return identifier.upper()


def _row_to_dict(columns: list[str], row: Any) -> dict[str, Any]:
    return {
        column: _json_safe(value)
        for column, value in zip(columns, row, strict=False)
    }


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, bytes):
        return value.hex()
    if hasattr(value, "read"):
        return _json_safe(value.read())
    return str(value)


def _apply_call_timeout(connection: Any, timeout_ms: int) -> None:
    try:
        connection.call_timeout = timeout_ms
    except AttributeError:
        return


def _close_quietly(resource: Any) -> None:
    close = getattr(resource, "close", None)
    if close is not None:
        close()
