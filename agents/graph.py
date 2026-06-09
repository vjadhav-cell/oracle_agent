"""LangGraph entrypoint: compiled worker agent."""

from agents.worker import WORKER_NAME, create_worker_agent


async def make_graph():
    """Async factory for LangGraph CLI — loads MCP tools at startup."""
    return await create_worker_agent()


__all__ = ["WORKER_NAME", "create_worker_agent", "make_graph"]
