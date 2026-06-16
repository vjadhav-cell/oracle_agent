# AGENTS.md

## Cursor Cloud specific instructions

### What this is
A unified **FastMCP** server (`main.py`). It serves the **MCP protocol over streamable HTTP** at
`http://0.0.0.0:8080/mcp` — it is **not** a plain REST API, so the `/tools/...` and `/resources/...`
cURL examples in `README.md` do not work directly; connect with an MCP client instead. Tools (e.g.
`test.echo`, `gcp.*`) are registered with `@mcp.tool`, and `resource://manifest` /
`resource://health/check` are MCP resources.

### Non-obvious gotchas
- **Most source files are missing from the repo.** Only the Oracle adapter/schema and `utils/*` ship
  as `.py`. The other modules (`adapters/{gcp,grafana,jira,k8s,mimir,opensearch,prometheus,slack,tempo}`,
  `schemas/{base,gcp,grafana,jira,k8s,mimir,opensearch,prometheus,slack,tempo}`, `tool_specs/{k8s,metadata}`)
  exist **only as compiled bytecode** in `__pycache__`. Sourceless `.pyc` copies are committed directly
  in the package directories (e.g. `adapters/gcp.pyc`) so imports resolve under Python 3.12. **Do not
  delete these `.pyc` files** — without them `import main` fails with `ModuleNotFoundError`. They are
  pinned to CPython 3.12 bytecode; a different Python minor version will not load them.
- **Startup requires env vars.** `OracleAdapter()` is instantiated at import time and needs
  `DB_CONNECTION_STRING`; `MCP_API_KEY` is also required by settings. The SQLAlchemy engine is created
  lazily, so **no live Oracle DB is needed just to start** — a dummy URL like
  `oracle+oracledb://dev:dev@localhost:1521/FREEPDB1` is enough to boot and serve `test.echo`/manifest.
- **`.env` is not committed.** Create one (see `README.md` → Configuration). A minimal dev `.env`:
  `MCP_API_KEY=dev-mcp-key`, `DB_CONNECTION_STRING=oracle+oracledb://dev:dev@localhost:1521/FREEPDB1`.
- **The committed `venv/` is from another machine** (broken shebangs pointing at `/home/vinj/...`). The
  startup update script recreates it fresh; don't rely on the committed one.
- **Redis is optional.** Rate limiting and idempotency fail open, so the server runs fine without Redis
  (health reports `redis: unavailable`). To enable it locally: `docker compose up -d redis` (or run Redis
  on `localhost:6379`).
- **Kubernetes tools** are only registered when `K8S_ENABLED=true`.

### Run / test / lint
- Run server (dev): `venv/bin/python main.py` (serves on `:8080/mcp`).
- Hello-world check: with the server running, connect a FastMCP client and call `test.echo` /
  read `resource://manifest` (see the demo script used during setup).
- Tests: the only test, `test_schemas.py`, is **currently broken** — it imports
  `schemas.oracle_adapter_schemas`, which does not exist (the real module is `schemas.oracle`). This is a
  pre-existing code bug, not an environment problem. The underlying schemas import and validate correctly
  from `schemas.oracle`.
- Lint: no linter/formatter or pre-commit config is present. The closest available check is
  `venv/bin/python -m py_compile <files>`.
