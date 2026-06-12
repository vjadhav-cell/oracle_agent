from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class AdapterInputSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    def to_json(self) -> str:
        return self.model_dump_json()

    @classmethod
    def parse_or_error(cls, data: dict[str, Any], provider: str | None = None):
        return cls.model_validate(data)
