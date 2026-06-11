from __future__ import annotations

import re
from typing import Literal

from pydantic import Field, field_validator

from schemas.base import AdapterInputSchema


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


def validate_connection_string(value: str) -> str:
    cleaned = value.strip()
    if not cleaned.startswith(ORACLE_CONNECTION_PREFIXES):
        raise ValueError(
            "Oracle connection string must start with oracle+oracledb:// or oracle://"
        )
    return cleaned


def validate_identifier(value: str, *, allow_qualified: bool = False) -> str:
    cleaned = value.strip()
    pattern = QUALIFIED_IDENTIFIER_RE if allow_qualified else IDENTIFIER_RE
    if not pattern.match(cleaned):
        raise ValueError(f"Invalid Oracle identifier: {value}")
    return cleaned.upper()


def validate_read_only_sql(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("SQL statement cannot be empty")
    if ";" in cleaned.rstrip(";"):
        raise ValueError("Multiple SQL statements are not allowed")

    normalized = cleaned.rstrip(";").lstrip()
    upper = normalized.upper()
    if not (upper.startswith("SELECT ") or upper.startswith("WITH ")):
        raise ValueError("Only read-only SELECT or WITH queries are allowed")
    if FORBIDDEN_SQL_RE.search(normalized):
        raise ValueError("Only read-only SQL is allowed")
    return normalized


class OracleConnectDatabaseInput(AdapterInputSchema):
    db_connection_string: str = Field(..., description="Oracle SQLAlchemy URL")

    @field_validator("db_connection_string")
    @classmethod
    def validate_db_connection_string(cls, value: str) -> str:
        return validate_connection_string(value)


class OracleCommentDBConnectionInput(AdapterInputSchema):
    comment_db_connection_string: str = Field(..., description="Oracle metadata SQLAlchemy URL")

    @field_validator("comment_db_connection_string")
    @classmethod
    def validate_comment_db_connection_string(cls, value: str) -> str:
        return validate_connection_string(value)


class OracleTestConnectionInput(AdapterInputSchema):
    pass


class OracleGetTableDetailsInput(AdapterInputSchema):
    owner: str | None = Field(default=None, description="Optional schema/owner name")
    include_views: bool = Field(default=False, description="Include views with tables")
    limit: int = Field(default=100, ge=1, le=1000, description="Maximum objects to return")

    @field_validator("owner")
    @classmethod
    def validate_owner(cls, value: str | None) -> str | None:
        return validate_identifier(value) if value else None


class OracleGetColumnDetailsInput(AdapterInputSchema):
    table_name: str = Field(..., description="Oracle table name")
    owner: str | None = Field(default=None, description="Optional schema/owner name")

    @field_validator("table_name")
    @classmethod
    def validate_table_name(cls, value: str) -> str:
        return validate_identifier(value, allow_qualified=True)

    @field_validator("owner")
    @classmethod
    def validate_owner(cls, value: str | None) -> str | None:
        return validate_identifier(value) if value else None


class OracleGetSchemaInput(AdapterInputSchema):
    owner: str | None = Field(default=None, description="Optional schema/owner name")
    include_views: bool = Field(default=False, description="Include views with tables")
    table_limit: int = Field(default=100, ge=1, le=500, description="Maximum tables/views")

    @field_validator("owner")
    @classmethod
    def validate_owner(cls, value: str | None) -> str | None:
        return validate_identifier(value) if value else None


class OracleFetchTableInput(AdapterInputSchema):
    table_name: str = Field(..., description="Oracle table name")
    owner: str | None = Field(default=None, description="Optional schema/owner name")
    columns: list[str] | None = Field(default=None, description="Columns to return")
    where: str | None = Field(default=None, description="Optional read-only WHERE clause")
    bind_params: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    order_by: list[str] | None = Field(default=None, description="Columns with optional ASC/DESC")
    limit: int | None = Field(default=None, ge=1, le=1000, description="Maximum rows")
    offset: int = Field(default=0, ge=0, description="Rows to skip")

    @field_validator("table_name")
    @classmethod
    def validate_table_name(cls, value: str) -> str:
        return validate_identifier(value, allow_qualified=True)

    @field_validator("owner")
    @classmethod
    def validate_owner(cls, value: str | None) -> str | None:
        return validate_identifier(value) if value else None

    @field_validator("columns")
    @classmethod
    def validate_columns(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        if not value:
            raise ValueError("columns cannot be empty")
        return [validate_identifier(column) for column in value]

    @field_validator("order_by")
    @classmethod
    def validate_order_by(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
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
    sql_statement: str = Field(..., min_length=1, description="Read-only Oracle SELECT/WITH SQL")
    bind_params: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    limit: int | None = Field(default=None, ge=1, le=1000, description="Maximum rows")
    timeout_ms: int = Field(default=30000, ge=1000, le=120000)

    @field_validator("sql_statement")
    @classmethod
    def validate_sql(cls, value: str) -> str:
        return validate_read_only_sql(value)


class OracleToolRequest(AdapterInputSchema):
    action: Literal[
        "testConnection",
        "getTables",
        "getColumns",
        "getSchema",
        "fetchTable",
        "executeSQL",
    ]
    arguments: dict = Field(default_factory=dict)


ORACLE_TOOL_SCHEMA_REGISTRY = {
    "oracle.testConnection": OracleTestConnectionInput,
    "oracle.getTables": OracleGetTableDetailsInput,
    "oracle.getColumns": OracleGetColumnDetailsInput,
    "oracle.getSchema": OracleGetSchemaInput,
    "oracle.fetchTable": OracleFetchTableInput,
    "oracle.executeSQL": OracleExecuteSQLInput,
    "connect_to_database": OracleConnectDatabaseInput,
    "create_comment_db_connection": OracleCommentDBConnectionInput,
}