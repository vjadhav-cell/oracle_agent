"""
Agent Metadata Schemas

Defines TypedDict schemas for Oracle worker agent identification,
configuration, capabilities, and registry management.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, TypedDict


class AgentType(str, Enum):
    """Enumeration of supported agent roles."""

    WORKER = "worker"
    PLANNER = "planner"
    RCA = "rca"


class AgentProvider(str, Enum):
    """Enumeration of supported agent providers."""

    ORACLE = "oracle"


class OracleToolName(str, Enum):
    """Oracle tools exposed by the worker agent."""

    CONNECT_TO_DATABASE = "connect_to_database"
    CREATE_COMMENT_DB_CONNECTION = "create_comment_db_connection"
    GET_TABLE_DETAILS = "get_table_details"
    GET_COLUMN_DETAILS = "get_column_details"
    GET_SCHEMA = "get_schema"
    EXECUTE_SQL = "execute_sql"


class AgentSkill(TypedDict):
    """A skill exposed by an agent."""

    id: str
    name: str
    description: str
    tool_name: OracleToolName
    tags: List[str]
    examples: List[str]
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]


class AgentCapabilities(TypedDict):
    """Capabilities supported by the Oracle worker agent."""

    supported_tools: List[OracleToolName]
    skills: List[AgentSkill]
    read_only_sql: bool
    schema_introspection: bool
    connection_management: bool
    max_query_timeout_ms: Optional[int]


class AgentCard(TypedDict):
    """Public identity and capability card for an Oracle worker agent."""

    agent_id: str
    agent_type: AgentType
    provider: AgentProvider
    name: str
    description: str
    version: str
    capabilities: AgentCapabilities
    default_input_modes: List[str]
    default_output_modes: List[str]
    tags: List[str]


class AgentStatus(TypedDict):
    """Current status of an agent."""

    is_active: bool
    is_healthy: bool
    last_heartbeat: datetime
    active_tasks: int
    error_count: int


class OracleConnectionConfig(TypedDict):
    """Oracle database connection configuration."""

    connection_string_env: str
    comment_connection_string_env: Optional[str]
    default_schema: Optional[str]
    query_timeout_ms: int


class AgentConfig(TypedDict):
    """Configuration parameters for an Oracle worker agent."""

    agent_id: str
    agent_type: AgentType
    provider: AgentProvider
    name: str
    description: str
    version: str
    capabilities: AgentCapabilities

    # LLM configuration
    default_model: str
    temperature: float
    max_tokens: Optional[int]

    # Communication settings
    communication_timeout: int
    retry_attempts: int

    # Oracle settings
    oracle: OracleConnectionConfig

    # Custom configuration
    custom_config: Dict[str, Any]


class AgentMetadata(TypedDict):
    """Complete metadata for an Oracle worker agent instance."""

    config: AgentConfig
    status: AgentStatus
    card: AgentCard
    created_at: datetime
    updated_at: datetime
    tags: List[str]
    dependencies: List[str]
    endpoints: Dict[str, str]


class AgentRegistry(TypedDict):
    """Registry of all Oracle worker agents in the system."""

    agents: Dict[str, AgentMetadata]
    active_count: int
    total_count: int
    last_updated: datetime
    system_health: Literal["healthy", "degraded", "critical"]


__all__ = [
    "AgentType",
    "AgentProvider",
    "OracleToolName",
    "AgentSkill",
    "AgentCapabilities",
    "AgentCard",
    "AgentStatus",
    "OracleConnectionConfig",
    "AgentConfig",
    "AgentMetadata",
    "AgentRegistry",
]
