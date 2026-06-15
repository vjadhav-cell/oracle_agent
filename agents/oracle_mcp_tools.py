from __future__ import annotations

import json
import os
from typing import Any

import httpx
from langchain_core.tools import StructuredTool


DEFAULT_MCP_URL = os.getenv("MCP_URL", "http://127.0.0.1:8000/mcp")


class OracleMCPClientManager:
    """Create LangChain tools that call the Oracle MCP server over JSON-RPC."""

    def __init__(self, mcp_url: str | None = None):
        self.mcp_url = mcp_url or DEFAULT_MCP_URL

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
        }

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                self.mcp_url,
                headers={
                    "Accept": "application/json, text/event-stream",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()

        return self._extract_result(response.text)

    async def list_tools(self) -> list[dict[str, Any]]:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
        }

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                self.mcp_url,
                headers={
                    "Accept": "application/json, text/event-stream",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()

        result = self._decode_response(response.text).get("result", {})
        tools = result.get("tools", [])
        return tools if isinstance(tools, list) else []

    async def create_mcp_client_with_tools(self):
        tools = self._build_langchain_tools()
        tools_description = "\n".join(
            f"- {tool.name}: {tool.description}" for tool in tools
        )
        return self, tools, tools_description

    def _build_langchain_tools(self) -> list[StructuredTool]:
        async def oracle_test_connection() -> str:
            """Test the Oracle database connection."""
            return self._to_text(await self.call_tool("oracle.testConnection", {}))

        async def oracle_get_tables(include_views: bool = True, limit: int = 100) -> str:
            """List Oracle tables and optionally views."""
            return self._to_text(
                await self.call_tool(
                    "oracle.getTables",
                    {"include_views": include_views, "limit": limit},
                )
            )

        async def oracle_get_columns(table_name: str) -> str:
            """Get columns for an Oracle table or view."""
            return self._to_text(
                await self.call_tool("oracle.getColumns", {"table_name": table_name})
            )

        async def oracle_get_schema(
            include_views: bool = True,
            table_limit: int = 20,
        ) -> str:
            """Get schema details for Oracle tables and optionally views."""
            return self._to_text(
                await self.call_tool(
                    "oracle.getSchema",
                    {"include_views": include_views, "table_limit": table_limit},
                )
            )

        async def oracle_fetch_table(
            table_name: str,
            limit: int = 10,
            offset: int = 0,
            columns: list[str] | None = None,
            where: str | None = None,
            order_by: list[str] | None = None,
        ) -> str:
            """Fetch rows from an Oracle table or view."""
            args: dict[str, Any] = {
                "table_name": table_name,
                "limit": limit,
                "offset": offset,
            }
            if columns:
                args["columns"] = columns
            if where:
                args["where"] = where
            if order_by:
                args["order_by"] = order_by

            return self._to_text(await self.call_tool("oracle.fetchTable", args))

        async def oracle_execute_sql(sql_statement: str, limit: int = 50) -> str:
            """Execute a read-only Oracle SELECT or WITH SQL statement."""
            return self._to_text(
                await self.call_tool(
                    "oracle.executeSQL",
                    {"sql_statement": sql_statement, "limit": limit},
                )
            )

        async def oracle_execute_sql_query_with_filters(
            sql_statement: str,
            filters: dict[str, Any] | None = None,
            limit: int = 10,
            offset: int = 0,
            order_by: list[str] | None = None,
        ) -> str:
            """Execute read-only Oracle SQL with simple equality filters."""
            args: dict[str, Any] = {
                "sql_statement": sql_statement,
                "filters": filters or {},
                "limit": limit,
                "offset": offset,
            }
            if order_by:
                args["order_by"] = order_by

            return self._to_text(
                await self.call_tool("oracle.executeSQLQueryWithFilters", args)
            )

        return [
            StructuredTool.from_function(
                coroutine=oracle_test_connection,
                name="oracle_test_connection",
                description="Test the Oracle database connection.",
            ),
            StructuredTool.from_function(
                coroutine=oracle_get_tables,
                name="oracle_get_tables",
                description="List Oracle tables and views.",
            ),
            StructuredTool.from_function(
                coroutine=oracle_get_columns,
                name="oracle_get_columns",
                description="Get columns for a table. Requires table_name.",
            ),
            StructuredTool.from_function(
                coroutine=oracle_get_schema,
                name="oracle_get_schema",
                description="Get schema details for tables and views.",
            ),
            StructuredTool.from_function(
                coroutine=oracle_fetch_table,
                name="oracle_fetch_table",
                description="Fetch rows from a table. Requires table_name.",
            ),
            StructuredTool.from_function(
                coroutine=oracle_execute_sql,
                name="oracle_execute_sql",
                description="Run read-only Oracle SELECT/WITH SQL.",
            ),
            StructuredTool.from_function(
                coroutine=oracle_execute_sql_query_with_filters,
                name="oracle_execute_sql_query_with_filters",
                description="Run read-only Oracle SQL with equality filters.",
            ),
        ]

    @staticmethod
    def _decode_response(response_text: str) -> dict[str, Any]:
        stripped = response_text.strip()
        if stripped.startswith("{"):
            return json.loads(stripped)

        last_payload: dict[str, Any] | None = None
        for line in response_text.splitlines():
            if not line.startswith("data:"):
                continue

            data = line.removeprefix("data:").strip()
            if data and data != "[DONE]":
                last_payload = json.loads(data)

        if last_payload is None:
            raise ValueError(f"Could not parse MCP response: {response_text[:500]}")

        return last_payload

    @classmethod
    def _extract_result(cls, response_text: str) -> Any:
        payload = cls._decode_response(response_text)

        if "error" in payload:
            return {"ok": False, "error": payload["error"]}

        result = payload.get("result", {})
        if isinstance(result, dict) and "structuredContent" in result:
            return result["structuredContent"]

        content = result.get("content") if isinstance(result, dict) else None
        if isinstance(content, list):
            for item in content:
                if item.get("type") != "text":
                    continue

                text = item.get("text", "")
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    return text

        return result

    @staticmethod
    def _to_text(result: Any) -> str:
        return json.dumps(result, indent=2, default=str)
