"""Tests for worker system prompt assembly."""

from config.agent_config import get_worker_instructions


def test_worker_instructions_includes_instance_limit() -> None:
    """Prompt wires instance_limit into role, workflow, and rules."""
    prompt = get_worker_instructions(instance_limit=2)

    assert "last 2 application restarts" in prompt
    assert "limit: 2" in prompt
    assert "at most 2 relevant" in prompt
    assert "at most 2 instances" in prompt
