"""Per-worker configuration — customize prompt and MCP tool tags to define a worker."""

from agents.instructions import (
    WORKER_OUTPUT,
    WORKER_ROLE,
    WORKER_RULES,
    WORKER_WORKFLOW,
)

WORKER_NAME = "yarn_worker"

MCP_TOOL_TAGS = ["yarn_streaming"]


def get_worker_instructions(instance_limit: int = 3) -> str:
    """Assemble the worker system prompt."""
    fmt = {"instance_limit": instance_limit}
    return "\n\n".join(
        [
            WORKER_ROLE.format(**fmt),
            WORKER_WORKFLOW.format(**fmt),
            WORKER_RULES.format(**fmt),
            WORKER_OUTPUT,
        ]
    )


def get_mcp_tags() -> list[str]:
    """Return MCP tool tags used to filter tools for this worker."""
    return MCP_TOOL_TAGS


def get_worker_name() -> str:
    """Return the name of the worker agent."""
    return WORKER_NAME
