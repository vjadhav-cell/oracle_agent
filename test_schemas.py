from __future__ import annotations

import sys

from pydantic import ValidationError

from schemas.oracle import (
    ORACLE_TOOL_SCHEMA_REGISTRY,
    OracleConnectDatabaseInput,
    OracleExecuteSQLInput,
    OracleFetchTableInput,
    OracleGetColumnDetailsInput,
    OracleGetSchemaInput,
    OracleGetTableDetailsInput,
)


results: list[bool] = []


def check(label: str, passed: bool, detail: str = ""):
    status = "PASS" if passed else "FAIL"
    print(f"  {status}  {label}")
    if detail:
        print(f"        {detail}")
    results.append(passed)


def expect_valid(label: str, factory):
    try:
        value = factory()
        check(label, True, value.to_json() if hasattr(value, "to_json") else "")
    except Exception as exc:
        check(label, False, str(exc))


def expect_invalid(label: str, factory):
    try:
        factory()
        check(label, False, "Expected validation failure")
    except ValidationError:
        check(label, True)


print("\n-- Oracle connection schema --")
expect_valid(
    "oracle+oracledb URL accepted",
    lambda: OracleConnectDatabaseInput(
        db_connection_string="oracle+oracledb://user:pass@localhost:1521/?service_name=FREEPDB1"
    ),
)
expect_invalid(
    "non-Oracle URL rejected",
    lambda: OracleConnectDatabaseInput(db_connection_string="postgres://user:pass@host/db"),
)

print("\n-- Oracle metadata schemas --")
expect_valid("table listing accepts owner", lambda: OracleGetTableDetailsInput(owner="HR"))
expect_valid(
    "column lookup requires table",
    lambda: OracleGetColumnDetailsInput(owner="HR", table_name="EMPLOYEES"),
)
expect_invalid("bad table identifier rejected", lambda: OracleGetColumnDetailsInput(table_name="EMP;DROP"))
expect_valid("schema lookup accepts limit", lambda: OracleGetSchemaInput(owner="HR", table_limit=25))

print("\n-- Oracle fetchTable schema --")
expect_valid(
    "general table fetch accepted",
    lambda: OracleFetchTableInput(
        owner="HR",
        table_name="EMPLOYEES",
        columns=["EMPLOYEE_ID", "FIRST_NAME"],
        where="DEPARTMENT_ID = :department_id",
        bind_params={"department_id": 60},
        order_by=["EMPLOYEE_ID ASC"],
        limit=10,
    ),
)
expect_invalid(
    "unsafe where rejected",
    lambda: OracleFetchTableInput(table_name="EMPLOYEES", where="1=1; DELETE FROM EMPLOYEES"),
)

print("\n-- Oracle executeSQL schema --")
expect_valid(
    "SELECT with bind params accepted",
    lambda: OracleExecuteSQLInput(
        sql_statement="SELECT * FROM EMPLOYEES WHERE DEPARTMENT_ID = :department_id",
        bind_params={"department_id": 60},
    ),
)
expect_valid(
    "WITH query accepted",
    lambda: OracleExecuteSQLInput(
        sql_statement="WITH dept AS (SELECT department_id FROM departments) SELECT * FROM dept"
    ),
)
expect_invalid(
    "INSERT rejected",
    lambda: OracleExecuteSQLInput(sql_statement="INSERT INTO EMPLOYEES VALUES (1)"),
)
expect_invalid(
    "multiple statements rejected",
    lambda: OracleExecuteSQLInput(sql_statement="SELECT * FROM EMPLOYEES; SELECT * FROM DEPARTMENTS"),
)

print("\n-- Oracle schema registry --")
for tool in [
    "oracle.testConnection",
    "oracle.getTables",
    "oracle.getColumns",
    "oracle.getSchema",
    "oracle.fetchTable",
    "oracle.executeSQL",
]:
    check(f"{tool} registered", tool in ORACLE_TOOL_SCHEMA_REGISTRY)

total = len(results)
passed = sum(results)
failed = total - passed

print(f"\nTotal: {total} | Passed: {passed} | Failed: {failed}")
sys.exit(0 if failed == 0 else 1)
