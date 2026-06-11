from __future__ import annotations

from typing import Dict, List, Optional


class OracleToolSpec(Dict[str, object]):
    pass


def _inputs(description_map: Dict[str, str]) -> Dict[str, str]:
    return description_map


def _path(name: str) -> str:
    _, short = name.split(".", 1)

    kebab = []

    for char in short:
        if char.isupper():
            kebab.append("-")
            kebab.append(char.lower())
        else:
            kebab.append(char)

    return f"/tools/oracle/{''.join(kebab)}"


def _spec(
    tool: str,
    method: str,
    description: str,
    *,
    result_key: Optional[str] = None,
    passthrough: bool = False,
    param_map: Optional[Dict[str, str]] = None,
    required: Optional[List[str]] = None,
    inputs: Optional[Dict[str, str]] = None,
) -> OracleToolSpec:

    return {
        "tool": tool,
        "method": method,
        "description": description,
        "http_path": _path(tool),
        "result_key": result_key,
        "passthrough": passthrough,
        "param_map": param_map or {},
        "required": required or [],
        "inputs": inputs or {},
    }


ORACLE_TOOL_SPECS: List[OracleToolSpec] = [

    _spec(
        "oracle.testConnection",
        "test_connection",
        "Test Oracle database connection",
        result_key="result",
    ),

    _spec(
        "oracle.executeSQL",
        "execute_query",
        "Execute read-only SQL query",
        result_key="rows",
        required=["sql_statement"],
        inputs={
            "sql_statement": "SQL SELECT/WITH query",
            "bind_params": "object (optional) — named bind parameters",
            "limit": "number (optional, default QUERY_LIMIT_SIZE, max 1000)",
            "timeout_ms": "number (optional, 1000-120000)"
        },
    ),

    _spec(
        "oracle.getTables",
        "get_tables",
        "Get Oracle tables",
        result_key="tables",
        inputs={
            "owner": "string (optional) — Oracle schema owner",
            "include_views": "boolean (optional, default false)",
            "limit": "number (optional, default 100, max 1000)"
        },
    ),

    _spec(
        "oracle.getColumns",
        "get_columns",
        "Get columns for a table",
        result_key="columns",
        required=["table_name"],
        inputs={
            "table_name": "Oracle table name",
            "owner": "string (optional) — Oracle schema owner"
        },
    ),

    _spec(
        "oracle.getSchema",
        "get_schema",
        "Get complete Oracle schema",
        result_key="schema",
        inputs={
            "owner": "string (optional) — Oracle schema owner",
            "include_views": "boolean (optional, default false)",
            "table_limit": "number (optional, default 100, max 500)"
        },
    ),

    _spec(
        "oracle.fetchTable",
        "fetch_table",
        "Fetch rows from any allowed Oracle table",
        result_key="data",
        required=["table_name"],
        inputs={
            "table_name": "Oracle table name",
            "owner": "string (optional) — Oracle schema owner",
            "columns": "array<string> (optional)",
            "where": "string (optional) — read-only predicate with bind placeholders",
            "bind_params": "object (optional) — named bind parameters",
            "order_by": "array<string> (optional) — columns with optional ASC/DESC",
            "limit": "number (optional, default QUERY_LIMIT_SIZE, max 1000)",
            "offset": "number (optional, default 0)"
        },
    ),
]


ORACLE_TOOL_SPEC_BY_NAME = {
    spec["tool"]: spec
    for spec in ORACLE_TOOL_SPECS
}


ORACLE_TOOL_SPEC_BY_METHOD = {
    spec["method"]: spec
    for spec in ORACLE_TOOL_SPECS
}