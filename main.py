from __future__ import annotations

import asyncio
from typing import Any

from dotenv import load_dotenv
from fastmcp import FastMCP

from adapters.oracle import OracleAdapter
from manifest import build_manifest
from schemas.oracle import (
    OracleExecuteSQLInput,
    OracleFetchTableInput,
    OracleGetColumnDetailsInput,
    OracleGetSchemaInput,
    OracleGetTableDetailsInput,
    OracleTestConnectionInput,
)
from schemas.utils import ConfigureLoggingInput
from tool_specs.oracle_specs import ORACLE_TOOL_SPECS
from utils.config import settings
from utils.errors import ProviderError
from utils.http_client import SharedAsyncClient
from utils.idempotency_redis import IdempotencyStoreRedis
from utils.logging_config import configure_logging
from utils.ratelimit_redis import RedisRateLimiter


load_dotenv()

logger = configure_logging(ConfigureLoggingInput())
mcp = FastMCP(name="oracle-mcp-server")

idempotency_store: IdempotencyStoreRedis | None = None
rate_limiter: RedisRateLimiter | None = None


def oracle_enabled() -> bool:
    return bool(settings.ORACLE_ENABLED and settings.DB_CONNECTION_STRING)


def get_oracle_adapter() -> OracleAdapter:
    if not oracle_enabled():
        raise ProviderError("oracle", "Oracle is disabled or DB_CONNECTION_STRING is not configured", status=503)
    return OracleAdapter()


def _error_payload(exc: Exception) -> dict[str, Any]:
    if isinstance(exc, ProviderError):
        return {
            "ok": False,
            "provider": exc.provider,
            "error": str(exc),
            "status": exc.status_code,
        }
    return {"ok": False, "error": str(exc), "status": 500}


def _params(arguments: dict[str, Any] | None, fallback: dict[str, Any]) -> dict[str, Any]:
    if isinstance(arguments, dict):
        return arguments
    return {key: value for key, value in fallback.items() if value is not None}


async def _run_oracle_tool(tool_name: str, schema_cls, params: dict[str, Any]) -> dict[str, Any]:
    try:
        parsed = schema_cls.parse_or_error(params, "oracle")
        adapter = get_oracle_adapter()
        spec = next(spec for spec in ORACLE_TOOL_SPECS if spec["tool"] == tool_name)
        result = await getattr(adapter, spec["method"])(parsed)
        result_key = spec.get("result_key")
        if result_key:
            return {"ok": True, result_key: result}
        return {"ok": True, "result": result}
    except Exception as exc:
        return _error_payload(exc)


@mcp.resource("resource://manifest")
def manifest_resource():
    return build_manifest({"oracle": oracle_enabled()})


@mcp.resource("resource://health/{action}")
async def health_resource(action: str):
    info: dict[str, Any] = {
        "status": "ok",
        "providers": {
            "oracle": oracle_enabled(),
        },
    }

    if action not in {"check", "ready", "live"}:
        info["status"] = "unknown_action"
        info["message"] = f"Unknown health action: {action}"
        return {"ok": False, "info": info}

    try:
        import redis.asyncio as redis

        client = redis.from_url(settings.REDIS_URL)
        pong = await client.ping()
        info["redis"] = "ok" if pong else "error"
        await client.aclose()
    except Exception as exc:
        info["redis"] = f"unavailable: {exc}"

    if settings.HEALTHCHECK_FULL and oracle_enabled():
        try:
            adapter = OracleAdapter()
            info["oracle_connection"] = (await adapter.test_connection())["connected"]
        except Exception as exc:
            info["oracle_connection"] = False
            info["oracle_error"] = str(exc)

    return {"ok": True, "info": info}


async def init_services():
    global idempotency_store, rate_limiter
    SharedAsyncClient.get_client()

    if settings.IDEMPOTENCY_TTL > 0:
        try:
            idempotency_store = IdempotencyStoreRedis(settings.REDIS_URL)
        except Exception as exc:
            idempotency_store = None
            logger.warning("idempotency store disabled: %s", exc)

    try:
        rate_limiter = RedisRateLimiter(
            settings.REDIS_URL,
            settings.RATE_LIMIT_CAPACITY,
            settings.RATE_LIMIT_REFILL_SECONDS,
            fail_open=settings.RATE_LIMIT_FAIL_OPEN,
        )
        await rate_limiter.init()
    except Exception as exc:
        rate_limiter = None
        logger.warning("rate limiter disabled: %s", exc)


