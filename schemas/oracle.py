from __future__ import annotations

import re
from typing import Any

from pydantic import Field, field_validator, model_validator
from schemas.base import AdapterInputSchema


_READ_ONLY_PREFIXES = ("SELECT", "WITH")
_FORBIDDEN_SQL = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|MERGE|CREATE|GRANT|REVOKE|COMMIT|ROLLBACK)\b",
    re.IGNORECASE,
)
_COMMENT = re.compile(r"(--|/\*)")


def validate_read_only_sql(value: str) -> str:
    sql = value.strip().rstrip(";").strip()
    normalized = re.sub(r"\s+", " ", sql).upper()

    if not normalized.startswith(_READ_ONLY_PREFIXES):
        raise ValueError("Only SELECT and WITH queries are allowed")

    if _FORBIDDEN_SQL.search(normalized):
        raise ValueError("Only read-only SQL statements are allowed")

    if _COMMENT.search(sql):
        raise ValueError("SQL comments are not allowed")

    return sql


def _validate_identifier(value: str, label: str) -> str:
    value = value.strip()

    if not value:
        raise ValueError(f"{label} cannot be empty")

    # Allow simple Oracle identifiers, quoted identifiers, and dotted table refs.
    parts = value.split(".")
    identifier = r'(?:[A-Za-z][A-Za-z0-9_$#]*|"[^"]+")'

    if not all(re.fullmatch(identifier, part.strip()) for part in parts):
        raise ValueError(f"Invalid Oracle {label}")

    return value


def _validate_order_expression(value: str) -> str:
    value = value.strip()
    match = re.fullmatch(
        r'((?:[A-Za-z][A-Za-z0-9_$#]*|"[^"]+")(?:\.(?:[A-Za-z][A-Za-z0-9_$#]*|"[^"]+"))*)(?:\s+(ASC|DESC))?',
        value,
        re.IGNORECASE,
    )

    if not match:
        raise ValueError("Invalid Oracle order_by expression")

    return value


class OracleExecuteSQLInput(AdapterInputSchema):
    """Execute a read-only SQL query."""

    sql_statement: str = Field(
        ...,
        min_length=1,
        description="Oracle SELECT or WITH query",
    )
    bind_params: dict[str, Any] = Field(
        default_factory=dict,
        description="Named bind parameters for the query",
    )
    limit: int | None = Field(
        default=None,
        ge=1,
        le=10000,
        description="Maximum rows to return",
    )
    timeout_ms: int = Field(
        default=30000,
        ge=1000,
        le=120000,
        description="Query timeout in milliseconds",
    )

    @field_validator("sql_statement")
    @classmethod
    def validate_sql(cls, value: str) -> str:
        return validate_read_only_sql(value)


class OracleGetTableDetailsInput(AdapterInputSchema):
    """Input for get_tables()."""

    include_views: bool = Field(
        default=True,
        description="Include views alongside tables",
    )
    limit: int = Field(
        default=100,
        ge=1,
        le=10000,
        description="Maximum tables/views to return",
    )


class OracleGetColumnDetailsInput(AdapterInputSchema):
    """Input for get_columns()."""

    table_name: str = Field(
        ...,
        min_length=1,
        description="Oracle table or view name",
    )

    @field_validator("table_name")
    @classmethod
    def validate_table_name(cls, value: str) -> str:
        return _validate_identifier(value, "table name")


class OracleGetSchemaInput(AdapterInputSchema):
    """Input for get_schema()."""

    include_views: bool = Field(
        default=True,
        description="Include views alongside tables",
    )
    table_limit: int = Field(
        default=100,
        ge=1,
        le=10000,
        description="Maximum tables/views to include",
    )


