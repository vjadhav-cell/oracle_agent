"""Tests for settings env aliases (shared_litellm vs local names)."""

from config.settings import Settings


def test_litellm_aliases_from_shared_litellm_env() -> None:
    """LITELLM_SERVER_URL and DEFAULT_MODEL map to worker LLM config."""
    settings = Settings.model_validate(
        {
            "LITELLM_SERVER_URL": "https://proxy.example.com/v1",
            "DEFAULT_MODEL": "gemini-2.5-flash",
        }
    )

    assert settings.litellm_api_base == "https://proxy.example.com"
    assert settings.litellm_model == "gemini-2.5-flash"


def test_mcp_url_default() -> None:
    """MCP_URL defaults to local YARN MCP server."""
    settings = Settings.model_validate({})
    assert settings.mcp_url == "http://127.0.0.1:8080/mcp"
    assert settings.mcp_timeout == 30.0


def test_mcp_url_override() -> None:
    """MCP_URL can be overridden via environment."""
    settings = Settings.model_validate({"MCP_URL": "http://mcp-host:9000/mcp"})
    assert settings.mcp_url == "http://mcp-host:9000/mcp"
