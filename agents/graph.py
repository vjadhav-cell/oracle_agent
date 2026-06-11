"""LangGraph entrypoint: compiled worker agent."""

from agents.worker import create_worker_agent


async def make_graph():
    """Async factory for LangGraph CLI — loads MCP tools at startup."""
    return await create_worker_agent()
