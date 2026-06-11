import pytest

import agentic_oracle_mcp.server as server


class FakeClient:
    def query(self, sql, parameters=None, fetch_limit=None):
        return {
            "columns": ["X"],
            "rows": [{"X": 1}],
            "row_count": 1,
            "truncated": False,
        }


@pytest.mark.anyio
async def test_mcp_tool_dispatch_calls_oracle_query(monkeypatch) -> None:
    monkeypatch.setattr(server, "_client", FakeClient())

    content, structured = await server.mcp.call_tool(
        "oracle_query",
        {"sql": "select 1 as x from dual"},
    )

    assert structured["rows"] == [{"X": 1}]
    assert '"X": 1' in content[0].text
