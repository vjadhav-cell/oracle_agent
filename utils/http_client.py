# core/http_client.py
from typing import Optional
import httpx
import urllib3

# Disable SSL warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class SharedAsyncClient:
    _client: Optional[httpx.AsyncClient] = None

    @classmethod
    def get_client(cls) -> httpx.AsyncClient:
        if cls._client is None:
            cls._client = httpx.AsyncClient(
                timeout=httpx.Timeout(20.0, connect=5.0),
                verify=False  # Disable SSL verification for self-signed certificates
            )
        return cls._client

    @classmethod
    async def aclose(cls):
        if cls._client:
            await cls._client.aclose()
            cls._client = None
