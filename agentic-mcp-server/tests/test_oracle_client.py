import datetime as dt
import decimal
from typing import Any

import pytest

from agentic_oracle_mcp.config import OracleSettings
from agentic_oracle_mcp.oracle_client import OracleClient, OracleToolError


class FakeCursor:
    def __init__(
        self,
        *,
        description: list[tuple[str]] | None = None,
        rows: list[tuple[Any, ...]] | None = None,
        rowcount: int = 0,
    ) -> None:
        self.description = description
        self.rows = rows or []
        self.rowcount = rowcount
        self.executed_sql: str | None = None
        self.executed_parameters: dict[str, Any] | None = None
        self.closed = False

    def execute(self, sql: str, parameters: dict[str, Any]) -> None:
        self.executed_sql = sql
        self.executed_parameters = parameters

    def fetchmany(self, size: int) -> list[tuple[Any, ...]]:
        return self.rows[:size]

    def close(self) -> None:
        self.closed = True


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self._cursor = cursor
        self.closed = False
        self.committed = False
        self.rolled_back = False
        self.call_timeout: int | None = None

    def cursor(self) -> FakeCursor:
        return self._cursor

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    def close(self) -> None:
        self.closed = True


def make_settings(**overrides: Any) -> OracleSettings:
    values = {
        "username": "app",
        "password": "secret",
        "dsn": "db",
        "default_fetch_limit": 100,
    }
    values.update(overrides)
    return OracleSettings(**values)


def test_query_returns_json_safe_rows_and_truncation_flag() -> None:
    cursor = FakeCursor(
        description=[("ID",), ("CREATED_AT",), ("AMOUNT",), ("PAYLOAD",)],
        rows=[
            (
                1,
                dt.datetime(2026, 6, 11, 16, 30),
                decimal.Decimal("42.50"),
                b"abc",
            ),
            (2, dt.datetime(2026, 6, 11, 16, 31), decimal.Decimal("7"), b"x"),
        ],
    )
    connection = FakeConnection(cursor)
    client = OracleClient(make_settings(), connection_factory=lambda: connection)

    result = client.query("select * from invoices", fetch_limit=1)

    assert result == {
        "columns": ["ID", "CREATED_AT", "AMOUNT", "PAYLOAD"],
        "rows": [
            {
                "ID": 1,
                "CREATED_AT": "2026-06-11T16:30:00",
                "AMOUNT": 42.5,
                "PAYLOAD": "616263",
            }
        ],
        "row_count": 1,
        "truncated": True,
    }
    assert cursor.executed_sql == "select * from invoices"
    assert cursor.executed_parameters == {}
    assert cursor.closed is True
    assert connection.closed is True
    assert connection.call_timeout == 30_000


def test_query_rejects_non_read_only_sql() -> None:
    client = OracleClient(make_settings(), connection_factory=lambda: None)

    with pytest.raises(OracleToolError, match="Only SELECT or WITH"):
        client.query("delete from invoices")


def test_execute_sql_requires_allow_dml_for_mutating_statements() -> None:
    client = OracleClient(make_settings(allow_dml=False), connection_factory=lambda: None)

    with pytest.raises(OracleToolError, match="ORACLE_ALLOW_DML"):
        client.execute_sql("update invoices set amount = 1", read_only=False)


def test_execute_sql_rolls_back_uncommitted_dml() -> None:
    cursor = FakeCursor(description=None, rowcount=3)
    connection = FakeConnection(cursor)
    client = OracleClient(
        make_settings(allow_dml=True),
        connection_factory=lambda: connection,
    )

    result = client.execute_sql(
        "update invoices set amount = :amount",
        {"amount": 1},
        read_only=False,
        commit=False,
    )

    assert result["row_count"] == 3
    assert result["committed"] is False
    assert connection.rolled_back is True
    assert connection.committed is False


def test_sample_table_validates_identifiers() -> None:
    client = OracleClient(make_settings(), connection_factory=lambda: None)

    with pytest.raises(OracleToolError, match="table_name"):
        client.sample_table("invoice; drop table users")


def test_describe_table_uses_metadata_view_with_binds() -> None:
    cursor = FakeCursor(description=[("OWNER",), ("TABLE_NAME",)], rows=[("APP", "INVOICES")])
    connection = FakeConnection(cursor)
    client = OracleClient(make_settings(), connection_factory=lambda: connection)

    result = client.describe_table("invoices", owner="app")

    assert result["rows"] == [{"OWNER": "APP", "TABLE_NAME": "INVOICES"}]
    assert "all_tab_columns" in cursor.executed_sql
    assert cursor.executed_parameters == {"table_name": "INVOICES", "owner": "APP"}
