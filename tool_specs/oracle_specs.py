from __future__ import annotations

from typing import Any


OracleToolSpec = dict[str, Any]


def camel_to_kebab(name: str) -> str:
    parts: list[str] = []
    for char in name:
        if char.isupper():
            parts.append("-")
            parts.append(char.lower())
        else:
            parts.append(char)
    return "".join(parts).lstrip("-")


def oracle_http_path(tool_name: str) -> str:
    short_name = tool_name.split(".", 1)[1]
    return f"/tools/oracle/{camel_to_kebab(short_name)}"


def make_spec(
    tool: str,
    method: str,
    description: str,
    *,
    result_key: str | None = None,
    passthrough: bool = False,
    param_map: dict[str, str] | None = None,
    required: list[str] | None = None,
    inputs: dict[str, str] | None = None,
) -> OracleToolSpec:
    return {
        "tool": tool,
        "method": method,
        "description": description,
        "http_path": oracle_http_path(tool),
        "result_key": result_key,
        "passthrough": passthrough,
        "param_map": param_map or {},
        "required": required or [],
        "inputs": inputs or {},
    }


ORACLE_TOOL_SPECS: list[OracleToolSpec] = [
    make_spec(
        "oracle.testConnection",
        "test_connection",
        "Test Oracle database connection",
        result_key="result",
    ),
    make_spec(
        "oracle.getTables",
        "get_tables",
        "Get Oracle tables",
        result_key="tables",
        inputs={
            "owner": "optional schema/user name",
            "include_views": "optional boolean",
            "limit": "optional maximum tables/views to return",
        },
    ),
    make_spec(
        "oracle.getColumns",
        "get_columns",
        "Get columns for a table",
        result_key="columns",
        required=["table_name"],
        inputs={
            "table_name": "Oracle table name, e.g. EMPLOYEES or HR.EMPLOYEES",
            "owner": "optional schema/user name",
        },
    ),
    make_spec(
        "oracle.getSchema",
        "get_schema",
        "Get complete Oracle schema",
        result_key="schema",
        inputs={
            "owner": "optional schema/user name",
            "include_views": "optional boolean",
            "table_limit": "optional maximum tables/views to inspect",
        },
    ),
    make_spec(
        "oracle.fetchTable",
        "fetch_table",
        "Fetch rows from an Oracle table",
        result_key="result",
        required=["table_name"],
        inputs={
            "table_name": "Oracle table name, e.g. EMPLOYEES or HR.EMPLOYEES",
            "owner": "optional schema/user name",
            "columns": "optional list of columns to return",
            "where": "optional read-only WHERE predicate without the WHERE keyword",
            "bind_params": "optional object of bind parameters for the where predicate",
            "order_by": "optional list of columns, each can include ASC or DESC",
            "limit": "optional maximum rows to return",
            "offset": "optional rows to skip",
        },
    ),
    make_spec(
        "oracle.executeSQL",
        "execute_query",
        "Execute read-only SQL query",
        result_key="rows",
        required=["sql_statement"],
        inputs={
            "sql_statement": "SQL SELECT/WITH query",
            "bind_params": "optional object of SQL bind parameters",
            "limit": "optional maximum rows to return",
        },
    ),
    make_spec(
        "oracle.executeSQLQueryWithFilters",
        "execute_sql_query_with_filters",
        "Execute read-only SQL query with simple equality filters",
        result_key="rows",
        required=["sql_statement"],
        inputs={
            "sql_statement": "SQL SELECT/WITH query used as the base result set",
            "filters": "optional object of column-to-value equality filters",
            "bind_params": "optional object of SQL bind parameters",
            "order_by": "optional list of columns to order by",
            "limit": "optional maximum rows to return",
            "offset": "optional rows to skip",
        },
    ),
]


ORACLE_TOOL_SPEC_BY_NAME = {
    str(spec["tool"]): spec
    for spec in ORACLE_TOOL_SPECS
}


ORACLE_TOOL_SPEC_BY_METHOD = {
    str(spec["method"]): spec
    for spec in ORACLE_TOOL_SPECS
}