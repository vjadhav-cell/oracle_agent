"""Worker agent package."""

from config.agent_config import get_worker_name

from agents.worker import create_worker_agent

__all__ = ["get_worker_name", "create_worker_agent"]
