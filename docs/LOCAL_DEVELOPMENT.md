# Local development guide — yarn-worker

This document explains what to install locally, how to connect your **existing LiteLLM proxy** and **YARN MCP server**, and how to run and test the **yarn_worker** LangGraph microservice.

## What you are running

| Layer | Purpose |
|-------|---------|
| **LangGraph agent** (`yarn_worker`) | ReAct loop: LLM decides when to call MCP tools and formats the final answer |
| **MCP server** (external) | Exposes `yarn.getApplicationLogsByName`, `yarn.getAppAttempts`, `yarn.tailContainerLogs` |
| **LiteLLM proxy** (you already have this) | OpenAI-compatible API for the agent chat model |

The agent repo contains **no embedded YARN tools** — all YARN I/O goes through the MCP server. `AgentFactory` (from **agent-util**) loads tools from `MCP_HOST`/`MCP_PORT` filtered by the tags declared in [`config/agent_config.py`](./config/agent_config.py).

Each worker type is deployed as its **own microservice** with its own graph / `assistant_id`. This repo is the **yarn_worker** deployment; API calls use `assistant_id: "yarn_worker"` (see [`langgraph.json`](./langgraph.json)).

---

## Project layout

This repo uses a **shared worker template** plus **yarn-specific configuration**:

| File | Role |
|------|------|
| [`config/agent_config.py`](./config/agent_config.py) | **Yarn worker config** — `mcp_tags` and system prompt (`build_system_prompt`) |
| [`agents/worker.py`](./agents/worker.py) | **Common factory** — `create_worker_agent()`, LiteLLM model, `AgentFactory` wiring |
| [`agents/graph.py`](./agents/graph.py) | LangGraph CLI entrypoint (`make_graph`) |
| [`config/settings.py`](./config/settings.py) | Runtime settings from `.env` (LiteLLM, `STREAMING_APP_INSTANCE_LIMIT`, etc.) |
| [`langgraph.json`](./langgraph.json) | Registers graph id `yarn_worker` |

```mermaid
flowchart LR
    agent_config["agent_config.py\nmcp_tags + prompt"]
    worker["worker.py\ncreate_worker_agent"]
    graph["graph.py\nmake_graph"]
    langgraph["langgraph.json\nyarn_worker"]
    agent_config --> worker --> graph --> langgraph
```

To customize this deployment, edit **`config/agent_config.py`**:

- **`mcp_tags`** — MCP tool tags passed to `AgentFactory` (here: `["yarn_streaming"]`)
- **Prompt constants** + **`build_system_prompt()`** — system prompt assembled for the agent

`get_worker_name()` in [`config/agent_config.py`](../config/agent_config.py) sets the graph name and LangGraph `assistant_id` for this microservice. Other worker repos keep the same factory code and change `agent_config.py` plus `langgraph.json` for their own service id.

---

## Prerequisites

| Requirement | Version / notes |
|-------------|-----------------|
| **Python** | **3.11+** (see `langgraph.json`) |
| **LiteLLM proxy** | Already running locally (default port **4000**) |
| **YARN MCP server** | Running at `MCP_HOST`:`MCP_PORT` (default `127.0.0.1:8080`); must reach YARN RM/NM |
| **Network** | MCP server must reach RM Web Services + NodeManager log URLs |

Optional:

- **Docker** — only for `langgraph up` (production-like stack with Postgres/Redis), not for day-to-day dev
- **LangSmith** — optional tracing; set `LANGSMITH_API_KEY` if you use LangGraph Cloud features

You do **not** need a separate Ollama install in this repo if Ollama is already wired **behind** your LiteLLM proxy (common setup: model alias `gemma4` → Ollama).

---

## 1. Install project dependencies

From the repo root:

```bash
python3.11 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
```

What `requirements.txt` pulls in:

