from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

from utils.errors import ProviderError


class AdapterInputSchema(BaseModel):
    """Base schema used by MCP tool adapters."""

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra="forbid",
        populate_by_name=True,
    )

    @classmethod
    def parse_or_error(cls, data: dict[str, Any] | None, provider: str = "mcp"):
        try:
            return cls.model_validate(data or {})
        except ValidationError as exc:
            raise ProviderError(provider, exc.errors(), status=400) from exc

    def to_json(self) -> str:
        return self.model_dump_json()
