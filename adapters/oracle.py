import os
from typing import Any, Dict, List

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from schemas.oracle import (
    OracleExecuteSQLInput,
    OracleGetTableDetailsInput,
    OracleGetColumnDetailsInput,
)

from utils.errors import ProviderError


class OracleAdapter:
    name = "oracle"

    def __init__(self, tenant_id: str | None = None):  

        self.connection_string = os.getenv("DB_CONNECTION_STRING") 

        if not self.connection_string:
            raise ProviderError(
                "oracle",
                "DB_CONNECTION_STRING not found in .env"
            )

        try:
            self.engine = create_engine(
                self.connection_string,
                pool_pre_ping=True,
                pool_recycle=3600,
            )
        except Exception as exc:
            raise ProviderError("oracle", str(exc))

    # Added: MCP calls this as "connect_to_database"
    async def connect_to_database(self, connection_string: str = None) -> Dict[str, Any]:
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT 'CONNECTED' AS STATUS FROM DUAL"))
                return {
                    "success": True,
                    "result": [dict(row._mapping) for row in result],
                }
        except Exception as exc:
            raise ProviderError("oracle", str(exc))

    # Added: MCP calls this as "execute_sql"
    async def execute_sql(self, sql_statement: str) -> List[Dict[str, Any]]:
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(sql_statement))
                return [dict(row._mapping) for row in result]
        except SQLAlchemyError as exc:
            raise ProviderError("oracle", str(exc))

    async def execute_query(self, data: OracleExecuteSQLInput) -> List[Dict[str, Any]]:
        return await self.execute_sql(data.sql_statement)

    async def get_tables(self, data: OracleGetTableDetailsInput | None = None) -> List[Dict[str, Any]]:
        sql = """
            SELECT TABLE_NAME
            FROM USER_TABLES
            ORDER BY TABLE_NAME
        """
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(sql))
                return [dict(row._mapping) for row in result]
        except SQLAlchemyError as exc:
            raise ProviderError("oracle", str(exc))

    async def get_columns(self, data: OracleGetColumnDetailsInput) -> List[Dict[str, Any]]:
        sql = """
            SELECT
                COLUMN_NAME,
                DATA_TYPE,
                DATA_LENGTH,
                NULLABLE
            FROM USER_TAB_COLUMNS
            WHERE TABLE_NAME = :table_name
            ORDER BY COLUMN_ID
        """
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(sql), {"table_name": data.table_name.upper()})
                return [dict(row._mapping) for row in result]
        except SQLAlchemyError as exc:
            raise ProviderError("oracle", str(exc))

    async def get_schema(self) -> Dict[str, Any]:
        try:
            tables = await self.get_tables()
            schema = {}
            for table in tables:
                table_name = table["TABLE_NAME"]
                columns = await self.get_columns(
                    OracleGetColumnDetailsInput(table_name=table_name)
                )
                schema[table_name] = columns
            return schema
        except Exception as exc:
            raise ProviderError("oracle", str(exc))