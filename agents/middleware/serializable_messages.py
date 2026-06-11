"""Strip non-JSON-serializable metadata from model messages for LangGraph API persistence."""

from collections.abc import Awaitable, Callable
from typing import Any

import orjson
from langchain_core.messages import AIMessage, BaseMessage

from langchain.agents.middleware.types import (
    AgentMiddleware,
    AgentState,
    ContextT,
    ModelRequest,
    ModelResponse,
    ResponseT,
)


def _is_json_safe(value: Any) -> bool:
    try:
        orjson.dumps(value)
    except TypeError:
        return False
    return True


def _json_safe(value: Any) -> Any:
    """Recursively coerce a value to JSON-serializable data, dropping bad leaves."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        safe_dict: dict[str, Any] = {}
        for key, item in value.items():
            safe_item = _json_safe(item)
            if not _is_json_safe(safe_item):
                continue
            safe_dict[str(key)] = safe_item
        return safe_dict
    if isinstance(value, (list, tuple)):
        safe_list: list[Any] = []
        for item in value:
            safe_item = _json_safe(item)
            if not _is_json_safe(safe_item):
                continue
            safe_list.append(safe_item)
        return safe_list
    if hasattr(value, "model_dump") and callable(value.model_dump):
        try:
            return _json_safe(value.model_dump())
        except Exception:
            return str(value)
    return str(value)


def sanitize_message(message: BaseMessage) -> BaseMessage:
    """Return a copy safe for LangGraph API JSON responses and thread search."""
    if not isinstance(message, AIMessage):
        return message
    return message.model_copy(
        update={
            "additional_kwargs": _json_safe(message.additional_kwargs),
            "response_metadata": _json_safe(message.response_metadata),
        }
    )


def sanitize_messages(messages: list[BaseMessage]) -> list[BaseMessage]:
    return [sanitize_message(m) for m in messages]


class SerializableMessagesMiddleware(
    AgentMiddleware[AgentState[ResponseT], ContextT, ResponseT]
):
    """Ensure AIMessage metadata is JSON-serializable (required for ``langgraph dev``)."""

    def wrap_model_call(
        self,
        request: ModelRequest[ContextT],
        handler: Callable[[ModelRequest[ContextT]], ModelResponse[ResponseT]],
    ) -> ModelResponse[ResponseT]:
        response = handler(request)
        return ModelResponse(
            result=sanitize_messages(response.result),
            structured_response=response.structured_response,
        )

    async def awrap_model_call(
        self,
        request: ModelRequest[ContextT],
        handler: Callable[
            [ModelRequest[ContextT]], Awaitable[ModelResponse[ResponseT]]
        ],
    ) -> ModelResponse[ResponseT]:
        response = await handler(request)
        return ModelResponse(
            result=sanitize_messages(response.result),
            structured_response=response.structured_response,
        )
