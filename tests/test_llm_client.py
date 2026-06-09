"""Tests for shared_litellm CustomLiteLLMModel wiring."""

import os
from unittest.mock import patch

from shared_litellm import CustomLiteLLMModel, create_custom_litellm_model

from agents.worker import _build_model
from config.settings import Settings


def test_build_model_uses_custom_litellm() -> None:
    """Worker model is CustomLiteLLMModel configured from Settings."""
    model = _build_model(
        Settings(
            litellm_api_base="http://litellm:4000",
            litellm_api_key="sk-test",
            litellm_model="gemma4",
            agent_temperature=0.2,
        )
    )

    assert isinstance(model, CustomLiteLLMModel)
    assert model.model == "gemma4"
    assert model.base_url == "http://litellm:4000"
    assert model.api_key == "sk-test"
    assert model.temperature == 0.2
    assert model._llm_type == "custom_litellm"


def test_create_custom_litellm_model_from_env() -> None:
    """Factory reads LITELLM_SERVER_URL, DEFAULT_MODEL, and related env vars."""
    env = {
        "LITELLM_SERVER_URL": "http://proxy:4000",
        "LITELLM_API_KEY": "key",
        "DEFAULT_MODEL": "test-model",
        "LITELLM_TEMPERATURE": "0.5",
    }
    with patch.dict(os.environ, env, clear=False):
        model = create_custom_litellm_model()

    assert isinstance(model, CustomLiteLLMModel)
    assert model.model == "test-model"
    assert model.base_url == "http://proxy:4000"
    assert model.api_key == "key"
    assert model.temperature == 0.5
