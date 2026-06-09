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