class OracleFetchTableInput(AdapterInputSchema):
    """Input for fetch_table()."""

    table_name: str = Field(
        ...,
        min_length=1,
        description="Oracle table or view name",
    )
    columns: list[str] = Field(
        default_factory=list,
        description="Columns to select. Defaults to all columns.",
    )
    where: str | None = Field(
        default=None,
        description="Optional read-only WHERE clause without the WHERE keyword",
    )
    order_by: list[str] = Field(
        default_factory=list,
        description="Optional ORDER BY expressions",
    )
    limit: int | None = Field(
        default=None,
        ge=1,
        le=10000,
        description="Maximum rows to return",
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Rows to skip",
    )
    bind_params: dict[str, Any] = Field(
        default_factory=dict,
        description="Named bind parameters for WHERE clauses",
    )

    @field_validator("table_name")
    @classmethod
    def validate_table_name(cls, value: str) -> str:
        return _validate_identifier(value, "table name")

    @field_validator("columns")
    @classmethod
    def validate_columns(cls, value: list[str]) -> list[str]:
        return [_validate_identifier(column, "column name") for column in value]

    @field_validator("order_by")
    @classmethod
    def validate_order_by(cls, value: list[str]) -> list[str]:
        return [_validate_order_expression(expression) for expression in value]

    @field_validator("where")
    @classmethod
    def validate_where(cls, value: str | None) -> str | None:
        if value is None:
            return value

        if _FORBIDDEN_SQL.search(value) or _COMMENT.search(value) or ";" in value:
            raise ValueError("WHERE clause must be read-only")

        return value.strip()


class OracleExecuteSQLQueryWithFiltersInput(AdapterInputSchema):
    """Input for execute_sql_query_with_filters()."""

    sql_statement: str = Field(
        ...,
        min_length=1,
        description="Oracle SELECT or WITH query",
    )
    filters: dict[str, Any] = Field(
        default_factory=dict,
        description="Column equality filters applied to the query result",
    )
    order_by: list[str] = Field(
        default_factory=list,
        description="Optional ORDER BY expressions",
    )
    limit: int | None = Field(
        default=None,
        ge=1,
        le=10000,
        description="Maximum rows to return",
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Rows to skip",
    )
    bind_params: dict[str, Any] = Field(
        default_factory=dict,
        description="Named bind parameters for the query",
    )

    @field_validator("sql_statement")
    @classmethod
    def validate_sql(cls, value: str) -> str:
        return validate_read_only_sql(value)

    @field_validator("order_by")
    @classmethod
    def validate_order_by(cls, value: list[str]) -> list[str]:
        return [_validate_order_expression(expression) for expression in value]

    @model_validator(mode="after")
    def validate_filter_columns(self) -> "OracleExecuteSQLQueryWithFiltersInput":
        for column in self.filters:
            _validate_identifier(column, "filter column")

        return self


class OracleTestConnectionInput(AdapterInputSchema):
    """Input for test_connection()."""


class OracleConnectDatabaseInput(AdapterInputSchema):

    db_connection_string: str = Field(
        ...,
        description="Oracle connection string",
    )

    @field_validator("db_connection_string")
    @classmethod
    def validate_connection_string(cls, value: str) -> str:
        if not value.startswith(("oracle://", "oracle+oracledb://", "oracle+cx_oracle://")):
            raise ValueError("Oracle connection string must use an oracle SQLAlchemy dialect")

        return value


class OracleCommentDBConnectionInput(AdapterInputSchema):

    comment_db_connection_string: str = Field(
        ...,
        description="Oracle metadata connection string",
    )

    @field_validator("comment_db_connection_string")
    @classmethod
    def validate_connection_string(cls, value: str) -> str:
        if not value.startswith(("oracle://", "oracle+oracledb://", "oracle+cx_oracle://")):
            raise ValueError("Oracle connection string must use an oracle SQLAlchemy dialect")

        return value


ORACLE_TOOL_SCHEMA_REGISTRY = {
    "connect_to_database":
        OracleConnectDatabaseInput,

    "create_comment_db_connection":
        OracleCommentDBConnectionInput,

    "get_table_details":
        OracleGetTableDetailsInput,

    "get_column_details":
        OracleGetColumnDetailsInput,

    "get_schema":
        OracleGetSchemaInput,

    "fetch_table":
        OracleFetchTableInput,

    "execute_sql":
        OracleExecuteSQLInput,

    "execute_sql_query_with_filters":
        OracleExecuteSQLQueryWithFiltersInput,

    "test_connection":
        OracleTestConnectionInput,
}