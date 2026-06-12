from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


ORACLE_CONNECTION_PREFIXES = ("oracle+oracledb://", "oracle://")
IDENTIFIER_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_$#]*$")
QUALIFIED_IDENTIFIER_RE = re.compile(
    r"^[A-Za-z][A-Za-z0-9_$#]*(\.[A-Za-z][A-Za-z0-9_$#]*)?$"
)
SAFE_ORDER_BY_RE = re.compile(
    r"^[A-Za-z][A-Za-z0-9_$#]*(\s+(ASC|DESC))?$",
    re.IGNORECASE,
)
FORBIDDEN_SQL_RE = re.compile(
    r"\b(ALTER|BEGIN|CALL|COMMIT|CREATE|DELETE|DROP|EXEC|EXECUTE|GRANT|INSERT|"
    r"MERGE|REVOKE|ROLLBACK|TRUNCATE|UPDATE|UPSERT)\b",
    re.IGNORECASE,
)


class AdapterInputSchema(BaseModel):
    """Small local base class used by Oracle tool inputs."""

    model_config = ConfigDict(extra="forbid")

    def to_json(self) -> str:
        return self.model_dump_json()

    @classmethod
    def parse_or_error(cls, data: dict[str, Any], provider: str = "oracle"):
        return cls.model_validate(data)


def validate_connection_string(value: str) -> str:
    cleaned = value.strip()
    if not cleaned.startswith(ORACLE_CONNECTION_PREFIXES):
        raise ValueError(
            "Oracle connection string must start with oracle+oracledb:// or oracle://"
        )
    return cleaned


def validate_identifier(value: str, field_name: str = "identifier", *, allow_qualified: bool = False) -> str:
    """Only allow Oracle identifiers, not SQL fragments."""
    cleaned = value.strip()
    pattern = QUALIFIED_IDENTIFIER_RE if allow_qualified else IDENTIFIER_RE
    if not pattern.match(cleaned):
        raise ValueError(f"{field_name} must be a simple Oracle identifier")
    return cleaned.upper()


def validate_read_only_sql(sql_statement: str) -> str:
    """Allow SELECT/WITH queries and reject common write/DDL statements."""
    sql = sql_statement.strip()
    if not sql:
        raise ValueError("SQL statement cannot be empty")
    if ";" in sql.rstrip(";"):
        raise ValueError("Multiple SQL statements are not allowed")

    normalized = sql.rstrip(";").lstrip()
    upper_sql = normalized.upper()
    if not (upper_sql.startswith("SELECT ") or upper_sql.startswith("WITH ")):
        raise ValueError("Only read-only SELECT or WITH queries are allowed")

    if FORBIDDEN_SQL_RE.search(normalized):
        raise ValueError("Only read-only SQL is allowed")

    return normalized


class OracleTestConnectionInput(AdapterInputSchema):
    """No parameters required."""


class OracleGetTableDetailsInput(AdapterInputSchema):
    owner: str | None = Field(default=None, description="Schema/user name")
    include_views: bool = Field(default=False, description="Include views with tables")
    limit: int = Field(default=100, ge=1, le=1000)

    @field_validator("owner")
    @classmethod
    def validate_owner(cls, value: str | None) -> str | None:
        return validate_identifier(value, "owner") if value else value


class OracleGetColumnDetailsInput(AdapterInputSchema):
    table_name: str = Field(..., min_length=1)
    owner: str | None = Field(default=None, description="Schema/user name")

    @field_validator("table_name")
    @classmethod
    def validate_table_name(cls, value: str) -> str:
        return validate_identifier(value, "table_name", allow_qualified=True)

    @field_validator("owner")
    @classmethod
    def validate_owner(cls, value: str | None) -> str | None:
        return validate_identifier(value, "owner") if value else value


class OracleGetSchemaInput(AdapterInputSchema):
    owner: str | None = Field(default=None, description="Schema/user name")
    include_views: bool = False
    table_limit: int = Field(default=100, ge=1, le=1000)

    @field_validator("owner")
    @classmethod
    def validate_owner(cls, value: str | None) -> str | None:
        return validate_identifier(value, "owner") if value else value


