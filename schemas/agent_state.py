"""
State Management Schemas

Defines TypedDict schemas for Oracle worker agent state management in
LangGraph-style workflows.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Dict, List, Literal, Optional, TypedDict

try:
    from langchain_core.messages import BaseMessage
except ImportError:  # pragma: no cover - optional LangGraph runtime dependency
    BaseMessage = Any  # type: ignore[assignment]

try:
    from langgraph.graph.message import add_messages
except ImportError:  # pragma: no cover - optional LangGraph runtime dependency

    def add_messages(left: List[Any], right: List[Any]) -> List[Any]:
        """Fallback message reducer matching LangGraph's append semantics."""

        return [*left, *right]


try:
    from .agent_metadata import OracleToolName
except ImportError:  # pragma: no cover - supports direct script-style imports
    from schemas.agent_metadata import OracleToolName


class TaskPriority(str, Enum):
    """Priority levels for Oracle worker tasks."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class TaskStatus(str, Enum):
    """Lifecycle status for Oracle worker tasks and tool executions."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentMessage(TypedDict):
    """Message exchanged between agents or workflow nodes."""

    message_id: str
    sender_id: str
    recipient_id: str
    conversation_id: str
    message_type: Literal["request", "response", "event", "error"]
    content: Dict[str, Any]
    created_at: datetime
    metadata: Dict[str, Any]


class AgentState(TypedDict):
    """
    Minimal LangGraph node state for Oracle worker execution.

    The `messages` field keeps LangGraph-compatible merge behavior when
    LangGraph is installed, while the remaining fields support simple worker
    nodes that read a task and write a result.
    """

    messages: Annotated[List[BaseMessage], add_messages]
    task: str
    result: str
    status: str
    agent: str
    current_tool: Optional[OracleToolName]


class BaseAgentState(TypedDict):
    """Base state schema shared by Oracle worker state variants."""

    # Agent identification
    agent_id: str
    agent_type: Literal["worker"]
    provider: Literal["oracle"]
    session_id: str

    # State management
    state_version: int
    last_updated: datetime
    created_at: datetime

    # Communication
    messages: List[AgentMessage]
    pending_responses: List[str]

    # Task tracking
    active_task_ids: List[str]
    completed_task_ids: List[str]
    failed_task_ids: List[str]
    cancelled_task_ids: List[str]
    task_priorities: Dict[str, TaskPriority]
    task_statuses: Dict[str, TaskStatus]

    # Error handling
    errors: List[Dict[str, Any]]
    retry_count: int

    # Metadata
    metadata: Dict[str, Any]


class OracleConnectionState(TypedDict):
    """Current Oracle database connection state."""

    is_connected: bool
    connection_name: Optional[str]
    connection_string_env: str
    default_schema: Optional[str]
    last_connected_at: Optional[datetime]
    last_heartbeat: Optional[datetime]
    last_error: Optional[str]


class OracleQueryExecution(TypedDict):
    """State captured for a single Oracle SQL execution."""

    query_id: str
    sql_statement: str
    status: TaskStatus
    started_at: datetime
    completed_at: Optional[datetime]
    timeout_ms: int
    row_count: Optional[int]
    error: Optional[str]
    metadata: Dict[str, Any]


class OracleSchemaCache(TypedDict):
    """Cached Oracle schema information collected by the worker."""

    tables: List[str]
    columns_by_table: Dict[str, List[Dict[str, Any]]]
    last_refreshed: Optional[datetime]
    refresh_status: TaskStatus


class OracleToolExecution(TypedDict):
    """History entry for an Oracle tool invocation."""

    execution_id: str
    tool_name: OracleToolName
    status: TaskStatus
    started_at: datetime
    completed_at: Optional[datetime]
    input: Dict[str, Any]
    output: Optional[Dict[str, Any]]
    error: Optional[str]


class OracleWorkerAgentState(BaseAgentState):
    """State schema specific to Oracle worker agents."""

    # Tool and execution state
    available_tools: List[OracleToolName]
    current_tool: Optional[OracleToolName]
    tool_execution_history: List[OracleToolExecution]

    # Oracle connection state
    connection: OracleConnectionState
    data_sources: List[str]
    last_data_fetch: Optional[datetime]

    # SQL execution state
    read_only_mode: bool
    current_query: Optional[OracleQueryExecution]
    active_queries: List[OracleQueryExecution]
    query_history: List[OracleQueryExecution]
    default_query_timeout_ms: int

    # Schema introspection state
    schema_cache: OracleSchemaCache
    table_lookup_history: List[Dict[str, Any]]
    column_lookup_history: List[Dict[str, Any]]

    # Result processing
    processed_rows: int
    processed_results: List[Dict[str, Any]]


# Backwards-compatible name for code that expects a generic worker state.
WorkerAgentState = OracleWorkerAgentState


__all__ = [
    "TaskPriority",
    "TaskStatus",
    "AgentMessage",
    "AgentState",
    "BaseAgentState",
    "OracleConnectionState",
    "OracleQueryExecution",
    "OracleSchemaCache",
    "OracleToolExecution",
    "OracleWorkerAgentState",
    "WorkerAgentState",
]
