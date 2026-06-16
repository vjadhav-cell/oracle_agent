# AGENTS.md

## Cursor Cloud specific instructions

### What this is
A single Python product: a **Unified MCP (Model Context Protocol) server** (`unified-mcp-server`) built on FastMCP + Uvicorn. Entry point is `python main.py`, which serves streamable HTTP MCP at `http://0.0.0.0:8080/mcp`. Provider integrations (GCP, Grafana, Prometheus, Mimir, Tempo, OpenSearch, Jira, Slack, Kubernetes, Oracle) are enabled lazily from env vars; with no provider creds, the server still boots and exposes `test.echo`, `resource://manifest`, and `resource://health/{action}`.

### Non-obvious setup caveats (important)
- **Sourceless modules**: Only `oracle` modules ship as `.py` source. The other adapters/schemas/tool_specs (`gcp`, `grafana`, `jira`, `k8s`, `mimir`, `opensearch`, `prometheus`, `slack`, `tempo`, plus `schemas/base`, `schemas/__init__`, `tool_specs/k8s`, `tool_specs/metadata`) are committed only as compiled bytecode under each package's `__pycache__/*.cpython-312.pyc`. Python cannot import those from `__pycache__` directly, so they must be materialized to importable `<pkg>/<name>.pyc` (sourceless import). The startup/update script does this automatically. This requires **CPython 3.12** (the bytecode magic is 3.12-specific); do not switch Python versions.
- **`.env` is required and is not tracked.** The app reads `.env` via python-dotenv. `MCP_API_KEY` has no default (the app raises on import without it) and `OracleAdapter` is constructed at import time, so `DB_CONNECTION_STRING` must also be present (engine creation is lazy, so no live Oracle DB is needed to boot). If `.env` is missing, recreate it with:
  ```
  MCP_API_KEY=dev-mcp-key
  HOST=0.0.0.0
  PORT=8080
  DB_CONNECTION_STRING=oracle+oracledb://user:pass@localhost:1521/?service_name=XEPDB1
  ```
- `venv/` is (unusually) committed to the repo and was created on a different machine. The startup/update script re-runs `python3 -m venv venv`, which repairs the shebangs/`pyvenv.cfg`, then reinstalls deps. Always use `source venv/bin/activate` (or `venv/bin/python`).

### Running the server
- Activate venv and run `python main.py` (serves on port 8080, path `/mcp`). Prefer a long-lived tmux session.
- Redis is **optional** (rate limiting + idempotency). It is installed in the image but not auto-started. Start it with `redis-server --daemonize yes` (listens on 6379) before launching the server if you want the rate limiter active; otherwise the server logs a warning and continues (fail-open). Idempotency stays disabled unless `IDEMPOTENCY_TTL>0`.

### Testing / hello-world
- This is a headless backend (no GUI). Exercise it as an MCP client over HTTP. Minimal smoke test using the installed `fastmcp` client: connect to `http://127.0.0.1:8080/mcp`, `list_tools()`, call `test.echo` with `{"params": {"message": "..."}}`, and `read_resource("resource://manifest")` / `read_resource("resource://health/check")`.
- Known broken: `test_schemas.py` imports `schemas.oracle_adapter_schemas`, a module that is not present in the repo (no source and no bytecode), so `python test_schemas.py` fails at import. This is a pre-existing repo defect, not an environment issue.
- There is no configured linter (no ruff/flake8/black config and no `.pre-commit-config.yaml`), even though `pre-commit` is listed in `requirements.txt`. There is no lint step to run.
