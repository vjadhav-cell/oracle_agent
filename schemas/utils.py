from typing import Any

from schemas.base import AdapterInputSchema


class TenantInput(AdapterInputSchema):
    tenant_id: str | None = None


class HeadersFromCtxInput(AdapterInputSchema):
    ctx: Any = None


class RequireMcpAuthAndRateInput(AdapterInputSchema):
    ctx: Any = None
    rate_limiter: Any = None


class ConfigureLoggingInput(AdapterInputSchema):
    level: int = 20


class SetRequestIdInput(AdapterInputSchema):
    rid: str


class IdempotencyGetInput(AdapterInputSchema):
    raw_key: str


class IdempotencySetIfNotExistsInput(AdapterInputSchema):
    raw_key: str
    payload: dict[str, Any]
    ttl: int | None = None


class RedisAllowInput(AdapterInputSchema):
    key: str
    consume: int = 1
