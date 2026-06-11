"""
schemas/oracle.py

Oracle MCP Adapter Schemas
"""

from pydantic import Field, field_validator
from schemas.base import AdapterInputSchema


class OracleExecuteSQLInput(AdapterInputSchema):
    """
    Execute a read-only SQL query.
    """

    sql_statement: str = Field(
        ...,
        min_length=1,
        description="Oracle SQL query"
    )

    timeout_ms: int = Field(
        default=30000,
        ge=1000,
        le=120000,
        description="Query timeout in milliseconds"
    )

    @field_validator("sql_statement")
    @classmethod
    def validate_sql(cls, value: str) -> str:

        sql = value.strip().upper()

        forbidden = [
            "INSERT",
            "UPDATE",
            "DELETE",
            "DROP",
            "ALTER",
            "TRUNCATE",
            "MERGE",
            "CREATE"
        ]

        for keyword in forbidden:
            if sql.startswith(keyword):
                raise ValueError(
                    f"{keyword} statements are not allowed"
                )

        return value


class OracleGetTableDetailsInput(AdapterInputSchema):
    """
    Input for get_tables().
    No parameters required.
    """
    pass


class OracleGetColumnDetailsInput(AdapterInputSchema):
    """
    Input for get_columns().
    """

    table_name: str = Field(
        ...,
        description="Oracle table name"
    )


class OracleConnectDatabaseInput(AdapterInputSchema):

    db_connection_string: str = Field(
        ...,
        description="Oracle connection string"
    )


class OracleCommentDBConnectionInput(AdapterInputSchema):

    comment_db_connection_string: str = Field(
        ...,
        description="Oracle metadata connection string"
    )


ORACLE_TOOL_SCHEMA_REGISTRY = {
    "connect_to_database":
        OracleConnectDatabaseInput,

    "create_comment_db_connection":
        OracleCommentDBConnectionInput,

    "get_table_details":
        OracleGetTableDetailsInput,

    "get_column_details":
        OracleGetColumnDetailsInput,

    "execute_sql":
        OracleExecuteSQLInput,
}