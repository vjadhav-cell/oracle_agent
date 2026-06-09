"""Load YARN tools from the external MCP server."""

from __future__ import annotations

import asyncio

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.sessions import Connection
from langchain_mcp_adapters.tools import (
    _list_all_tools,
    convert_mcp_tool_to_langchain_tool,
)
from mcp.types import Tool as MCPTool

from config.settings import YARN_MCP_TOOL_NAMES, YARN_MCP_TOOL_TAG, Settings

YARN_MCP_SERVER = "yarn"


def _mcp_tool_tags(tool: MCPTool) -> list[str]:
    """Read FastMCP tags from MCP tool metadata."""
    if not tool.meta:
        return []
    for key in ("fastmcp", "_fastmcp"):
        section = tool.meta.get(key)
        if isinstance(section, dict):
            tags = section.get("tags")
            if isinstance(tags, list):
                return [str(tag) for tag in tags]
    return []


def _filter_mcp_tools_by_tag(tools: list[MCPTool], tag: str) -> list[MCPTool]:
    """Keep MCP tools that declare the given FastMCP tag."""
    return [tool for tool in tools if tag in _mcp_tool_tags(tool)]


async def load_yarn_mcp_tools(settings: Settings) -> list[BaseTool]:
    """Connect to the MCP server and return tagged YARN streaming tools."""
    connection: Connection = {
        "url": settings.mcp_url,
        "transport": "streamable_http",
    }
    client = MultiServerMCPClient({YARN_MCP_SERVER: connection})

    async with client.session(YARN_MCP_SERVER) as session:
        mcp_tools = await asyncio.wait_for(
            _list_all_tools(session),
            timeout=settings.mcp_timeout,
        )

    tagged_mcp_tools = _filter_mcp_tools_by_tag(mcp_tools, YARN_MCP_TOOL_TAG)
    if not tagged_mcp_tools:
        raise RuntimeError(
            f"No MCP tools found with tag '{YARN_MCP_TOOL_TAG}' at {settings.mcp_url}"
        )

    loaded_names: set[str] = {tool.name for tool in tagged_mcp_tools}
    missing = set[str](YARN_MCP_TOOL_NAMES) - loaded_names
    if missing:
        raise RuntimeError(
            f"MCP server missing tagged tools {sorted(missing)} "
            f"(tag='{YARN_MCP_TOOL_TAG}')"
        )

    return [
        convert_mcp_tool_to_langchain_tool(
            None,
            tool,
            connection=connection,
            server_name=YARN_MCP_SERVER,
        )
        for tool in tagged_mcp_tools
    ]
