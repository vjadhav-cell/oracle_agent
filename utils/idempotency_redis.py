import hashlib
import json
from typing import Dict, Optional
import redis.asyncio as redis
from schemas.utils import IdempotencyGetInput, IdempotencySetIfNotExistsInput
from utils.config import settings

_PREFIX = "idemp:"

class IdempotencyStoreRedis:
    def __init__(self, url: str | None = None):
        self._url = url or settings.REDIS_URL
        self._client = redis.from_url(self._url, decode_responses=True)

    def _key(self, raw: str) -> str:
        return _PREFIX + hashlib.sha256(raw.encode("utf-8")).hexdigest()

    async def get(self, data: IdempotencyGetInput) -> Optional[Dict]:
        val = await self._client.get(self._key(data.raw_key))
        if not val:
            return None
        try:
            return json.loads(val)
        except Exception:
            return None

    async def set_if_not_exists(self, data: IdempotencySetIfNotExistsInput) -> bool:
        raw = json.dumps(data.payload, default=str)
        ttl = data.ttl or settings.IDEMPOTENCY_TTL
        res = await self._client.set(self._key(data.raw_key), raw, nx=True, ex=ttl)
        return bool(res)

    async def close(self):
        await self._client.close()
