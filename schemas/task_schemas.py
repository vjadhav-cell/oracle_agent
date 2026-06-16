"""
Task Management Schemas

Defines TypedDict schemas for Oracle worker task definition, execution,
results, and template tracking.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, TypedDict, Union

try:
    from .agent_metadata import OracleToolName
except ImportError:  # pragma: no cover - supports direct script-style imports
    from schemas.agent_metadata import OracleToolName


class TaskType(str, Enum):
    """Types of tasks that can be executed by Oracle worker agents."""

    DATABASE_CONNECTION = "database_connection"
    SCHEMA_INTROSPECTION = "schema_introspection"
    TABLE_DISCOVERY = "table_discovery"
    COLUMN_DISCOVERY = "column_discovery"
    SQL_QUERY = "sql_query"
    DATA_COLLECTION = "data_collection"
    DATA_VALIDATION = "data_validation"
    REPORT_GENERATION = "report_generation"
    COORDINATION = "coordination"
    CUSTOM = "custom"


class TaskStatus(str, Enum):
    """Status of Oracle worker task execution."""

    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class TaskPriority(str, Enum):
    """Priority levels for Oracle worker tasks."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class OracleTaskParameters(TypedDict, total=False):
    """Oracle-specific task parameters."""

    tool_name: OracleToolName
    connection_name: str
    connection_string_env: str
    sql_statement: str
    table_name: str
    include_columns: bool
    refresh_schema_cache: bool
    timeout_ms: int
    read_only: bool
    bind_parameters: Dict[str, Any]


class Task(TypedDict):
    """Core Oracle worker task definition schema."""

    # Task identification
    task_id: str
    task_type: TaskType
    name: str
    description: str
    created_at: datetime
    estimated_duration_minutes: Optional[int]
    priority: TaskPriority
    dependencies: List[str]
    assigned_agent: Optional[str]
    required_capabilities: List[str]
    preferred_agents: List[str]

    # Task parameters
    parameters: OracleTaskParameters
    input_data: Dict[str, Any]
    expected_output: Dict[str, Any]

    # Constraints and requirements
    max_execution_time_minutes: int
    retry_policy: Dict[str, Any]
    read_only_required: bool

    # Metadata
    tags: List[str]
    metadata: Dict[str, Any]


class TaskExecution(TypedDict):
    """Oracle worker task execution tracking schema."""

    # Execution identification
    execution_id: str
    task_id: str
    agent_id: str
    started_at: datetime
    completed_at: Optional[datetime]
    duration_seconds: Optional[int]
    status: TaskStatus
    progress_percentage: float
    current_step: Optional[str]

    # Execution details
    current_tool: Optional[OracleToolName]
    execution_log: List[Dict[str, Any]]
    checkpoints: List[Dict[str, Any]]
    output_data: Dict[str, Any]
    error_details: Optional[Dict[str, Any]]
    warnings: List[str]
    performance_metrics: Dict[str, Union[int, float]]


class OracleQueryResult(TypedDict):
    """Result metadata for Oracle query tasks."""

    sql_statement: str
    row_count: int
    columns: List[str]
    truncated: bool
    timeout_ms: int


class OracleSchemaResult(TypedDict):
    """Result metadata for Oracle schema discovery tasks."""

    tables: List[str]
    columns_by_table: Dict[str, List[Dict[str, Any]]]
    refreshed_at: datetime
    source_schema: Optional[str]


class TaskResult(TypedDict):
    """Oracle worker task execution result schema."""

    result_id: str
    task_id: str
    execution_id: str
    success: bool
    output: Dict[str, Any]
    oracle_query: Optional[OracleQueryResult]
    oracle_schema: Optional[OracleSchemaResult]
    artifacts: List[Dict[str, Any]]
    confidence_score: Optional[float]
    quality_metrics: Dict[str, float]
    execution_time_seconds: int

    # Validation
    validated: bool
    validation_results: Dict[str, Any]

    # Errors
    error_occurred: bool
    error_message: Optional[str]
    error_code: Optional[str]
    generated_at: datetime
    metadata: Dict[str, Any]


class TaskTemplate(TypedDict):
    """Template for creating similar Oracle worker tasks."""

    template_id: str
    name: str
    description: str
    task_type: TaskType

    # Template parameters
    parameter_schema: Dict[str, Any]
    default_parameters: OracleTaskParameters

    # Requirements
    required_capabilities: List[str]
    required_tools: List[OracleToolName]
    resource_requirements: Dict[str, Any]

    # Configuration
    default_priority: TaskPriority
    estimated_duration_minutes: int
    retry_policy: Dict[str, Any]
    read_only_required: bool

    # Metadata
    created_by: str
    created_at: datetime
    version: str
    tags: List[str]


class TaskQueue(TypedDict):
    """Queue of Oracle worker tasks grouped by status."""

    pending: List[str]
    assigned: List[str]
    in_progress: List[str]
    completed: List[str]
    failed: List[str]
    cancelled: List[str]
    updated_at: datetime


class TaskAssignment(TypedDict):
    """Assignment record for routing a task to an Oracle worker agent."""

    task_id: str
    agent_id: str
    assigned_at: datetime
    status: Literal["assigned", "accepted", "rejected", "expired"]
    reason: Optional[str]
    metadata: Dict[str, Any]


__all__ = [
    "TaskType",
    "TaskStatus",
    "TaskPriority",
    "OracleTaskParameters",
    "Task",
    "TaskExecution",
    "OracleQueryResult",
    "OracleSchemaResult",
    "TaskResult",
    "TaskTemplate",
    "TaskQueue",
    "TaskAssignment",
]
