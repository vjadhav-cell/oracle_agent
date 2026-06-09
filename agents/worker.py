"""YARN streaming worker agent factory (LangChain create_agent harness)."""

from __future__ import annotations

from typing import cast

from langchain.agents import create_agent
from langchain.agents.middleware import ModelRetryMiddleware, ToolRetryMiddleware
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph

from agents.middleware.serializable_messages import SerializableMessagesMiddleware
from agents.mcp_tools import load_yarn_mcp_tools
from agents.prompts.yarn_worker_prompt import build_yarn_worker_prompt
from config.settings import Settings, get_settings
from shared_litellm import CustomLiteLLMModel

WORKER_NAME = "yarn_worker"


def _build_model(settings: Settings) -> BaseChatModel:
    """Chat model for the worker loop (shared_litellm CustomLiteLLMModel)."""
    return CustomLiteLLMModel(
        model=settings.litellm_model,
        base_url=settings.litellm_api_base,
        api_key=settings.litellm_api_key,
        temperature=settings.agent_temperature,
    )


def _build_middleware(tools: list[BaseTool]) -> list[
    SerializableMessagesMiddleware
    | ModelRetryMiddleware
    | ToolRetryMiddleware
]:
    """Resilience and LangGraph-safe message metadata for local dev / Studio."""
    tool_names = [tool.name for tool in tools]
    return [
        SerializableMessagesMiddleware(),
        ModelRetryMiddleware(max_retries=2),
        ToolRetryMiddleware(
            max_retries=2,
            tools=cast(list[BaseTool | str], tool_names),
        ),
    ]


def _compile_yarn_worker_agent(
    cfg: Settings,
    tools: list[BaseTool],
) -> CompiledStateGraph:
    """Build the compiled agent graph from model, tools, and settings."""
    return create_agent(
        model=_build_model(cfg),
        tools=tools,
        system_prompt=build_yarn_worker_prompt(
            instance_limit=cfg.streaming_app_instance_limit,
        ),
        middleware=_build_middleware(tools),
        name=WORKER_NAME,
    )


async def create_yarn_worker_agent(
    settings: Settings | None = None,
    *,
    tools: list[BaseTool] | None = None,
) -> CompiledStateGraph:
    """
    Create the YARN worker agent: model + MCP tools loop until the task completes.

    Uses LangChain ``create_agent`` (model calls tools until done).
    See https://docs.langchain.com/oss/python/langchain/agents
    """
    cfg = settings or get_settings()
    resolved_tools = tools if tools is not None else await load_yarn_mcp_tools(cfg)
    return _compile_yarn_worker_agent(cfg, resolved_tools)
