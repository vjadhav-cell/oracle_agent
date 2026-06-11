import uuid
from schemas.utils import HeadersFromCtxInput, RedisAllowInput, RequireMcpAuthAndRateInput, SetRequestIdInput
from utils.config import settings
from utils.errors import AuthError, RateLimitError
from utils.logging_config import set_request_id
from utils.request_helpers import headers_from_ctx


async def require_mcp_auth_and_rate(data: RequireMcpAuthAndRateInput) -> str:
    headers = headers_from_ctx(HeadersFromCtxInput(ctx=data.ctx))
    auth = headers.get("Authorization") or headers.get("authorization")
    if not auth or not auth.startswith("Bearer "):
        raise AuthError("Missing Authorization Bearer token")
    token = auth.split(" ", 1)[1].strip()
    if token != settings.MCP_API_KEY:
        raise AuthError("Invalid API key")
    # set request id for logs
    rid = headers.get("X-Request-Id") or headers.get("x-request-id") or str(uuid.uuid4())
    try:
        set_request_id(SetRequestIdInput(rid=rid))
    except Exception:
        pass
    if data.rate_limiter:
        try:
            allowed = await data.rate_limiter.allow(RedisAllowInput(key=f"rl:client:{token}"))
            if not allowed:
                raise RateLimitError("rate limit exceeded")
        except Exception as e:
            # If rate limiter fails, log warning but don't block the request
            # This allows the service to continue working even if Redis is down
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Rate limiter error (allowing request): {e}")
    return token
