"""Application settings loaded from environment variables."""

from functools import lru_cache

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

YARN_MCP_TOOL_NAMES: tuple[str, ...] = (
    "yarn.getApplicationLogsByName",
    "yarn.getAppAttempts",
    "yarn.tailContainerLogs",
)
YARN_MCP_TOOL_TAG = "yarn_streaming"


class Settings(BaseSettings):
    """Central configuration for the YARN worker agent and MCP server."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    mcp_url: str = Field(
        default="http://127.0.0.1:8080/mcp",
        validation_alias=AliasChoices("mcp_url", "MCP_URL"),
    )
    mcp_timeout: float = Field(
        default=30.0,
        validation_alias=AliasChoices("mcp_timeout", "MCP_TIMEOUT"),
    )

    streaming_app_instance_limit: int = 3

    litellm_api_base: str = Field(
        default="http://localhost:4000",
        validation_alias=AliasChoices(
            "litellm_api_base",
            "LITELLM_API_BASE",
            "LITELLM_SERVER_URL",
        ),
    )
    litellm_api_key: str = ""
    litellm_model: str = Field(
        default="gemini-2.5-flash",
        validation_alias=AliasChoices(
            "litellm_model",
            "LITELLM_MODEL",
            "DEFAULT_MODEL",
        ),
    )
    agent_temperature: float = 0.0

    @field_validator("litellm_api_base", mode="before")
    @classmethod
    def _normalize_litellm_api_base(cls, value: object) -> object:
        """Accept base URL with or without /v1 (shared_litellm uses .../v1)."""
        if isinstance(value, str):
            return value.rstrip("/").removesuffix("/v1")
        return value


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
