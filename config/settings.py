"""Application settings loaded from environment variables."""

from agent_util.config import BaseAgentSettings, get_settings as _get_settings
from pydantic import Field, field_validator
from pydantic_settings import SettingsConfigDict


class Settings(BaseAgentSettings):
    """YARN worker settings extending shared agent-util base."""

    model_config = SettingsConfigDict(populate_by_name=True)

    streaming_app_instance_limit: int = Field(
        default=3,
        alias="STREAMING_APP_INSTANCE_LIMIT",
    )

    @field_validator("litellm_server_url", mode="before")
    @classmethod
    def _normalize_litellm_server_url(cls, value: object) -> object:
        """Accept base URL with or without /v1 (shared_litellm uses .../v1)."""
        if isinstance(value, str):
            return value.rstrip("/").removesuffix("/v1")
        return value


def get_settings() -> Settings:
    """Return cached settings instance."""
    return _get_settings(Settings)
