# AGENTS.md

## Cursor Cloud specific instructions

This repo is the **Unified MCP Server** (`main.py`), a FastMCP-based HTTP server exposing
infrastructure/observability tools (Oracle, GCP, Grafana, OpenSearch, Mimir, Prometheus, K8s, etc.).
See `README.md` for the full tool catalog and API reference.

### Non-obvious repo facts (important)

- **Sourceless modules**: Most adapter/schema modules (`adapters/gcp`, `adapters/k8s`, `schemas/base`,
  `tool_specs/metadata`, …) are committed **only as compiled bytecode** under `*/__pycache__/*.cpython-312.pyc`;
  their `.py` sources are not in the repo. Only `adapters/oracle.py`, `schemas/oracle.py`, `schemas/utils.py`,
  the `utils/*` package, `main.py`, and `manifest.py` exist as source. `main.py` imports the bytecode-only modules,
  so the app cannot import until those `.pyc` files are materialized next to their packages
  (e.g. `schemas/__pycache__/base.cpython-312.pyc` → `schemas/base.pyc`). The update script does this automatically.
  This is tied to **CPython 3.12** — the bytecode will not load on other Python versions.
- **Python**: requires 3.12 (system `python3` is 3.12). The base VM image ships without `python3.12-venv`/`pip`;
  those are installed at the system level and captured in the VM snapshot (do not put system installs in the update script).

### Running the server (dev)

A `.env` is required or `main.py` will fail at import (`MCP_API_KEY` is required, and the Oracle adapter is
instantiated at module load, so `DB_CONNECTION_STRING` must be set even though no DB connection is made at boot).
Create `.env` in the repo root if missing:

```
MCP_API_KEY=dev-mcp-key
DB_CONNECTION_STRING=oracle+oracledb://demo:demo@localhost:1521/FREEPDB1
```

Then run:

```
venv/bin/python main.py
```

The server starts on `http://0.0.0.0:8080/mcp` (FastMCP **streamable HTTP**, stateless). It is an MCP endpoint,
**not** the plain REST paths shown in `README.md` — connect with an MCP client (e.g. `fastmcp.Client("http://127.0.0.1:8080/mcp")`),
call the `test.echo` tool, or read the `resource://manifest` resource. Bearer auth is disabled in stateless mode.

Provider tools (Jira/Slack/Grafana/OpenSearch/Mimir/Prometheus) only register when their credentials are set in `.env`;
K8s tools only register when `K8S_ENABLED=true`. Redis is optional (rate limiting fails open if absent).

### Tests / lint

- `venv/bin/python test_schemas.py` currently fails on import: it references `schemas.oracle_adapter_schemas`,
  which does not exist in the repo (the module is `schemas.oracle`). This is a pre-existing code bug, not an env issue.
- No lint configuration (ruff/flake8/pre-commit config) is committed, despite `pre-commit` being in `requirements.txt`.
