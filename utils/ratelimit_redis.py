import time
import redis.asyncio as redis
from schemas.utils import RedisAllowInput
from utils.config import settings
from utils.errors import MCPError

RATE_LIMIT_LUA = r"""
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local rate = tonumber(ARGV[2])
local now_ms = tonumber(ARGV[3])
local consume = tonumber(ARGV[4])
local ttl = tonumber(ARGV[5])
local item = redis.call("HMGET", key, "tokens", "ts")
local tokens = item[1]
local ts = item[2]
if not tokens or not ts then
  tokens = capacity
  ts = now_ms
else
  tokens = tonumber(tokens)
  ts = tonumber(ts)
end
local elapsed = math.max(0, now_ms - ts) / 1000.0
local refill = elapsed * rate
tokens = math.min(capacity, tokens + refill)
if tokens + 1e-9 >= consume then
  tokens = tokens - consume
  redis.call("HMSET", key, "tokens", tostring(tokens), "ts", tostring(now_ms))
  redis.call("EXPIRE", key, ttl)
  return {1, tokens}
else
  redis.call("HMSET", key, "tokens", tostring(tokens), "ts", tostring(now_ms))
  redis.call("EXPIRE", key, ttl)
  return {0, tokens}
end
"""

class RedisRateLimiter:
    def __init__(self, url: str | None = None, capacity: int | None = None, refill_seconds: int | None = None, fail_open: bool | None = None):
        self._url = url or settings.REDIS_URL
        self._client = redis.from_url(self._url, decode_responses=True)
        self.capacity = capacity or settings.RATE_LIMIT_CAPACITY
        self.refill_seconds = refill_seconds or settings.RATE_LIMIT_REFILL_SECONDS
        self.fail_open = settings.RATE_LIMIT_FAIL_OPEN if fail_open is None else fail_open
        self._sha = None

    async def init(self):
        self._sha = await self._client.script_load(RATE_LIMIT_LUA)

    async def allow(self, data: RedisAllowInput) -> bool:
        if not self._sha:
            await self.init()
        now_ms = int(time.time() * 1000)
        rate = float(self.capacity) / float(self.refill_seconds)
        ttl = max(self.refill_seconds * 2, 60)
        try:
            res = await self._client.evalsha(
                self._sha, 1, data.key, str(self.capacity), str(rate), str(now_ms), str(data.consume), str(ttl)
            )
            return bool(int(res[0]))
        except redis.exceptions.NoScriptError:
            self._sha = await self._client.script_load(RATE_LIMIT_LUA)
            res = await self._client.evalsha(
                self._sha, 1, data.key, str(self.capacity), str(rate), str(now_ms), str(data.consume), str(ttl)
            )
            return bool(int(res[0]))
        except Exception as exc:
            if self.fail_open:
                return True
            raise MCPError(f"rate_limiter_error: {exc}")

    async def close(self):
        await self._client.close()
