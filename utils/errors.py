from typing import Any, Dict


class MCPError(Exception):
    status_code = 500
    code = "internal_error"
    def to_payload(self) -> Dict[str, Any]:
        return {"ok": False, "code": self.code, "message": str(self)}

class AuthError(MCPError):
    status_code = 401
    code = "unauthorized"

class ProviderError(MCPError):
    status_code = 502
    code = "provider_error"
    def __init__(self, provider: str, message: str, status: int | None = None):
        super().__init__(message)
        self.provider = provider
        if status:
            self.status_code = status

class RateLimitError(MCPError):
    status_code = 429
    code = "rate_limited"
