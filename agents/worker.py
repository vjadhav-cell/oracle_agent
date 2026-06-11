"""Worker agent factory."""

from agent_util.agent_factory import AgentFactory
from langgraph.graph.state import CompiledStateGraph
from shared_litellm import CustomLiteLLMModel

from config.agent_config import get_mcp_tags, get_worker_instructions, get_worker_name
from agents.middleware.serializable_messages import SerializableMessagesMiddleware
from config.settings import Settings, get_settings


def _build_model(settings: Settings) -> CustomLiteLLMModel:
    """Chat model for the worker loop (shared_litellm CustomLiteLLMModel)."""
    return CustomLiteLLMModel(
        model=settings.litellm_model,
        base_url=settings.litellm_server_url,
        api_key=settings.litellm_api_key,
        temperature=settings.litellm_temperature,
    )


async def create_worker_agent(
    settings: Settings | None = None,
) -> CompiledStateGraph:
    """
    Create the worker agent via AgentFactory (MCP tools filtered by tag).

    MCP connections remain open for the process lifetime (LangGraph CLI).
    """
    cfg = settings or get_settings()
    factory = AgentFactory(
        system_prompt=get_worker_instructions(
            instance_limit=cfg.streaming_app_instance_limit,
        ),
        tool_tags=get_mcp_tags(),
        model=_build_model(cfg),
        agent_name=get_worker_name(),
        agent_kwargs={"middleware": [SerializableMessagesMiddleware()]},
    )
    return await factory.build()
