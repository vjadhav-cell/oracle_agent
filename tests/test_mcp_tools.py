"""Tests for MCP tool loading."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.tools import StructuredTool
from mcp.types import Tool as MCPTool

from agents.mcp_tools import _filter_mcp_tools_by_tag, load_yarn_mcp_tools
from config.settings import YARN_MCP_TOOL_NAMES, YARN_MCP_TOOL_TAG, Settings


def _make_mcp_tool(name: str, *, tags: list[str] | None = None) -> MCPTool:
    payload: dict[str, object] = {
        "name": name,
        "description": "Test tool",
        "inputSchema": {"type": "object", "properties": {}},
    }
    if tags is not None:
        payload["_meta"] = {"fastmcp": {"tags": tags}}
    return MCPTool.model_validate(payload)


def _make_langchain_tool(name: str) -> StructuredTool:
    def _handler() -> str:
        """Test tool."""
        return "ok"

    return StructuredTool.from_function(_handler, name=name)


@pytest.mark.asyncio
async def test_load_yarn_mcp_tools_success() -> None:
    """Returns only tagged tools when MCP server exposes expected YARN tools."""
    mcp_tools = [
        _make_mcp_tool(name, tags=[YARN_MCP_TOOL_TAG]) for name in YARN_MCP_TOOL_NAMES
    ]
    mcp_tools.append(_make_mcp_tool("yarn.otherTool", tags=["other"]))
    langchain_tools = [_make_langchain_tool(name) for name in YARN_MCP_TOOL_NAMES]

    mock_session = MagicMock()
    mock_client = MagicMock()
    mock_client.session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_client.session.return_value.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("agents.mcp_tools.MultiServerMCPClient", return_value=mock_client),
        patch("agents.mcp_tools._list_all_tools", AsyncMock(return_value=mcp_tools)),
        patch(
            "agents.mcp_tools.convert_mcp_tool_to_langchain_tool",
            side_effect=langchain_tools,
        ),
    ):
        tools = await load_yarn_mcp_tools(Settings(mcp_url="http://127.0.0.1:8080/mcp"))

    assert {t.name for t in tools} == set(YARN_MCP_TOOL_NAMES)


@pytest.mark.asyncio
async def test_load_yarn_mcp_tools_missing_raises() -> None:
    """Raises when tagged MCP tools are incomplete."""
    mcp_tools = [_make_mcp_tool("yarn.getApplicationLogsByName", tags=[YARN_MCP_TOOL_TAG])]
    mock_session = MagicMock()
    mock_client = MagicMock()
    mock_client.session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_client.session.return_value.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("agents.mcp_tools.MultiServerMCPClient", return_value=mock_client),
        patch("agents.mcp_tools._list_all_tools", AsyncMock(return_value=mcp_tools)),
    ):
        with pytest.raises(RuntimeError, match="MCP server missing tagged tools"):
            await load_yarn_mcp_tools(Settings())


@pytest.mark.asyncio
async def test_load_yarn_mcp_tools_no_tagged_tools_raises() -> None:
    """Raises when MCP server exposes no tools with the streaming tag."""
    mcp_tools = [_make_mcp_tool("yarn.getApplicationLogsByName", tags=["other"])]
    mock_session = MagicMock()
    mock_client = MagicMock()
    mock_client.session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_client.session.return_value.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("agents.mcp_tools.MultiServerMCPClient", return_value=mock_client),
        patch("agents.mcp_tools._list_all_tools", AsyncMock(return_value=mcp_tools)),
    ):
        with pytest.raises(RuntimeError, match=f"No MCP tools found with tag '{YARN_MCP_TOOL_TAG}'"):
            await load_yarn_mcp_tools(Settings())


def test_filter_mcp_tools_by_tag() -> None:
    """Tag filter keeps only MCP tools with the requested FastMCP metadata tag."""
    tagged = _make_mcp_tool("yarn.getAppAttempts", tags=[YARN_MCP_TOOL_TAG])
    untagged = _make_mcp_tool("yarn.otherTool", tags=["other"])

    filtered = _filter_mcp_tools_by_tag([tagged, untagged], YARN_MCP_TOOL_TAG)

    assert [tool.name for tool in filtered] == ["yarn.getAppAttempts"]


def test_filter_mcp_tools_by_tag_supports_legacy_fastmcp_key() -> None:
    """Tag filter also reads tags from legacy `_fastmcp` metadata key."""
    tool = MCPTool.model_validate(
        {
            "name": "yarn.getAppAttempts",
            "description": "Test tool",
            "inputSchema": {"type": "object", "properties": {}},
            "_meta": {"_fastmcp": {"tags": [YARN_MCP_TOOL_TAG]}},
        }
    )

    filtered = _filter_mcp_tools_by_tag([tool], YARN_MCP_TOOL_TAG)

    assert [t.name for t in filtered] == ["yarn.getAppAttempts"]
