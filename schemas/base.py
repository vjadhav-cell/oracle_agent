from __future__ import annotations

import json
from typing import Any, TypeVar

from pydantic import BaseModel, ConfigDict, ValidationError

from utils.errors import ProviderError


SchemaT = TypeVar("SchemaT", bound="AdapterInputSchema")


class AdapterInputSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    @classmethod
    def parse_or_error(cls: type[SchemaT], data: dict[str, Any], provider: str) -> SchemaT:
        try:
            return cls.model_validate(data)
        except ValidationError as exc:
            raise ProviderError(provider, str(exc), status=400) from exc

    def to_json(self) -> str:
        return json.dumps(self.model_dump(mode="json", exclude_none=True))
