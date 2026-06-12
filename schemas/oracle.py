from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


IDENTIFIER_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_$#]*$")


class AdapterInputSchema(BaseModel):
    """Small local base class used by Oracle tool inputs."""

    model_config = ConfigDict(extra="forbid")

    def to_json(self) -> str:
        return self.model_dump_json()

    @classmethod
    def parse_or_error(cls, data: dict[str, Any], provider: str = "oracle"):
        return cls.model_validate(data)


def validate_identifier(value: str, field_name: str = "identifier") -> str:
    """Only allow plain Oracle identifiers, not SQL fragments."""
    if not IDENTIFIER_RE.match(value):
        raise ValueError(f"{field_name} must be a simple Oracle identifier")
    return value.upper()


def validate_read_only_sql(sql_statement: str) -> str:
    """Allow SELECT/WITH queries and reject common write/DDL statements."""
    sql = sql_statement.strip().rstrip(";")
    upper_sql = sql.upper()

    if not (upper_sql.startswith("SELECT") or upper_sql.startswith("WITH")):
        raise ValueError("Only SELECT or WITH queries are allowed")

    forbidden = (
        "INSERT",
        "UPDATE",
        "DELETE",
        "DROP",
        "ALTER",
        "TRUNCATE",
        "MERGE",
        "CREATE",
        "GRANT",
        "REVOKE",
    )
    for keyword in forbidden:
        if re.search(rf"\b{keyword}\b", upper_sql):
            raise ValueError(f"{keyword} statements are not allowed")

    return sql


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
        return validate_identifier(value, "table_name")

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
    bind_params: dict[str, Any] = Field(default_factory=dict)
    order_by: list[str] | None = None
    limit: int | None = Field(default=None, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)

    @field_validator("table_name")
    @classmethod
    def validate_table_name(cls, value: str) -> str:
        return validate_identifier(value, "table_name")

    @field_validator("owner")
    @classmethod
    def validate_owner(cls, value: str | None) -> str | None:
        return validate_identifier(value, "owner") if value else value

    @field_validator("columns", "order_by")
    @classmethod
    def validate_identifier_list(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        return [validate_identifier(item, "column") for item in value]


class OracleExecuteSQLInput(AdapterInputSchema):
    sql_statement: str = Field(..., min_length=1)
    bind_params: dict[str, Any] = Field(default_factory=dict)
    limit: int | None = Field(default=None, ge=1, le=1000)
    timeout_ms: int = Field(default=30000, ge=1000, le=120000)

    @field_validator("sql_statement")
    @classmethod
    def validate_sql(cls, value: str) -> str:
        return validate_read_only_sql(value)


class OracleExecuteSQLQueryWithFiltersInput(OracleExecuteSQLInput):
    filters: dict[str, Any] = Field(
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
        return [validate_identifier(item, "order_by column") for item in value]


class OracleConnectDatabaseInput(AdapterInputSchema):
    db_connection_string: str = Field(..., description="Oracle connection string")

    @field_validator("db_connection_string")
    @classmethod
    def validate_connection_string(cls, value: str) -> str:
        if not value.startswith(("oracle://", "oracle+oracledb://")):
            raise ValueError("Oracle connection string must start with oracle:// or oracle+oracledb://")
        return value


class OracleCommentDBConnectionInput(AdapterInputSchema):
    comment_db_connection_string: str = Field(..., description="Oracle metadata connection string")

    @field_validator("comment_db_connection_string")
    @classmethod
    def validate_connection_string(cls, value: str) -> str:
        if not value.startswith(("oracle://", "oracle+oracledb://")):
            raise ValueError("Oracle connection string must start with oracle:// or oracle+oracledb://")
        return value


ORACLE_TOOL_SCHEMA_REGISTRY = {
    "connect_to_database": OracleConnectDatabaseInput,
    "create_comment_db_connection": OracleCommentDBConnectionInput,
    "get_table_details": OracleGetTableDetailsInput,
    "get_column_details": OracleGetColumnDetailsInput,
    "get_schema": OracleGetSchemaInput,
    "fetch_table": OracleFetchTableInput,
    "execute_sql": OracleExecuteSQLInput,
    "execute_sql_query_with_filters": OracleExecuteSQLQueryWithFiltersInput,
}