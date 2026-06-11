"""MCP server exposing Oracle database tools."""

from __future__ import annotations

from typing import Any, Mapping

from mcp.server.fastmcp import FastMCP

from .oracle_client import OracleClient


mcp = FastMCP("agentic-oracle-mcp")
_client = OracleClient()


@mcp.tool()
def oracle_test_connection() -> dict[str, Any]:
    """Verify the Oracle connection and return basic database context."""
    return _client.test_connection()


@mcp.tool()
def oracle_query(
    sql: str,
    parameters: Mapping[str, Any] | None = None,
    fetch_limit: int | None = None,
) -> dict[str, Any]:
    """Run a read-only Oracle SELECT/WITH query and return JSON-safe rows."""
    return _client.query(sql, parameters, fetch_limit=fetch_limit)


@mcp.tool()
def oracle_execute_sql(
    sql: str,
    parameters: Mapping[str, Any] | None = None,
    fetch_limit: int | None = None,
    commit: bool = False,
) -> dict[str, Any]:
    """Run SQL, requiring ORACLE_ALLOW_DML=true for non-read-only statements."""
    return _client.execute_sql(
        sql,
        parameters,
        fetch_limit=fetch_limit,
        read_only=False,
        commit=commit,
    )


@mcp.tool()
def oracle_list_tables(
    owner: str | None = None,
    name_like: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """List visible Oracle tables, optionally filtered by owner or LIKE pattern."""
    return _client.list_tables(owner=owner, name_like=name_like, limit=limit)


@mcp.tool()
def oracle_describe_table(table_name: str, owner: str | None = None) -> dict[str, Any]:
    """Return column metadata for a visible Oracle table."""
    return _client.describe_table(table_name, owner=owner)


@mcp.tool()
def oracle_sample_table(
    table_name: str,
    owner: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Fetch sample rows from a table using a validated table identifier."""
    return _client.sample_table(table_name, owner=owner, limit=limit)


def main() -> None:
    """Run the MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
