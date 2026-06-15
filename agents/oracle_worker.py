from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
from typing import Any, TypedDict

import httpx
from langgraph.graph import END, StateGraph


DEFAULT_MCP_URL = os.getenv("MCP_URL", "http://127.0.0.1:8000/mcp")
DEFAULT_TABLE_NAME = os.getenv("ORACLE_DEFAULT_TABLE", "MCP_DEMO_EMPLOYEES")

KNOWN_DESIGNATIONS = (
    "Backend Developer",
    "Business Analyst",
    "Data Engineer",
    "DevOps Engineer",
    "Frontend Developer",
    "Product Analyst",
    "Project Manager",
    "QA Engineer",
    "Software Engineer",
    "Support Engineer",
)


class OracleWorkerState(TypedDict):
    question: str
    mcp_url: str
    table_name: str
    tool_name: str | None
    tool_args: dict[str, Any]
    tool_result: Any
    answer: str


def _clean_question(question: str) -> str:
    return re.sub(r"\s+", " ", question).strip()


def _extract_int(pattern: str, text: str) -> int | None:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return None

    return int(match.group(1))


def _match_designation(question: str) -> str | None:
    question_lower = question.lower()

    for designation in KNOWN_DESIGNATIONS:
        if designation.lower() in question_lower:
            return designation

    return None


def _decode_mcp_response(response_text: str) -> dict[str, Any]:
    """Parse FastMCP JSON or text/event-stream responses into one JSON-RPC payload."""
    stripped = response_text.strip()

    if stripped.startswith("{"):
        return json.loads(stripped)

    last_payload: dict[str, Any] | None = None

    for line in response_text.splitlines():
        if not line.startswith("data:"):
            continue

        data = line.removeprefix("data:").strip()
        if not data or data == "[DONE]":
            continue

        last_payload = json.loads(data)

    if last_payload is None:
        raise ValueError(f"Could not parse MCP response: {response_text[:500]}")

    return last_payload


def _extract_tool_result(json_rpc_payload: dict[str, Any]) -> Any:
    if "error" in json_rpc_payload:
        return {"ok": False, "error": json_rpc_payload["error"]}

    result = json_rpc_payload.get("result", {})

    if isinstance(result, dict) and "structuredContent" in result:
        return result["structuredContent"]

    content = result.get("content") if isinstance(result, dict) else None
    if isinstance(content, list):
        for item in content:
            if item.get("type") != "text":
                continue

            text = item.get("text", "")
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return text

    return result


async def call_mcp_tool(
    mcp_url: str,
    tool_name: str,
    arguments: dict[str, Any],
) -> Any:
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments,
        },
    }

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            mcp_url,
            headers={
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()

    return _extract_tool_result(_decode_mcp_response(response.text))


async def choose_tool(state: OracleWorkerState) -> OracleWorkerState:
    question = _clean_question(state["question"])
    question_lower = question.lower()
    table_name = state["table_name"]
    limit = _extract_int(r"\blimit\s+(\d+)\b", question_lower) or 10

    if "tables" in question_lower or "list tables" in question_lower:
        state["tool_name"] = "oracle.getTables"
        state["tool_args"] = {"include_views": True, "limit": max(limit, 20)}
        return state

    if "schema" in question_lower:
        state["tool_name"] = "oracle.getSchema"
        state["tool_args"] = {"include_views": True, "table_limit": max(limit, 20)}
        return state

    if "columns" in question_lower or "column" in question_lower:
        state["tool_name"] = "oracle.getColumns"
        state["tool_args"] = {"table_name": table_name}
        return state

    if "count" in question_lower or "how many" in question_lower:
        state["tool_name"] = "oracle.executeSQL"
        state["tool_args"] = {
            "sql_statement": f"SELECT COUNT(*) AS TOTAL_ROWS FROM {table_name}",
            "limit": 1,
        }
        return state

    employee_id = _extract_int(r"\bemployee(?:_id| id)?\s+(\d+)\b", question_lower)
    if employee_id is not None:
        state["tool_name"] = "oracle.executeSQLQueryWithFilters"
        state["tool_args"] = {
            "sql_statement": f"SELECT * FROM {table_name}",
            "filters": {"EMPLOYEE_ID": employee_id},
            "limit": limit,
            "offset": 0,
        }
        return state

    designation = _match_designation(question)
    if designation:
        state["tool_name"] = "oracle.executeSQLQueryWithFilters"
        state["tool_args"] = {
            "sql_statement": f"SELECT * FROM {table_name}",
            "filters": {"DESIGNATION": designation},
            "order_by": ["EMPLOYEE_ID ASC"],
            "limit": limit,
            "offset": 0,
        }
        return state

    state["tool_name"] = "oracle.fetchTable"
    state["tool_args"] = {
        "table_name": table_name,
        "limit": limit,
        "offset": 0,
    }
    return state


async def execute_tool(state: OracleWorkerState) -> OracleWorkerState:
    tool_name = state["tool_name"]
    if not tool_name:
        state["tool_result"] = {"ok": False, "error": "No tool selected"}
        return state

    state["tool_result"] = await call_mcp_tool(
        state["mcp_url"],
        tool_name,
        state["tool_args"],
    )
    return state


async def format_answer(state: OracleWorkerState) -> OracleWorkerState:
    tool_name = state["tool_name"]
    tool_args = json.dumps(state["tool_args"], indent=2, sort_keys=True)
    tool_result = json.dumps(state["tool_result"], indent=2, default=str)

    state["answer"] = (
        f"Question: {state['question']}\n\n"
        f"Selected tool: {tool_name}\n\n"
        f"Tool arguments:\n{tool_args}\n\n"
        f"Tool result:\n{tool_result}"
    )
    return state


def build_oracle_worker():
    graph = StateGraph(OracleWorkerState)

    graph.add_node("choose_tool", choose_tool)
    graph.add_node("execute_tool", execute_tool)
    graph.add_node("format_answer", format_answer)

    graph.set_entry_point("choose_tool")
    graph.add_edge("choose_tool", "execute_tool")
    graph.add_edge("execute_tool", "format_answer")
    graph.add_edge("format_answer", END)

    return graph.compile()


async def run_question(
    question: str,
    *,
    mcp_url: str = DEFAULT_MCP_URL,
    table_name: str = DEFAULT_TABLE_NAME,
) -> OracleWorkerState:
    worker = build_oracle_worker()
    return await worker.ainvoke(
        {
            "question": question,
            "mcp_url": mcp_url,
            "table_name": table_name,
            "tool_name": None,
            "tool_args": {},
            "tool_result": None,
            "answer": "",
        }
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the LangGraph Oracle MCP worker.")
    parser.add_argument("question", help="Question or instruction for the Oracle worker")
    parser.add_argument(
        "--mcp-url",
        default=DEFAULT_MCP_URL,
        help=f"MCP endpoint URL. Default: {DEFAULT_MCP_URL}",
    )
    parser.add_argument(
        "--table",
        default=DEFAULT_TABLE_NAME,
        help=f"Default Oracle table. Default: {DEFAULT_TABLE_NAME}",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    result = await run_question(args.question, mcp_url=args.mcp_url, table_name=args.table)
    print(result["answer"])


if __name__ == "__main__":
    asyncio.run(main())
