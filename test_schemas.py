"""
test_schemas.py

Validates all Oracle adapter input schemas with
both valid and invalid inputs to confirm they work correctly.

Run: python test_schemas.py
"""

import sys
import json
from pydantic import ValidationError

# Make sure schemas folder is in path
sys.path.insert(0, ".")

from schemas.oracle import (
    OracleConnectDatabaseInput,
    OracleCommentDBConnectionInput,
    OracleGetTableDetailsInput,
    OracleGetColumnDetailsInput,
    OracleExecuteSQLInput,
    OracleExecuteSQLQueryWithFiltersInput,
    ORACLE_TOOL_SCHEMA_REGISTRY,
)

PASS = "PASS"
FAIL = "FAIL"
results = []

def check(label: str, passed: bool, detail: str = ""):
    icon = PASS if passed else FAIL
    print(f"  {icon}  {label}")
    if detail:
        print(f"        {detail}")
    results.append(passed)


# ─────────────────────────────────────────────
# 1. OracleConnectDatabaseInput
# ─────────────────────────────────────────────

print("\n── OracleConnectDatabaseInput ──")

try:
    s = OracleConnectDatabaseInput(
        db_connection_string="oracle+oracledb://company_db:Password123@localhost:1521/FREEPDB1"
    )
    check("Valid connection string accepted", True, s.to_json())
except ValidationError as e:
    check("Valid connection string accepted", False, str(e))

try:
    OracleConnectDatabaseInput(db_connection_string="mysql://user:pass@localhost/db")
    check("Invalid prefix rejected", False, "Should have raised ValidationError")
except ValidationError:
    check("Invalid prefix (mysql://) rejected", True)

try:
    OracleConnectDatabaseInput(db_connection_string="oracle://valid", unknown_field="x")
    check("Extra fields rejected", False, "Should have raised ValidationError")
except ValidationError:
    check("Extra fields rejected", True)


# ─────────────────────────────────────────────
# 2. OracleCommentDBConnectionInput
# ─────────────────────────────────────────────

print("\n── OracleCommentDBConnectionInput ──")

try:
    s = OracleCommentDBConnectionInput(
        comment_db_connection_string="oracle+oracledb://company_db:Password123@localhost:1521/FREEPDB1"
    )
    check("Valid comment DB connection string accepted", True, s.to_json())
except ValidationError as e:
    check("Valid comment DB connection string accepted", False, str(e))

try:
    OracleCommentDBConnectionInput(comment_db_connection_string="postgres://user:pass@host/db")
    check("Invalid prefix rejected", False, "Should have raised ValidationError")
except ValidationError:
    check("Invalid prefix (postgres://) rejected", True)


# ─────────────────────────────────────────────
# 3. OracleGetTableDetailsInput
# ─────────────────────────────────────────────

print("\n── OracleGetTableDetailsInput ──")

try:
    s = OracleGetTableDetailsInput()
    check("No-input schema instantiates cleanly", True, s.to_json())
except ValidationError as e:
    check("No-input schema instantiates cleanly", False, str(e))


# ─────────────────────────────────────────────
# 4. OracleGetColumnDetailsInput
# ─────────────────────────────────────────────

print("\n── OracleGetColumnDetailsInput ──")

try:
    s = OracleGetColumnDetailsInput(table_name="EMPLOYEES")
    check("Table name schema instantiates cleanly", True, s.to_json())
except ValidationError as e:
    check("Table name schema instantiates cleanly", False, str(e))


# ─────────────────────────────────────────────
# 5. OracleExecuteSQLInput
# ─────────────────────────────────────────────

print("\n── OracleExecuteSQLInput ──")

# Valid SELECT
try:
    s = OracleExecuteSQLInput(sql_statement="SELECT * FROM EMPLOYEES")
    check("Valid SELECT accepted", True, s.to_json())
except ValidationError as e:
    check("Valid SELECT accepted", False, str(e))

# Valid WITH (CTE)
try:
    s = OracleExecuteSQLInput(
        sql_statement="WITH dept AS (SELECT DEPT_ID FROM DEPARTMENTS) SELECT * FROM dept",
        timeout_ms=10000
    )
    check("Valid WITH (CTE) accepted", True, s.to_json())
except ValidationError as e:
    check("Valid WITH (CTE) accepted", False, str(e))

# Block INSERT
try:
    OracleExecuteSQLInput(sql_statement="INSERT INTO EMPLOYEES VALUES (99, 'Test')")
    check("INSERT blocked", False, "Should have raised ValidationError")
except ValidationError:
    check("INSERT blocked", True)

# Block DELETE
try:
    OracleExecuteSQLInput(sql_statement="DELETE FROM EMPLOYEES WHERE EMP_ID=1")
    check("DELETE blocked", False, "Should have raised ValidationError")
except ValidationError:
    check("DELETE blocked", True)

# Block DROP
try:
    OracleExecuteSQLInput(sql_statement="DROP TABLE EMPLOYEES")
    check("DROP blocked", False, "Should have raised ValidationError")
except ValidationError:
    check("DROP blocked", True)

# Timeout too low
try:
    OracleExecuteSQLInput(sql_statement="SELECT 1 FROM DUAL", timeout_ms=500)
    check("Timeout < 1000ms rejected", False, "Should have raised ValidationError")
except ValidationError:
    check("Timeout < 1000ms rejected", True)

# Timeout too high
try:
    OracleExecuteSQLInput(sql_statement="SELECT 1 FROM DUAL", timeout_ms=999999)
    check("Timeout > 120000ms rejected", False, "Should have raised ValidationError")
except ValidationError:
    check("Timeout > 120000ms rejected", True)

try:
    s = OracleExecuteSQLQueryWithFiltersInput(
        sql_statement="SELECT EMPLOYEE_ID, DEPARTMENT_ID FROM EMPLOYEES",
        filters={"DEPARTMENT_ID": 50},
        order_by=["EMPLOYEE_ID"],
        limit=10,
    )
    check("Filtered SQL schema accepted", True, s.to_json())
except ValidationError as e:
    check("Filtered SQL schema accepted", False, str(e))


# ─────────────────────────────────────────────
# 6. Schema Registry
# ─────────────────────────────────────────────

print("\n── ORACLE_TOOL_SCHEMA_REGISTRY ──")

expected_tools = [
    "connect_to_database",
    "create_comment_db_connection",
    "get_table_details",
    "get_column_details",
    "get_schema",
    "fetch_table",
    "execute_sql",
    "execute_sql_query_with_filters",
]

for tool in expected_tools:
    check(f"'{tool}' registered", tool in ORACLE_TOOL_SCHEMA_REGISTRY)

# Dynamic instantiation via registry
try:
    schema_cls = ORACLE_TOOL_SCHEMA_REGISTRY["execute_sql"]
    instance = schema_cls(sql_statement="SELECT * FROM DEPARTMENTS")
    check("Registry lookup + dynamic instantiation works", True, instance.to_json())
except Exception as e:
    check("Registry lookup + dynamic instantiation works", False, str(e))


# ─────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────

total  = len(results)
passed = sum(results)
failed = total - passed

print(f"\n{'='*50}")
print(f"  Total: {total}  |  Passed: {passed}  |  Failed: {failed}")
if failed == 0:
    print("All schema validations passed!")
else:
    print(f"{failed} validation(s) failed.")
print(f"{'='*50}\n")

sys.exit(0 if failed == 0 else 1)