def register_tools():
    async def test_echo(message: str | None = None, arguments: dict[str, Any] | None = None):
        params = _params(arguments, {"message": message})
        return {
            "ok": True,
            "message": params.get("message", "Oracle MCP server is running"),
        }

    mcp.tool(name="test.echo", tags=["test"])(test_echo)

    async def oracle_test_connection(arguments: dict[str, Any] | None = None):
        return await _run_oracle_tool(
            "oracle.testConnection",
            OracleTestConnectionInput,
            _params(arguments, {}),
        )

    mcp.tool(name="oracle.testConnection", tags=["oracle"])(oracle_test_connection)

    async def oracle_get_tables(
        owner: str | None = None,
        include_views: bool = False,
        limit: int = 100,
        arguments: dict[str, Any] | None = None,
    ):
        return await _run_oracle_tool(
            "oracle.getTables",
            OracleGetTableDetailsInput,
            _params(
                arguments,
                {
                    "owner": owner,
                    "include_views": include_views,
                    "limit": limit,
                },
            ),
        )

    mcp.tool(name="oracle.getTables", tags=["oracle"])(oracle_get_tables)

    async def oracle_get_columns(
        table_name: str | None = None,
        owner: str | None = None,
        arguments: dict[str, Any] | None = None,
    ):
        return await _run_oracle_tool(
            "oracle.getColumns",
            OracleGetColumnDetailsInput,
            _params(arguments, {"table_name": table_name, "owner": owner}),
        )

    mcp.tool(name="oracle.getColumns", tags=["oracle"])(oracle_get_columns)

    async def oracle_get_schema(
        owner: str | None = None,
        include_views: bool = False,
        table_limit: int = 100,
        arguments: dict[str, Any] | None = None,
    ):
        return await _run_oracle_tool(
            "oracle.getSchema",
            OracleGetSchemaInput,
            _params(
                arguments,
                {
                    "owner": owner,
                    "include_views": include_views,
                    "table_limit": table_limit,
                },
            ),
        )

    mcp.tool(name="oracle.getSchema", tags=["oracle"])(oracle_get_schema)

    async def oracle_fetch_table(
        table_name: str | None = None,
        owner: str | None = None,
        columns: list[str] | None = None,
        where: str | None = None,
        bind_params: dict[str, Any] | None = None,
        order_by: list[str] | None = None,
        limit: int | None = None,
        offset: int = 0,
        arguments: dict[str, Any] | None = None,
    ):
        return await _run_oracle_tool(
            "oracle.fetchTable",
            OracleFetchTableInput,
            _params(
                arguments,
                {
                    "table_name": table_name,
                    "owner": owner,
                    "columns": columns,
                    "where": where,
                    "bind_params": bind_params,
                    "order_by": order_by,
                    "limit": limit,
                    "offset": offset,
                },
            ),
        )

    mcp.tool(name="oracle.fetchTable", tags=["oracle"])(oracle_fetch_table)

    async def oracle_execute_sql(
        sql_statement: str | None = None,
        bind_params: dict[str, Any] | None = None,
        limit: int | None = None,
        timeout_ms: int = 30000,
        arguments: dict[str, Any] | None = None,
    ):
        return await _run_oracle_tool(
            "oracle.executeSQL",
            OracleExecuteSQLInput,
            _params(
                arguments,
                {
                    "sql_statement": sql_statement,
                    "bind_params": bind_params,
                    "limit": limit,
                    "timeout_ms": timeout_ms,
                },
            ),
        )

    mcp.tool(name="oracle.executeSQL", tags=["oracle"])(oracle_execute_sql)


async def cleanup():
    try:
        await SharedAsyncClient.aclose()
    except Exception:
        logger.exception("http client close error")
    try:
        if idempotency_store:
            await idempotency_store.close()
    except Exception:
        logger.exception("idempotency store close error")
    try:
        if rate_limiter:
            await rate_limiter.close()
    except Exception:
        logger.exception("rate limiter close error")


if __name__ == "__main__":
    asyncio.run(init_services())
    register_tools()
    logger.info("Starting Oracle MCP server on %s:%s", settings.HOST, settings.PORT)
    mcp.run(
        transport=settings.MCP_TRANSPORT,
        host=settings.HOST,
        port=settings.PORT,
        stateless_http=True,
    )
