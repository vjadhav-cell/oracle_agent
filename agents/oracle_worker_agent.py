from __future__ import annotations

import logging
import sys
import traceback
from contextlib import nullcontext
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from agents.oracle_mcp_tools import OracleMCPClientManager
from agents.oracle_worker_prompts import get_oracle_worker_agent_prompt

try:
    from opentelemetry.trace import Status, StatusCode
except ImportError:  # pragma: no cover - optional instrumentation dependency
    Status = None
    StatusCode = None

try:
    from utils.telemetry import get_app_tracer, increment_error_counter

    tracer = get_app_tracer(__name__)
    TELEMETRY_AVAILABLE = True
except ImportError:  # pragma: no cover - optional instrumentation dependency
    tracer = None
    TELEMETRY_AVAILABLE = False


load_dotenv()

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

memory = MemorySaver()


def _set_span_ok(span: Any) -> None:
    if span and Status and StatusCode:
        span.set_status(Status(StatusCode.OK))


def _set_span_error(span: Any, exc: Exception | str) -> None:
    if not span or not Status or not StatusCode:
        return

    message = str(exc)
    if isinstance(exc, Exception):
        span.record_exception(exc)
    span.set_status(Status(StatusCode.ERROR, message))


def create_default_model() -> BaseChatModel:
    """Create a chat model using project-specific or common LangChain providers."""
    try:
        from shared_litellm import create_custom_litellm_model

        return create_custom_litellm_model()
    except ImportError:
        pass

    try:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model="gpt-4o-mini", temperature=0)
    except ImportError as exc:
        raise RuntimeError(
            "No default LLM model is available. Install/configure your shared_litellm "
            "module or install langchain-openai and set OPENAI_API_KEY. You can also "
            "pass a BaseChatModel instance to create_oracle_worker_agent_with_mcp(model=...)."
        ) from exc


class OracleWorkerAgent:
    """Standalone worker agent for Oracle read-only MCP operations."""

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        *,
        model: BaseChatModel | None = None,
        mcp_url: str | None = None,
    ):
        self.config = config or {"agent": {"name": "OracleWorkerAgent"}}
        self.name = self.config.get("agent", {}).get("name", "OracleWorkerAgent")
        self.model = model
        self.mcp_url = mcp_url
        self.tools = []
        self.graph = None
        logger.info("Initialized %s", self.name)

    async def app(self):
        span_ctx = tracer.start_as_current_span("oracle_worker.app") if tracer else nullcontext()
        with span_ctx as span:
            if self.graph is None:
                self.graph = await create_oracle_worker_agent_with_mcp(
                    model=self.model,
                    mcp_url=self.mcp_url,
                )

            _set_span_ok(span)
            return self.graph


async def create_oracle_worker_agent_with_mcp(
    *,
    model: BaseChatModel | None = None,
    mcp_url: str | None = None,
):
    """
    Create an Oracle worker ReAct agent using MCP-backed Oracle tools.

    The worker can use:
    - oracle_test_connection
    - oracle_get_tables
    - oracle_get_columns
    - oracle_get_schema
    - oracle_fetch_table
    - oracle_execute_sql
    - oracle_execute_sql_query_with_filters
    """
    span_ctx = (
        tracer.start_as_current_span("oracle_worker.create_with_mcp")
        if tracer
        else nullcontext()
    )

    with span_ctx as span:
        try:
            mcp_manager = OracleMCPClientManager(mcp_url=mcp_url)
            client, worker_tools, tools_description = await mcp_manager.create_mcp_client_with_tools()

            if not client:
                message = "Failed to initialize Oracle MCP client"
                logger.error(message)
                _set_span_error(span, message)
                return None

            if not worker_tools:
                message = "No Oracle MCP tools available"
                logger.error(message)
                _set_span_error(span, message)
                return None

            logger.info("Found %d Oracle tools", len(worker_tools))
            logger.info("Oracle tools description: %s", tools_description)

            if span:
                span.set_attribute("tools.count", len(worker_tools))

            tool_names = [getattr(tool, "name", "unknown") for tool in worker_tools]
            logger.info("Oracle tool names registered for agent: %s", tool_names)

            system_message = get_oracle_worker_agent_prompt(tools_description)
            safe_system_message = system_message.replace("{", "{{").replace("}", "}}")

            worker_prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", safe_system_message),
                    MessagesPlaceholder(variable_name="messages"),
                ]
            )

            llm = model or create_default_model()

            react_agent = create_react_agent(
                model=llm,
                tools=worker_tools,
                prompt=worker_prompt,
                name="oracle_worker_agent",
                checkpointer=memory,
            )

            _set_span_ok(span)
            return react_agent

        except Exception as exc:
            logger.error("Failed to create Oracle worker agent with MCP: %s", exc)
            traceback.print_exc()
            _set_span_error(span, exc)

            if TELEMETRY_AVAILABLE:
                increment_error_counter(
                    {
                        "error.type": type(exc).__name__,
                        "error.message": str(exc)[:100],
                        "error.source": "oracle_worker.create_oracle_worker_agent_with_mcp",
                    }
                )

            return None
