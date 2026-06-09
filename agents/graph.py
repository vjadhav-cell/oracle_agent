"""LangGraph entrypoint: compiled worker agent."""

from config.agent_config import get_worker_name

from agents.worker import create_worker_agent


async def make_graph():
    """Async factory for LangGraph CLI — loads MCP tools at startup."""
    return await create_worker_agent()


__all__ = ["get_worker_name", "create_worker_agent", "make_graph"]
