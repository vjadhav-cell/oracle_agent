"""YARN streaming worker agent factory."""

from __future__ import annotations

from agent_util.agent_factory import AgentFactory
from langgraph.graph.state import CompiledStateGraph
from shared_litellm import CustomLiteLLMModel

from agents.middleware.serializable_messages import SerializableMessagesMiddleware
from agents.prompts.yarn_worker_prompt import build_yarn_worker_prompt
from config.settings import Settings, get_settings

WORKER_NAME = "yarn_worker"
YARN_TOOL_TAGS = ["yarn_streaming"]


def _build_model(settings: Settings) -> CustomLiteLLMModel:
    """Chat model for the worker loop (shared_litellm CustomLiteLLMModel)."""
    return CustomLiteLLMModel(
        model=settings.litellm_model,
        base_url=settings.litellm_api_base,
        api_key=settings.litellm_api_key,
        temperature=settings.agent_temperature,
    )


async def create_yarn_worker_agent(
    settings: Settings | None = None,
) -> CompiledStateGraph:
    """
    Create the YARN worker agent via AgentFactory (MCP tools filtered by tag).

    MCP connections remain open for the process lifetime (LangGraph CLI).
    """
    cfg = settings or get_settings()
    factory = AgentFactory(
        system_prompt=build_yarn_worker_prompt(
            instance_limit=cfg.streaming_app_instance_limit,
        ),
        tool_tags=YARN_TOOL_TAGS,
        model=_build_model(cfg),
        agent_name=WORKER_NAME,
        agent_kwargs={"middleware": [SerializableMessagesMiddleware()]},
    )
    return await factory.build()
