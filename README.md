# Oracle MCP Server

A Model Context Protocol (MCP) server that exposes safe, read-oriented Oracle database tools for connection testing, schema discovery, table metadata, table row fetching, and read-only SQL execution.

## Features

- **Oracle Database Support**: Fetch data from Oracle tables through MCP tools
- **HTTP/REST API**: Stateless HTTP transport for easy integration
- **Rate Limiting**: Built-in Redis-based rate limiting (optional)
- **Idempotency**: Request idempotency support via Redis (optional)
- **Health Checks**: Comprehensive health check endpoints
- **Tool Discovery**: Manifest endpoint to discover all available tools
- **Read-Only Guardrails**: Allows only table fetches and read-only `SELECT`/`WITH` SQL

## Table of Contents

- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Server](#running-the-server)
- [API Documentation](#api-documentation)
- [Sample cURL Commands](#sample-curl-commands)
- [Docker Deployment](#docker-deployment)

## Installation

### Prerequisites

- Python 3.12+
- Redis (optional, for rate limiting and idempotency)
- Kubernetes cluster access (if using K8s tools)
- Credentials for the services you want to use

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd agentic-mcp-server
```

2. Create a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file (see [Configuration](#configuration) section)

## Configuration

Create a `.env` file in the project root with the following variables:

### Required

```env
MCP_API_KEY=your-api-key-here
```

### Server Configuration

```env
MCP_TRANSPORT=http
HOST=0.0.0.0
PORT=8080
```

### Redis (Optional)

```env
REDIS_URL=redis://localhost:6379/0
IDEMPOTENCY_TTL=3600  # TTL in seconds (0 to disable)
RATE_LIMIT_CAPACITY=120
RATE_LIMIT_REFILL_SECONDS=60
RATE_LIMIT_FAIL_OPEN=true
```

### Provider Credentials

#### Oracle
```env
ORACLE_ENABLED=true
DB_CONNECTION_STRING=oracle+oracledb://user:password@host:1521/?service_name=ORCLPDB1
QUERY_LIMIT_SIZE=50

# Optional comma-separated access controls.
# TABLE_WHITE_LIST can contain TABLE_NAME or OWNER.TABLE_NAME entries.
TABLE_WHITE_LIST=EMPLOYEES,HR.DEPARTMENTS

# COLUMN_WHITE_LIST can contain COLUMN_NAME or OWNER.TABLE_NAME.COLUMN_NAME entries.
COLUMN_WHITE_LIST=EMPLOYEE_ID,FIRST_NAME,LAST_NAME,HR.DEPARTMENTS.DEPARTMENT_NAME

# Optional SQLAlchemy pool settings.
ORACLE_POOL_SIZE=5
ORACLE_MAX_OVERFLOW=10
ORACLE_POOL_RECYCLE=3600
```

The server uses the `oracledb` Python driver in thin mode by default. If your environment requires Oracle Instant Client / thick mode, add the Instant Client libraries to the container image and configure the driver before creating connections.

#### Jira
```env
JIRA_BASE=https://your-org.atlassian.net
JIRA_EMAIL=your-email@example.com
JIRA_API_TOKEN=your-jira-api-token
```

#### Slack
```env
SLACK_BOT_TOKEN=xoxb-your-slack-bot-token
```

#### GCP
```env
# Option 1: Service Account JSON (as string)
GCP_SA_JSON={"type": "service_account", "project_id": "...", ...}

# Option 2: Use Application Default Credentials (ADC)
# Run: gcloud auth application-default login
```

#### Grafana
```env
GRAFANA_BASE_URL=https://your-grafana.com
# Option 1: API Key
GRAFANA_API_KEY=your-api-key

# Option 2: Username/Password
GRAFANA_USERNAME=admin
GRAFANA_PASSWORD=your-password
```

#### OpenSearch
```env
OPENSEARCH_URL=https://your-opensearch.com
OPENSEARCH_USERNAME=admin
OPENSEARCH_PASSWORD=your-password
OPENSEARCH_VERIFY_SSL=false
```

#### Mimir
```env
MIMIR_URL=https://your-mimir.com
MIMIR_USERNAME=admin
MIMIR_PASSWORD=your-password
MIMIR_TENANT_ID=your-tenant-id
MIMIR_DISABLE_SSL=false
MIMIR_TIMEOUT=30
```

#### Prometheus
```env
PROMETHEUS_ENDPOINT=https://your-prometheus.com
PROMETHEUS_USERNAME=admin
PROMETHEUS_PASSWORD=your-password
```

#### Kubernetes
```env
K8S_ENABLED=true
K8S_KUBECONFIG=/path/to/kubeconfig  # Optional, defaults to ~/.kube/config
K8S_CONTEXT=my-context  # Optional, uses current-context if not set
K8S_NAMESPACE=default  # Optional default namespace
K8S_VERIFY_SSL=true
K8S_TIMEOUT=30
```

**Note:** The metrics tools (`k8s.getPodMetrics`, `k8s.getNodeMetrics`) require the Kubernetes metrics-server to be installed in the cluster. This is cluster infrastructure configuration, not application configuration. The MCP server/adapter needs kubeconfig or service account credentials configured at the MCP server level (via environment variables above).

### Advanced Configuration

```env
HEALTHCHECK_FULL=false  # Enable full health checks (tests actual connections)
RETRY_MAX_ATTEMPTS=3
RETRY_MULTIPLIER=0.5
RETRY_MAX_WAIT=4
```

## Running the Server

### Local Development

```bash
# Activate virtual environment
source venv/bin/activate

# Run the server
python main.py
```

The server will start on `http://0.0.0.0:8080` by default.

### Using Docker

```bash
# Build the image (from inside agentic-mcp-server directory)
docker build -t unified-mcp-server .

# Or from repository root
docker build -t unified-mcp-server -f Dockerfile agentic-mcp-server/.

# Run with docker-compose (includes Redis)
docker-compose up
```

### Production Deployment

```bash
# Using docker-compose.prod.yml
docker-compose -f docker-compose.prod.yml up -d
```

## API Documentation

### Base URL

All endpoints are relative to the server base URL (default: `http://localhost:8080`).

### Authentication

All tool endpoints require Bearer token authentication:

```
Authorization: Bearer <MCP_API_KEY>
```

### Endpoints

#### 1. Manifest (Tool Discovery)

Get a list of all available tools and their endpoints.

**Endpoint:** `GET /resources/manifest`

**Response:**
```json
{
  "name": "unified-mcp-server",
  "version": "1.0.0",
  "description": "Unified MCP server; discover available tools and their HTTP endpoints.",
  "auth": {
    "type": "bearer",
    "header": "Authorization",
    "description": "Send 'Authorization: Bearer <MCP_API_KEY>'"
  },
  "tools": {
    "test.echo": {
      "name": "test.echo",
      "description": "Simple test tool to verify MCP server functionality",
      "http": {
        "path": "/tools/test/echo",
        "method": "POST"
      },
      "inputs": {
        "message": "string (optional) — message to echo back"
      }
    },
    ...
  }
}
```

#### 2. Health Check

Check server health and provider status.

**Endpoint:** `GET /resources/health/check`

**Response:**
```json
{
  "ok": true,
  "info": {
    "status": "ok",
    "providers": {
      "jira": true,
      "slack": true,
      "gcp": true,
      "grafana": true
    },
    "redis": "ok"
  }
}
```

### Tool Endpoints

All tool endpoints follow the pattern: `POST /tools/{provider}/{tool-name}`

Request body format:
```json
{
  "arguments": {
    "param1": "value1",
    "param2": "value2"
  }
}
```

## Sample cURL Commands

### Test Tool

```bash
# Test echo
curl -X POST http://localhost:8080/tools/test/echo \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "message": "Hello from MCP!"
    }
  }'
```

### Oracle Tools

```bash
# Test Oracle connectivity
curl -X POST http://localhost:8080/tools/oracle/test-connection \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"arguments": {}}'

# List tables in the current schema
curl -X POST http://localhost:8080/tools/oracle/get-tables \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "include_views": false,
      "limit": 100
    }
  }'

# Get columns for a table
curl -X POST http://localhost:8080/tools/oracle/get-columns \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "owner": "HR",
      "table_name": "EMPLOYEES"
    }
  }'

# Fetch rows from any allowed table
curl -X POST http://localhost:8080/tools/oracle/fetch-table \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "owner": "HR",
      "table_name": "EMPLOYEES",
      "columns": ["EMPLOYEE_ID", "FIRST_NAME", "LAST_NAME"],
      "where": "DEPARTMENT_ID = :department_id",
      "bind_params": {
        "department_id": 60
      },
      "order_by": ["EMPLOYEE_ID ASC"],
      "limit": 25,
      "offset": 0
    }
  }'

# Execute read-only SQL
curl -X POST http://localhost:8080/tools/oracle/execute-sql \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "sql_statement": "SELECT employee_id, first_name FROM hr.employees WHERE department_id = :department_id",
      "bind_params": {
        "department_id": 60
      },
      "limit": 25
    }
  }'
```

### Jira Tools

```bash
# Create Jira issue
curl -X POST http://localhost:8080/tools/jira/create-issue \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "projectKey": "PROJ",
      "summary": "Test Issue",
      "description": "This is a test issue",
      "issueType": "Task",
      "idempotency_key": "unique-key-123"
    }
  }'
```

### Slack Tools

```bash
# Post message to Slack
curl -X POST http://localhost:8080/tools/slack/post-message \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "channel": "#general",
      "text": "Hello from MCP Server!"
    }
  }'
```

### GCP Tools

```bash
# List GCS buckets
curl -X POST http://localhost:8080/tools/gcp/list-buckets \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "projectId": "my-gcp-project"
    }
  }'

# Query Cloud Logs
curl -X POST http://localhost:8080/tools/gcp/query-logs \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "projectId": "my-gcp-project",
      "filter": "severity>=ERROR",
      "limit": 50,
      "timeRange": "1h"
    }
  }'

# Search logs by message
curl -X POST http://localhost:8080/tools/gcp/search-logs-by-message \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "projectId": "my-gcp-project",
      "searchTerm": "error",
      "timeRange": "1h",
      "limit": 100,
      "caseSensitive": false
    }
  }'

# Count logs
curl -X POST http://localhost:8080/tools/gcp/count-logs \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "projectId": "my-gcp-project",
      "filter": "severity>=ERROR",
      "timeRange": "1h"
    }
  }'

# List log sinks
curl -X POST http://localhost:8080/tools/gcp/list-log-sinks \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "projectId": "my-gcp-project",
      "parentType": "project"
    }
  }'

# List log views
curl -X POST http://localhost:8080/tools/gcp/list-log-views \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "projectId": "my-gcp-project",
      "location": "global"
    }
  }'

# List log scopes
curl -X POST http://localhost:8080/tools/gcp/list-log-scopes \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "parentId": "my-folder-id",
      "parentType": "folder",
      "location": "global"
    }
  }'

# List log names
curl -X POST http://localhost:8080/tools/gcp/list-log-names \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "projectId": "my-gcp-project",
      "pageSize": 1000
    }
  }'

# List log buckets
curl -X POST http://localhost:8080/tools/gcp/list-log-buckets \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "projectId": "my-gcp-project",
      "location": "global"
    }
  }'
```

### Grafana Tools

```bash
# List dashboards
curl -X POST http://localhost:8080/tools/grafana/get-dashboards \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "query": "my-dashboard",
      "limit": 10
    }
  }'

# Get dashboard by UID
curl -X POST http://localhost:8080/tools/grafana/get-dashboard \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "uid": "dashboard-uid-123"
    }
  }'

# Create dashboard
curl -X POST http://localhost:8080/tools/grafana/create-dashboard \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "dashboard": {
        "title": "My Dashboard",
        "panels": []
      }
    }
  }'

# Get dashboard panel queries
curl -X POST http://localhost:8080/tools/grafana/get-dashboard-panel-queries \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "uid": "dashboard-uid-123"
    }
  }'

# Query Prometheus via Grafana
curl -X POST http://localhost:8080/tools/grafana/query-prometheus \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "expr": "up",
      "time": 1640995200
    }
  }'

# Execute range query
curl -X POST http://localhost:8080/tools/grafana/execute-range-query \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "expr": "rate(http_requests_total[5m])",
      "start_ms": 1640995200000,
      "end_ms": 1640998800000,
      "step": "60s"
    }
  }'

# List datasources
curl -X POST http://localhost:8080/tools/grafana/list-datasources \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{}'

# Get default Prometheus UID
curl -X POST http://localhost:8080/tools/grafana/get-default-prometheus-uid \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{}'
```

### OpenSearch Tools

```bash
# List indices
curl -X POST http://localhost:8080/tools/opensearch/list-indices \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {}
  }'

# Get index mapping
curl -X POST http://localhost:8080/tools/opensearch/get-index-mapping \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "index": "my-index"
    }
  }'

# Search index
curl -X POST http://localhost:8080/tools/opensearch/search-index \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "index": "my-index",
      "body": {
        "query": {
          "match_all": {}
        }
      }
    }
  }'

# Search with time range
curl -X POST http://localhost:8080/tools/opensearch/search-with-time-range \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "index": "my-index",
      "time_field": "@timestamp",
      "start_time": "now-1h",
      "end_time": "now",
      "size": 100
    }
  }'

# Get shards
curl -X POST http://localhost:8080/tools/opensearch/get-shards \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "index": "my-index"
    }
  }'

# Cluster health
curl -X POST http://localhost:8080/tools/opensearch/cluster-health \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {}
  }'

# Count documents
curl -X POST http://localhost:8080/tools/opensearch/count \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "index": "my-index",
      "body": {
        "query": {
          "match_all": {}
        }
      }
    }
  }'

# Get document by ID
curl -X POST http://localhost:8080/tools/opensearch/get-document \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "index": "my-index",
      "id": "document-id-123"
    }
  }'

# Get index info
curl -X POST http://localhost:8080/tools/opensearch/get-index-info \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "index": "my-index"
    }
  }'

# Get index stats
curl -X POST http://localhost:8080/tools/opensearch/get-index-stats \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "index": "my-index"
    }
  }'

# Get cluster stats
curl -X POST http://localhost:8080/tools/opensearch/get-cluster-stats \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {}
  }'

# Get nodes stats
curl -X POST http://localhost:8080/tools/opensearch/get-nodes-stats \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {}
  }'

# Get aliases
curl -X POST http://localhost:8080/tools/opensearch/get-aliases \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {}
  }'

# Create alias
curl -X POST http://localhost:8080/tools/opensearch/create-alias \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "index": "my-index",
      "alias": "my-alias"
    }
  }'
```

### Mimir Tools

```bash
# Instant query
curl -X POST http://localhost:8080/tools/mimir/query-instant \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "query": "up",
      "time": "2025-01-20T00:00:00Z"
    }
  }'

# Range query
curl -X POST http://localhost:8080/tools/mimir/query-range \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "query": "rate(http_requests_total[5m])",
      "startTime": "2025-01-20T00:00:00Z",
      "endTime": "2025-01-20T01:00:00Z",
      "step": "15s"
    }
  }'

# Get series
curl -X POST http://localhost:8080/tools/mimir/get-series \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "match": ["up"]
    }
  }'

# Get labels
curl -X POST http://localhost:8080/tools/mimir/get-labels \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {}
  }'

# Get label values
curl -X POST http://localhost:8080/tools/mimir/get-label-values \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "labelName": "job"
    }
  }'

# Get metadata
curl -X POST http://localhost:8080/tools/mimir/get-metadata \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {}
  }'

# Get targets
curl -X POST http://localhost:8080/tools/mimir/get-targets \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {}
  }'

# Get alerts
curl -X POST http://localhost:8080/tools/mimir/get-alerts \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {}
  }'

# Get rules
curl -X POST http://localhost:8080/tools/mimir/get-rules \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {}
  }'
```

### Prometheus Tools

```bash
# List metrics
curl -X POST http://localhost:8080/tools/prometheus/list-metrics \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "limit": 100,
      "offset": 0,
      "filterPattern": "http"
    }
  }'

# Get metric metadata
curl -X POST http://localhost:8080/tools/prometheus/get-metric-metadata \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "metric": "http_requests_total"
    }
  }'

# Get targets
curl -X POST http://localhost:8080/tools/prometheus/get-targets \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {}
  }'

# Execute query
curl -X POST http://localhost:8080/tools/prometheus/execute-query \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "query": "up",
      "time": "2025-01-20T00:00:00Z"
    }
  }'

# Execute range query
curl -X POST http://localhost:8080/tools/prometheus/execute-range-query \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "query": "rate(http_requests_total[5m])",
      "start": "2025-01-20T00:00:00Z",
      "end": "2025-01-20T01:00:00Z",
      "step": "15s"
    }
  }'
```

### Kubernetes Tools

The Kubernetes adapter provides 34+ read-only tools for cluster inspection. Here are some examples:

```bash
# List pods
curl -X POST http://localhost:8080/tools/k8s/list-pods \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "namespace": "default",
      "allNamespaces": false
    }
  }'

# Get pod details
curl -X POST http://localhost:8080/tools/k8s/get-pod \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "name": "my-pod",
      "namespace": "default"
    }
  }'

# Describe pod
curl -X POST http://localhost:8080/tools/k8s/describe-pod \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "name": "my-pod",
      "namespace": "default"
    }
  }'

# Get pod logs
curl -X POST http://localhost:8080/tools/k8s/get-pod-logs \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "name": "my-pod",
      "namespace": "default",
      "tailLines": 100,
      "timestamps": true
    }
  }'

# List nodes
curl -X POST http://localhost:8080/tools/k8s/list-nodes \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {}
  }'

# Describe node
curl -X POST http://localhost:8080/tools/k8s/describe-node \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "name": "node-1"
    }
  }'

# List namespaces
curl -X POST http://localhost:8080/tools/k8s/list-namespaces \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {}
  }'

# List deployments
curl -X POST http://localhost:8080/tools/k8s/list-deployments \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "namespace": "default",
      "allNamespaces": false
    }
  }'

# List statefulsets
curl -X POST http://localhost:8080/tools/k8s/list-statefulsets \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "namespace": "default"
    }
  }'

# List daemonsets
curl -X POST http://localhost:8080/tools/k8s/list-daemonsets \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "namespace": "default"
    }
  }'

# List jobs
curl -X POST http://localhost:8080/tools/k8s/list-jobs \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "namespace": "default"
    }
  }'

# List cronjobs
curl -X POST http://localhost:8080/tools/k8s/list-cronjobs \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "namespace": "default"
    }
  }'

# Get pod events
curl -X POST http://localhost:8080/tools/k8s/get-pod-events \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "name": "my-pod",
      "namespace": "default"
    }
  }'

# List events
curl -X POST http://localhost:8080/tools/k8s/list-events \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "namespace": "default",
      "allNamespaces": false
    }
  }'

# Search events
curl -X POST http://localhost:8080/tools/k8s/search-events \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "namespace": "default",
      "reason": "Failed",
      "messageContains": "error"
    }
  }'

# Get node metrics (requires metrics-server in cluster)
curl -X POST http://localhost:8080/tools/k8s/get-node-metrics \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {}
  }'

# Get pod metrics (requires metrics-server in cluster)
curl -X POST http://localhost:8080/tools/k8s/get-pod-metrics \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "namespace": "default"
    }
  }'

# List HPAs
curl -X POST http://localhost:8080/tools/k8s/list-hpa \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "namespace": "default"
    }
  }'

# Get HPA status
curl -X POST http://localhost:8080/tools/k8s/get-hpa-status \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "name": "my-hpa",
      "namespace": "default"
    }
  }'

# Get PDBs
curl -X POST http://localhost:8080/tools/k8s/get-pdbs \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "namespace": "default"
    }
  }'

# Diagnose pod status
curl -X POST http://localhost:8080/tools/k8s/diagnose-pod-status \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "name": "my-pod",
      "namespace": "default"
    }
  }'

# Diagnose node status
curl -X POST http://localhost:8080/tools/k8s/diagnose-node-status \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "name": "node-1"
    }
  }'

# Cluster info
curl -X POST http://localhost:8080/tools/k8s/cluster-info \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {}
  }'

# API server health
curl -X POST http://localhost:8080/tools/k8s/api-server-health \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {}
  }'

# Node health report
curl -X POST http://localhost:8080/tools/k8s/node-health-report \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {}
  }'

# Pod health report
curl -X POST http://localhost:8080/tools/k8s/pod-health-report \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "namespace": "default"
    }
  }'

# List API resources
curl -X POST http://localhost:8080/tools/k8s/list-api-resources \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {}
  }'

# List custom resources
curl -X POST http://localhost:8080/tools/k8s/list-custom-resources \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {}
  }'
```

**Note:** For a complete list of all Kubernetes tools, use the manifest endpoint to discover available tools dynamically.

## Docker Deployment

### Development

```bash
docker-compose up
```

This starts:
- Redis on port 6379
- MCP Server on port 8080

### Production

```bash
docker-compose -f docker-compose.prod.yml up -d
```

Make sure to set all required environment variables in `docker-compose.prod.yml` or use a `.env` file.

### CI/CD Build Command

**Important:** If building from a parent directory, use the correct path:

```bash
# Correct build command (from repository root)
docker build -t "mcp:test" -f Dockerfile agentic-mcp-server/.

# Incorrect (will fail): unified-mcp/.
```

The build context must be `agentic-mcp-server/.` (not `unified-mcp/.`).

## Available Tools Summary

### Test Tools
- `test.echo` - Simple test tool

### Oracle Tools
- `oracle.testConnection` - Test Oracle database connectivity
- `oracle.getTables` - List tables and optionally views
- `oracle.getColumns` - Get column metadata for a table
- `oracle.getSchema` - Get schema metadata for tables/views
- `oracle.fetchTable` - Fetch rows from any allowed table with columns, filters, order, limit, and offset
- `oracle.executeSQL` - Execute read-only `SELECT`/`WITH` SQL with bind parameters

### Jira Tools
- `jira.createIssue` - Create a Jira issue

### Slack Tools
- `slack.postMessage` - Post a message to Slack

### GCP Tools (9 tools)
- `gcp.listBuckets` - List GCS buckets
- `gcp.queryLogs` - Query Cloud Logs
- `gcp.countLogs` - Count Cloud Logs
- `gcp.searchLogsByMessage` - Search logs by message content
- `gcp.listLogSinks` - List log sinks
- `gcp.listLogViews` - List log views
- `gcp.listLogScopes` - List log scopes
- `gcp.listLogNames` - List log names
- `gcp.listLogBuckets` - List log buckets

### Grafana Tools (9 tools)
- `grafana.getDashboards` - List dashboards
- `grafana.getDashboard` - Get dashboard by UID
- `grafana.createDashboard` - Create dashboard
- `grafana.getDashboardByUid` - Get full dashboard details
- `grafana.getDashboardPanelQueries` - Get panel queries
- `grafana.queryPrometheus` - Query Prometheus
- `grafana.executeRangeQuery` - Execute range query
- `grafana.listDatasources` - List datasources
- `grafana.getDefaultPrometheusUid` - Get default Prometheus UID

### OpenSearch Tools (25+ tools)
- `opensearch.listIndices` - List indices
- `opensearch.getIndexMapping` - Get index mapping
- `opensearch.searchIndex` - Search index
- `opensearch.searchWithTimeRange` - Search with time range
- `opensearch.getShards` - Get shard info
- `opensearch.clusterHealth` - Get cluster health
- `opensearch.count` - Count documents
- `opensearch.explain` - Explain query
- `opensearch.msearch` - Multi-search
- `opensearch.getClusterState` - Get cluster state
- `opensearch.getSegments` - Get Lucene segments
- `opensearch.catNodes` - Get node metrics
- `opensearch.getNodes` - Get node info
- `opensearch.getIndexInfo` - Get index info
- `opensearch.getIndexStats` - Get index stats
- `opensearch.getQueryInsights` - Get query insights
- `opensearch.getNodesHotThreads` - Get hot threads
- `opensearch.getAllocation` - Get shard allocation
- `opensearch.getLongRunningTasks` - Get long-running tasks
- `opensearch.getNodesStats` - Get nodes stats
- `opensearch.getClusterStats` - Get cluster stats
- `opensearch.getTasks` - Get tasks
- `opensearch.getAliases` - Get aliases
- `opensearch.getTemplates` - Get templates
- `opensearch.getMapping` - Get mapping
- `opensearch.createAlias` - Create alias
- `opensearch.getDocument` - Get document by ID

### Mimir Tools (9 tools)
- `mimir.queryInstant` - Instant query
- `mimir.queryRange` - Range query
- `mimir.getSeries` - Get series
- `mimir.getLabels` - Get labels
- `mimir.getLabelValues` - Get label values
- `mimir.getMetadata` - Get metadata
- `mimir.getTargets` - Get targets
- `mimir.getAlerts` - Get alerts
- `mimir.getRules` - Get rules

### Prometheus Tools (5 tools)
- `prometheus.listMetrics` - List metrics
- `prometheus.getMetricMetadata` - Get metric metadata
- `prometheus.getTargets` - Get targets
- `prometheus.executeQuery` - Execute query
- `prometheus.executeRangeQuery` - Execute range query

### Kubernetes Tools (34+ tools)
The Kubernetes adapter provides comprehensive read-only access to cluster resources including:
- Pods (list, get, describe, logs, events, metrics)
- Nodes (list, describe, metrics, health)
- Namespaces (list, events)
- Deployments, StatefulSets, DaemonSets, ReplicaSets
- Jobs and CronJobs
- ConfigMaps
- Events (list, search, filter)
- Metrics (node, pod) - **Requires metrics-server in cluster (cluster infrastructure)**
- HPAs and PDBs
- Resource quotas and limit ranges
- Cluster info and health
- API resources and custom resources
- Diagnostics tools

**Cluster Requirements:**
- Metrics tools (`k8s.getPodMetrics`, `k8s.getNodeMetrics`) require the Kubernetes metrics-server to be installed in the cluster. This is cluster infrastructure configuration, not application configuration.
- The MCP server/adapter needs kubeconfig or service account credentials configured at the MCP server level (via `K8S_KUBECONFIG`, `K8S_CONTEXT`, etc. environment variables).

## Error Handling

All endpoints return JSON responses with the following structure:

**Success:**
```json
{
  "ok": true,
  "result": {...}
}
```

**Error:**
```json
{
  "ok": false,
  "error": "Error message",
  "status": 400
}
```

## Rate Limiting

If Redis is configured, rate limiting is enabled by default:
- Capacity: 120 requests
- Refill: 60 seconds
- Fail-open: true (allows requests if Redis is unavailable)

## Idempotency

If `IDEMPOTENCY_TTL > 0` and Redis is available, idempotency is enabled. Include an `idempotency_key` in your request to get cached responses for duplicate requests.

## License

[Add your license here]

## Contributing

[Add contributing guidelines here]

