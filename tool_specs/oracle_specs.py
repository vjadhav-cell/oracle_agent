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
            "bind_params": "optional object of SQL bind parameters",
            "limit": "optional maximum rows to return",
        },
    ),

    _spec(
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

    _spec(
        "oracle.getTables",
        "get_tables",
        "Get Oracle tables",
        result_key="tables",
    ),

    _spec(
        "oracle.getColumns",
        "get_columns",
        "Get columns for a table",
        result_key="columns",
        required=["table_name"],
        inputs={
            "table_name": "Oracle table name",
            "owner": "optional schema/user name",
        },
    ),

    _spec(
        "oracle.getSchema",
        "get_schema",
        "Get complete Oracle schema",
        result_key="schema",
        inputs={
            "owner": "optional schema/user name",
            "include_views": "optional boolean",
            "table_limit": "optional table limit",
        },
    ),

    _spec(
        "oracle.fetchTable",
        "fetch_table",
        "Fetch rows from an Oracle table",
        result_key="result",
        required=["table_name"],
        inputs={
            "table_name": "Oracle table name",
            "owner": "optional schema/user name",
            "columns": "optional list of columns",
            "where": "optional WHERE clause without the WHERE keyword",
            "bind_params": "optional object of bind parameters for where",
            "order_by": "optional list of columns to order by",
            "limit": "optional maximum rows to return",
            "offset": "optional rows to skip",
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