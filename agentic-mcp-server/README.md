# Agentic Oracle MCP Server

This repository contains a Python MCP server that exposes Oracle database tools to
MCP-compatible clients such as Cursor.

## Tools

- `oracle_test_connection` - verifies credentials and returns basic database context.
- `oracle_query` - runs read-only `SELECT` or `WITH` SQL and returns JSON-safe rows.
- `oracle_list_tables` - lists visible Oracle tables.
- `oracle_describe_table` - returns column metadata for a table.
- `oracle_sample_table` - fetches sample rows from a validated table name.
- `oracle_execute_sql` - runs SQL. Non-read-only statements require
  `ORACLE_ALLOW_DML=true`; otherwise the server rejects them.

## Configuration

Set these environment variables in your MCP client configuration:

| Variable | Required | Description |
| --- | --- | --- |
| `ORACLE_USER` or `ORACLE_USERNAME` | Yes | Oracle database username. |
| `ORACLE_PASSWORD` | Yes | Oracle database password. |
| `ORACLE_DSN` | Yes | Oracle DSN, for example `host:1521/service_name`. |
| `ORACLE_CONFIG_DIR` or `TNS_ADMIN` | No | Directory containing `tnsnames.ora` or wallet config. |
| `ORACLE_WALLET_LOCATION` | No | Wallet directory for mTLS or Autonomous DB connections. |
| `ORACLE_WALLET_PASSWORD` | No | Wallet password, if your wallet requires one. |
| `ORACLE_THICK_MODE` | No | Set to `true` to initialize Oracle Instant Client thick mode. |
| `ORACLE_CLIENT_LIB_DIR` | No | Instant Client library path for thick mode. |
| `ORACLE_FETCH_LIMIT` | No | Default max rows returned by fetch tools. Defaults to `100`. |
| `ORACLE_CALL_TIMEOUT_MS` | No | Per-call timeout in milliseconds. Defaults to `30000`. |
| `ORACLE_POOL_MIN` | No | Minimum connection pool size. Defaults to `1`. |
| `ORACLE_POOL_MAX` | No | Maximum connection pool size. Defaults to `4`. |
| `ORACLE_POOL_INCREMENT` | No | Connection pool increment. Defaults to `1`. |
| `ORACLE_ALLOW_DML` | No | Set to `true` to allow non-read-only SQL via `oracle_execute_sql`. |

The server uses python-oracledb thin mode by default, which does not require
Oracle Instant Client for many common connections.

## Run locally

```bash
cd agentic-mcp-server
python -m venv .venv
. .venv/bin/activate
python -m pip install -e .

export ORACLE_USER='your_user'
export ORACLE_PASSWORD='your_password'
export ORACLE_DSN='db-host.example.com:1521/ORCLPDB1'

agentic-oracle-mcp
```

The server communicates over stdio, as expected by MCP clients.

## Cursor MCP configuration example

Use the absolute path to this repository on your machine:

```json
{
  "mcpServers": {
    "oracle": {
      "command": "python",
      "args": ["-m", "agentic_oracle_mcp"],
      "cwd": "/absolute/path/to/agentic-mcp-server",
      "env": {
        "ORACLE_USER": "your_user",
        "ORACLE_PASSWORD": "your_password",
        "ORACLE_DSN": "db-host.example.com:1521/ORCLPDB1",
        "ORACLE_FETCH_LIMIT": "100"
      }
    }
  }
}
```

If your client does not support `cwd`, use the console script from an installed
environment instead:

```json
{
  "mcpServers": {
    "oracle": {
      "command": "/absolute/path/to/agentic-mcp-server/.venv/bin/agentic-oracle-mcp",
      "env": {
        "ORACLE_USER": "your_user",
        "ORACLE_PASSWORD": "your_password",
        "ORACLE_DSN": "db-host.example.com:1521/ORCLPDB1"
      }
    }
  }
}
```

## Development

```bash
cd agentic-mcp-server
python -m pip install -e '.[dev]'
pytest
```
