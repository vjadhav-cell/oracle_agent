"""
Public Input Schemas

Defines Pydantic input models used by Oracle worker agent public helpers,
retry wrappers, lifecycle hooks, and LangGraph node entrypoints.
"""

from typing import Any, Callable, Optional, Tuple, Type

from pydantic import BaseModel, ConfigDict, Field


DEFAULT_RETRY_JITTER_RANGE = 0.1
REGISTER_ORACLE_WORKER_AGENT_DELAY_SECONDS = 2.0
REGISTER_ORACLE_WORKER_AGENT_MAX_ATTEMPTS = 5


class PublicInputModel(BaseModel):
    """Base model for public helper inputs."""

    model_config = ConfigDict(arbitrary_types_allowed=True)


class IsRetryableErrorInput(PublicInputModel):
    """Input for determining whether an exception should be retried."""

    exception: Exception


class GetRetryAfterDelayInput(PublicInputModel):
    """Input for extracting a Retry-After delay from an exception."""

    exception: Exception


class CalculateDelayInput(PublicInputModel):
    """Input for retry delay calculation."""

    attempt: int
    base_delay: float
    max_delay: float
    exponential_backoff: bool = True
    jitter: bool = True
    jitter_range: float = DEFAULT_RETRY_JITTER_RANGE


class AsyncRetryInput(PublicInputModel):
    """Input for executing an async callable with retry handling."""

    func: Callable[..., Any]
    args: tuple[Any, ...] = Field(default_factory=tuple)
    max_attempts: Optional[int] = None
    base_delay: Optional[float] = None
    max_delay: Optional[float] = None
    exponential_backoff: bool = True
    jitter: bool = True
    jitter_range: float = DEFAULT_RETRY_JITTER_RANGE
    retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None
    non_retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None
    total_timeout: Optional[float] = None
    on_retry: Optional[Callable[[Exception, int, float], None]] = None
    respect_retry_after: bool = True
    stats: Optional[Any] = None
    kwargs: dict[str, Any] = Field(default_factory=dict)


class SyncRetryInput(AsyncRetryInput):
    """Input for executing a sync callable with retry handling."""


class RegisterOracleWorkerAgentWithRetryInput(PublicInputModel):
    """Input for registering the Oracle worker agent with retry handling."""

    max_attempts: int = REGISTER_ORACLE_WORKER_AGENT_MAX_ATTEMPTS
    delay_seconds: float = REGISTER_ORACLE_WORKER_AGENT_DELAY_SECONDS


class LifespanInput(PublicInputModel):
    """Input for application lifespan hooks."""

    app: Any


class GetToolsDescriptionInput(PublicInputModel):
    """Input for rendering tool descriptions for an agent prompt."""

    tools: list[Any]


class GetOracleWorkerAgentPromptInput(PublicInputModel):
    """Input for building the Oracle worker agent prompt."""

    tools_description: str = ""


class WorkerAgentNodeInput(PublicInputModel):
    """Input for invoking the Oracle worker agent node."""

    state: dict[str, Any]


__all__ = [
    "DEFAULT_RETRY_JITTER_RANGE",
    "REGISTER_ORACLE_WORKER_AGENT_DELAY_SECONDS",
    "REGISTER_ORACLE_WORKER_AGENT_MAX_ATTEMPTS",
    "PublicInputModel",
    "IsRetryableErrorInput",
    "GetRetryAfterDelayInput",
    "CalculateDelayInput",
    "AsyncRetryInput",
    "SyncRetryInput",
    "RegisterOracleWorkerAgentWithRetryInput",
    "LifespanInput",
    "GetToolsDescriptionInput",
    "GetOracleWorkerAgentPromptInput",
    "WorkerAgentNodeInput",
]
