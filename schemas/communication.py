"""
Communication Schemas

Defines schemas for Oracle worker inter-agent communication protocols and
message formats.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, TypedDict, Union

try:
    from .agent_metadata import OracleToolName
except ImportError:  # pragma: no cover - supports direct script-style imports
    from schemas.agent_metadata import OracleToolName


class MessageType(str, Enum):
    """Types of messages exchanged by Oracle worker agents."""

    TASK_REQUEST = "task_request"
    TASK_RESPONSE = "task_response"
    STATUS_UPDATE = "status_update"
    HEARTBEAT = "heartbeat"
    ERROR_REPORT = "error_report"
    DATA_SHARE = "data_share"
    COORDINATION = "coordination"
    SHUTDOWN = "shutdown"

    # Oracle-specific workflow messages
    ORACLE_CONNECTION_REQUEST = "oracle_connection_request"
    ORACLE_CONNECTION_RESPONSE = "oracle_connection_response"
    ORACLE_QUERY_REQUEST = "oracle_query_request"
    ORACLE_QUERY_RESPONSE = "oracle_query_response"
    ORACLE_SCHEMA_REQUEST = "oracle_schema_request"
    ORACLE_SCHEMA_RESPONSE = "oracle_schema_response"


class MessagePriority(str, Enum):
    """Priority levels for inter-agent messages."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class MessagePart(TypedDict):
    """A single part of a structured message payload."""

    part_id: str
    type: Literal["text", "json", "tool_call", "tool_result"]
    content: Union[str, Dict[str, Any], List[Any]]
    metadata: Dict[str, Any]


class Message(TypedDict):
    """A structured message with one or more content parts."""

    message_id: str
    role: Literal["system", "user", "assistant", "agent", "tool"]
    parts: List[MessagePart]
    created_at: datetime
    metadata: Dict[str, Any]


class Thread(TypedDict):
    """A conversation thread shared by agents."""

    thread_id: str
    participants: List[str]
    messages: List[Message]
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any]


class OracleConnectionContent(TypedDict):
    """Payload for Oracle connection request or status messages."""

    connection_name: Optional[str]
    connection_string_env: str
    default_schema: Optional[str]
    is_connected: Optional[bool]


class OracleQueryContent(TypedDict):
    """Payload for Oracle SQL query requests."""

    sql_statement: str
    timeout_ms: int
    read_only: bool
    parameters: Dict[str, Any]


class OracleSchemaContent(TypedDict):
    """Payload for Oracle schema introspection requests."""

    table_name: Optional[str]
    include_columns: bool
    refresh_cache: bool


class OracleToolResultContent(TypedDict):
    """Payload for Oracle tool execution responses."""

    tool_name: OracleToolName
    ok: bool
    result: Optional[Dict[str, Any]]
    error: Optional[str]


class MessageParams(TypedDict):
    """Parameters for an A2A-style message send request."""

    message_type: MessageType
    sender_id: str
    recipient_id: Optional[str]
    priority: MessagePriority
    content: Dict[str, Any]
    thread_id: Optional[str]
    conversation_id: Optional[str]
    requires_response: bool
    correlation_id: Optional[str]
    metadata: Dict[str, Any]


class A2AError(TypedDict):
    """Error payload for A2A-style message responses."""

    code: str
    message: str
    details: Dict[str, Any]
    retryable: bool


class A2AMessageRequest(TypedDict):
    """A2A-style JSON-RPC message request."""

    jsonrpc: Literal["2.0"]
    id: str
    method: Literal["message/send"]
    params: MessageParams


class A2AMessageResponse(TypedDict):
    """A2A-style JSON-RPC message response."""

    jsonrpc: Literal["2.0"]
    id: str
    result: Optional[Message]
    error: Optional[A2AError]


class AgentMessage(TypedDict):
    """TypedDict version for LangGraph state management."""

    message_id: str
    message_type: MessageType
    sender_id: str
    recipient_id: Optional[str]
    timestamp: datetime
    priority: MessagePriority
    content: Dict[str, Any]
    thread_id: Optional[str]
    conversation_id: Optional[str]
    requires_response: bool
    correlation_id: Optional[str]


__all__ = [
    "MessageType",
    "MessagePriority",
    "MessagePart",
    "Message",
    "Thread",
    "OracleConnectionContent",
    "OracleQueryContent",
    "OracleSchemaContent",
    "OracleToolResultContent",
    "MessageParams",
    "A2AError",
    "A2AMessageRequest",
    "A2AMessageResponse",
    "AgentMessage",
]
