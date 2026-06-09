"""Tests for YARN worker agent factory."""

import pytest
from langchain_core.tools import tool
from langgraph.graph.state import CompiledStateGraph

from agents.worker import WORKER_NAME, _compile_yarn_worker_agent
from config.settings import Settings


@tool
def _stub_yarn_tool() -> str:
    """Stub tool for graph compilation tests."""
    return "ok"


def test_compile_yarn_worker_agent_graph() -> None:
    """Factory returns a compiled LangGraph with model and tools nodes."""
    graph = _compile_yarn_worker_agent(
        Settings(streaming_app_instance_limit=2),
        tools=[_stub_yarn_tool],
    )
    assert isinstance(graph, CompiledStateGraph)
    nodes = set(graph.get_graph().nodes.keys())
    assert "model" in nodes
    assert "tools" in nodes


def test_worker_agent_name() -> None:
    """Graph is named for LangGraph / multi-agent embedding."""
    graph = _compile_yarn_worker_agent(Settings(), tools=[_stub_yarn_tool])
    assert graph.name == WORKER_NAME


@pytest.mark.asyncio
async def test_create_yarn_worker_agent_uses_injected_tools() -> None:
    """Async factory accepts pre-built tools without contacting MCP."""
    from agents.worker import create_yarn_worker_agent

    graph = await create_yarn_worker_agent(tools=[_stub_yarn_tool])
    assert isinstance(graph, CompiledStateGraph)
    assert graph.name == WORKER_NAME