- **langgraph-cli[inmem]** — `langgraph dev` (in-memory Agent Server, hot reload)
- **langgraph / langchain** — agent graph and chat model
- **agent-util** — `AgentFactory` (MCP tool discovery by tag) and `CustomLiteLLMModel` HTTP client
- **pydantic, pydantic-settings, python-dotenv** — config
- **pytest, pytest-asyncio** — unit tests

Verify the CLI:

```bash
langgraph --version
```

---

## 2. Configure environment (`.env`)

```bash
cp .env.example .env
```

Edit `.env` for your environment.

### MCP server

| Variable | Example | Notes |
|----------|---------|--------|
| `MCP_HOST` | `127.0.0.1` | YARN MCP server host (read by agent-util `AgentFactory`) |
| `MCP_PORT` | `8080` | YARN MCP server port |

Start the MCP server **before** `langgraph dev`. See [plan/mcp_yarn_tools_spec.md](./plan/mcp_yarn_tools_spec.md) for server implementation.

### Agent prompt tuning

| Variable | Example | Notes |
|----------|---------|--------|
| `STREAMING_APP_INSTANCE_LIMIT` | `3` | Passed into `build_system_prompt()` in `agent_config.py` |

Workflow, rules, and output format are defined in code in [`config/agent_config.py`](./config/agent_config.py), not in `.env`.

### LiteLLM proxy (use your existing instance)

| Variable | Example | Notes |
|----------|---------|--------|
| `LITELLM_API_BASE` or `LITELLM_SERVER_URL` | `http://127.0.0.1:4000` | Proxy base URL; `/v1` suffix is optional |
| `LITELLM_API_KEY` | `sk-...` | Must match what your proxy expects |
| `LITELLM_MODEL` or `DEFAULT_MODEL` | `gemma4` | Must match the **model alias** in LiteLLM `config.yaml` |
| `AGENT_TEMPERATURE` | `0` | Chat temperature for the worker loop |

Health check:

```bash
curl -s "${LITELLM_API_BASE%/}/health"
```

Chat smoke test (replace model and key):

```bash
curl -s "${LITELLM_API_BASE%/}/v1/chat/completions" \
  -H "Authorization: Bearer ${LITELLM_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"model":"gemma4","messages":[{"role":"user","content":"ping"}]}'
```

---

## 3. LiteLLM + Ollama (if you use Gemma via Ollama)

If LiteLLM is already configured for YARN/GCP workers, align **`.env`** with that config:

1. **`LITELLM_MODEL`** = the `model_name` entry in LiteLLM (e.g. `gemma4`).
2. **`LITELLM_API_BASE`** = where the proxy listens (e.g. `http://127.0.0.1:4000`).

The worker never talks to Ollama directly; it only talks to the proxy.

**Tool calling:** The agent uses `CustomLiteLLMModel` from **agent-util** `shared_litellm`. The model alias must support tool/function calling. If the model ignores tool calls, the agent will not invoke MCP tools — try a tool-capable alias.

---

## 4. Run the agent locally

### Start MCP server first

Ensure the YARN MCP server is running at `MCP_HOST`:`MCP_PORT` before starting LangGraph.

### Development server (recommended)

```bash
source .venv/bin/activate
langgraph dev
```

- API: **<http://127.0.0.1:2024>**
- OpenAPI: **<http://127.0.0.1:2024/docs>**
- Terminal prints a **LangGraph Studio** URL for interactive chat
- Loads graph `yarn_worker` from `langgraph.json` via async `make_graph` (connects to MCP at startup using `mcp_tags` from `agent_config.py`)

### Production-like local (optional)

Requires Docker and `LANGSMITH_API_KEY` in `.env`:

```bash
langgraph up
```

Exposes **<http://127.0.0.1:8123>** with Postgres/Redis.

---

## 5. How to test

### A. Unit tests (no MCP, no live LLM)

```bash
source .venv/bin/activate
pytest tests/ -q
```

Covers agent graph compilation (mocked MCP via `AgentFactory`), `mcp_tags` wiring from `agent_config.py`, and `CustomLiteLLMModel` configuration.

### B. LiteLLM only

