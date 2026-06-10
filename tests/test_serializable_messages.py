"""Tests for AIMessage metadata sanitization."""

import orjson
from langchain_core.messages import AIMessage, HumanMessage

from agents.middleware.serializable_messages import sanitize_message


def test_sanitize_message_strips_non_json_metadata() -> None:
    """AIMessage with non-serializable metadata becomes JSON-safe."""
    message = AIMessage(
        content="ok",
        response_metadata={"token": object()},
    )

    sanitized = sanitize_message(message)

    assert sanitized is not message
    orjson.dumps(sanitized.response_metadata)


def test_sanitize_message_passes_through_non_ai() -> None:
    """Non-AIMessage messages are returned unchanged."""
    message = HumanMessage(content="hello")

    assert sanitize_message(message) is message
