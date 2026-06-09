"""Tests for worker agent factory."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.tools import tool
from langgraph.graph.state import CompiledStateGraph

from config.agent_config import get_mcp_tags
from agents.worker import WORKER_NAME, create_worker_agent
from config.settings import Settings


@tool
def _stub_tool() -> str:
    """Stub tool for graph compilation tests."""
    return "ok"


@pytest.mark.asyncio
async def test_create_worker_agent_graph() -> None:
    """Factory returns a compiled LangGraph with model and tools nodes."""
    mock_manager = MagicMock()
    mock_manager.shutdown = AsyncMock()

    with (
        patch(
            "agent_util.agent_factory.fetch_mcp_tools_by_tags",
            new_callable=AsyncMock,
            return_value=(mock_manager, [_stub_tool]),
        ),
        patch(
            "agent_util.agent_factory._get_create_agent",
            side_effect=lambda: __import__(
                "langchain.agents", fromlist=["create_agent"]
            ).create_agent,
        ),
    ):
        graph = await create_worker_agent(
            Settings(streaming_app_instance_limit=2),
        )

    assert isinstance(graph, CompiledStateGraph)
    nodes = set(graph.get_graph().nodes.keys())
    assert "model" in nodes
    assert "tools" in nodes


@pytest.mark.asyncio
async def test_worker_agent_name() -> None:
    """Graph is named for LangGraph / multi-agent embedding."""
    mock_manager = MagicMock()
    mock_manager.shutdown = AsyncMock()

    with (
        patch(
            "agent_util.agent_factory.fetch_mcp_tools_by_tags",
            new_callable=AsyncMock,
            return_value=(mock_manager, [_stub_tool]),
        ),
        patch(
            "agent_util.agent_factory._get_create_agent",
            side_effect=lambda: __import__(
                "langchain.agents", fromlist=["create_agent"]
            ).create_agent,
        ),
    ):
        graph = await create_worker_agent(Settings())

    assert graph.name == WORKER_NAME


@pytest.mark.asyncio
async def test_create_worker_agent_passes_tool_tags() -> None:
    """AgentFactory is configured with MCP tags from agent_config."""
    mock_manager = MagicMock()
    mock_manager.shutdown = AsyncMock()
    captured_factory: list[SimpleNamespace] = []

    original_init = __import__(
        "agent_util.agent_factory", fromlist=["AgentFactory"]
    ).AgentFactory.__init__

    def _capture_init(self, *args, **kwargs):
        captured_factory.append(SimpleNamespace(args=args, kwargs=kwargs))
        return original_init(self, *args, **kwargs)

    with (
        patch(
            "agent_util.agent_factory.fetch_mcp_tools_by_tags",
            new_callable=AsyncMock,
            return_value=(mock_manager, [_stub_tool]),
        ),
        patch(
            "agent_util.agent_factory._get_create_agent",
            side_effect=lambda: __import__(
                "langchain.agents", fromlist=["create_agent"]
            ).create_agent,
        ),
        patch(
            "agent_util.agent_factory.AgentFactory.__init__",
            _capture_init,
        ),
    ):
        await create_worker_agent(Settings())

    assert captured_factory
    assert captured_factory[0].kwargs["tool_tags"] == get_mcp_tags()
    assert captured_factory[0].kwargs["agent_name"] == WORKER_NAME