```bash
source .venv/bin/activate
python -c "
from config.settings import get_settings
from shared_litellm import CustomLiteLLMModel

s = get_settings()
m = CustomLiteLLMModel(
    model=s.litellm_model,
    base_url=s.litellm_api_base,
    api_key=s.litellm_api_key,
    temperature=s.agent_temperature,
)
print('model:', m.model, 'base:', m.base_url, 'type:', m._llm_type)
"
```

### C. End-to-end via API (MCP + LiteLLM + agent)

With MCP server and `langgraph dev` running:

```bash
curl -s http://127.0.0.1:2024/runs/stream \
  -H "Content-Type: application/json" \
  -d '{
    "assistant_id": "yarn_worker",
    "input": {
      "messages": [{
        "role": "human",
        "content": "Get logs for streaming app my-streaming-app and summarize failures"
      }]
    },
    "stream_mode": "values"
  }'
```

Replace `my-streaming-app` with a real `applicationName` from your cluster.

In the streamed JSON, look for:

- `ToolMessage` entries for `yarn.getApplicationLogsByName`, `yarn.getAppAttempts`, `yarn.tailContainerLogs`
- Final assistant message with RCA-style narrative

### D. LangGraph Studio

After `langgraph dev`, open the Studio link from the terminal and send the same kind of prompt. Easiest way to inspect tool calls and messages.

---

## 6. MCP tool contract

Tools are discovered by the `yarn_streaming` tag (`mcp_tags` in `agent_config.py`):

| Tool | Purpose |
|------|---------|
| `yarn.getApplicationLogsByName` | Find instances by `applicationName`, fetch AM logs |
| `yarn.getAppAttempts` | Get restart attempts and `logsLink` for an `applicationId` |
| `yarn.tailContainerLogs` | Tail container log file from NodeManager |

See [plan/mcp_yarn_tools_spec.md](./plan/mcp_yarn_tools_spec.md) for full input/output schemas.

---

## 7. Troubleshooting

| Symptom | Likely cause | What to do |
|---------|----------------|------------|
| `langgraph: command not found` | venv not active or deps not installed | `source .venv/bin/activate && pip install -r requirements.txt` |
| MCP connection failed at startup | MCP server not running | Start MCP server at `MCP_HOST`:`MCP_PORT` before `langgraph dev` |
| No tools matched `yarn_streaming` tag | Wrong MCP server or missing tool metadata | Verify MCP tools declare the `yarn_streaming` FastMCP tag; check `mcp_tags` in `agent_config.py` |
| Proxy 401/403 | Wrong `LITELLM_API_KEY` | Match proxy master key / virtual key |
| Model not found | Alias mismatch | Set `LITELLM_MODEL` to LiteLLM `model_name`; restart proxy |
| Agent answers without calling tools | Model without tool support | Use a tool-capable alias on LiteLLM |
| Empty tool results | YARN connectivity from MCP server | Fix RM/NM reachability from MCP server host, not agent |
| Wrong graph / 404 on invoke | `assistant_id` mismatch | Use `"yarn_worker"` for this repo (see `langgraph.json` and `get_worker_name()`) |

---

## 8. Minimal checklist

- [ ] Python 3.11 venv + `pip install -r requirements.txt`
- [ ] `.env` copied from `.env.example` and filled in
- [ ] YARN MCP server running at `MCP_HOST`:`MCP_PORT`
- [ ] LiteLLM proxy up; `curl .../health` OK
- [ ] `LITELLM_MODEL` matches proxy alias; chat completion smoke test OK
- [ ] `langgraph dev` starts; Studio or curl stream returns tool calls + summary
- [ ] `pytest tests/ -q` passes

For a shorter overview, see [README.md](./README.md).

For MCP server implementation and YARN cluster setup, see **[plan/mcp_yarn_tools_spec.md](./plan/mcp_yarn_tools_spec.md)** and **[YARN_INSTALL.md](./YARN_INSTALL.md)**.