class OracleFetchTableInput(AdapterInputSchema):
    table_name: str = Field(..., min_length=1)
    owner: str | None = None
    columns: list[str] | None = None
    where: str | None = Field(default=None, description="Optional read-only WHERE clause")
    bind_params: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    order_by: list[str] | None = None
    limit: int | None = Field(default=None, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)

    @field_validator("table_name")
    @classmethod
    def validate_table_name(cls, value: str) -> str:
        return validate_identifier(value, "table_name", allow_qualified=True)

    @field_validator("owner")
    @classmethod
    def validate_owner(cls, value: str | None) -> str | None:
        return validate_identifier(value, "owner") if value else value

    @field_validator("columns")
    @classmethod
    def validate_columns(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        if not value:
            raise ValueError("columns cannot be empty")
        return [validate_identifier(item, "column") for item in value]

    @field_validator("order_by")
    @classmethod
    def validate_order_by(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        cleaned = []
        for item in value:
            candidate = item.strip()
            if not SAFE_ORDER_BY_RE.match(candidate):
                raise ValueError(f"Invalid order_by expression: {item}")
            cleaned.append(candidate.upper())
        return cleaned

    @field_validator("where")
    @classmethod
    def validate_where(cls, value: str | None) -> str | None:
        if not value:
            return None
        cleaned = value.strip()
        if ";" in cleaned or FORBIDDEN_SQL_RE.search(cleaned):
            raise ValueError("where must be a single read-only predicate")
        return cleaned


class OracleExecuteSQLInput(AdapterInputSchema):
    sql_statement: str = Field(..., min_length=1)
    bind_params: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    limit: int | None = Field(default=None, ge=1, le=1000)
    timeout_ms: int = Field(default=30000, ge=1000, le=120000)

    @field_validator("sql_statement")
    @classmethod
    def validate_sql(cls, value: str) -> str:
        return validate_read_only_sql(value)


class OracleExecuteSQLQueryWithFiltersInput(OracleExecuteSQLInput):
    filters: dict[str, str | int | float | bool | None] = Field(
        default_factory=dict,
        description="Simple equality filters, for example {'department_id': 50}",
    )
    order_by: list[str] | None = None
    offset: int = Field(default=0, ge=0)

    @field_validator("filters")
    @classmethod
    def validate_filter_names(cls, value: dict[str, Any]) -> dict[str, Any]:
        for key in value:
            validate_identifier(key, "filter column")
        return {key.upper(): filter_value for key, filter_value in value.items()}

    @field_validator("order_by")
    @classmethod
    def validate_order_by(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        cleaned = []
        for item in value:
            candidate = item.strip()
            if not SAFE_ORDER_BY_RE.match(candidate):
                raise ValueError(f"Invalid order_by expression: {item}")
            cleaned.append(candidate.upper())
        return cleaned


class OracleConnectDatabaseInput(AdapterInputSchema):
    db_connection_string: str = Field(..., description="Oracle connection string")

    @field_validator("db_connection_string")
    @classmethod
    def validate_connection_string(cls, value: str) -> str:
        return validate_connection_string(value)


class OracleCommentDBConnectionInput(AdapterInputSchema):
    comment_db_connection_string: str = Field(..., description="Oracle metadata connection string")

    @field_validator("comment_db_connection_string")
    @classmethod
    def validate_connection_string(cls, value: str) -> str:
        return validate_connection_string(value)


class OracleToolRequest(AdapterInputSchema):
    action: Literal[
        "testConnection",
        "getTables",
        "getColumns",
        "getSchema",
        "fetchTable",
        "executeSQL",
        "executeSQLQueryWithFilters",
    ]
    arguments: dict[str, Any] = Field(default_factory=dict)


ORACLE_TOOL_SCHEMA_REGISTRY = {
    "oracle.testConnection": OracleTestConnectionInput,
    "oracle.getTables": OracleGetTableDetailsInput,
    "oracle.getColumns": OracleGetColumnDetailsInput,
    "oracle.getSchema": OracleGetSchemaInput,
    "oracle.fetchTable": OracleFetchTableInput,
    "oracle.executeSQL": OracleExecuteSQLInput,
    "oracle.executeSQLQueryWithFilters": OracleExecuteSQLQueryWithFiltersInput,
    "connect_to_database": OracleConnectDatabaseInput,
    "create_comment_db_connection": OracleCommentDBConnectionInput,
    "get_table_details": OracleGetTableDetailsInput,
    "get_column_details": OracleGetColumnDetailsInput,
    "get_schema": OracleGetSchemaInput,
    "fetch_table": OracleFetchTableInput,
    "execute_sql": OracleExecuteSQLInput,
    "execute_sql_query_with_filters": OracleExecuteSQLQueryWithFiltersInput,
}