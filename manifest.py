# manifest.py
from typing import Any, Dict

from tool_specs.k8s import K8S_TOOL_SPECS
from tool_specs.oracle_specs import ORACLE_TOOL_SPECS


def build_manifest(enabled_tools: Dict[str, bool]) -> Dict[str, Any]:
    """
    Build a simple machine-readable manifest of available tools.
    `enabled_tools` is a dict like {"jira": True, "slack": False, "oracle": True}.
    """

    auth_info = {
        "type": "bearer",
        "header": "Authorization",
        "description": "Send 'Authorization: Bearer <MCP_API_KEY>'"
    }

    tools: Dict[str, Dict[str, Any]] = {}

    # Always include test tool
    tools["test.echo"] = {
        "name": "test.echo",
        "description": "Simple test tool to verify MCP server functionality",
        "http": {"path": "/tools/test/echo", "method": "POST"},
        "inputs": {
            "message": "string (optional) — message to echo back"
        }
    }

    # ✅ Oracle tools — ADD THIS BLOCK
    if enabled_tools.get("oracle"):
        tools["oracle_test_connection"] = {
            "name": "oracle_test_connection",
            "description": "Test Oracle database connection (uses DB_CONNECTION_STRING from .env)",
            "http": {"path": "/tools/oracle/test-connection", "method": "POST"},
            "inputs": {}
        }
        tools["oracle_get_tables"] = {
            "name": "oracle_get_tables",
            "description": "List all tables in the Oracle database",
            "http": {"path": "/tools/oracle/get-tables", "method": "POST"},
            "inputs": {}
        }
        tools["oracle_get_columns"] = {
            "name": "oracle_get_columns",
            "description": "Get columns for a specific Oracle table",
            "http": {"path": "/tools/oracle/get-columns", "method": "POST"},
            "inputs": {
                "table_name": "string (required) — name of the table"
            }
        }
        tools["oracle_get_schema"] = {
            "name": "oracle_get_schema",
            "description": "Get full schema of all Oracle tables with column details",
            "http": {"path": "/tools/oracle/get-schema", "method": "POST"},
            "inputs": {}
        }
        tools["execute_sql"] = {
            "name": "execute_sql",
            "description": "Execute any SQL statement against Oracle database",
            "http": {"path": "/tools/oracle/execute-sql", "method": "POST"},
            "inputs": {
                "sql_statement": "string (required) — SQL query to execute"
            }
        }
        tools["connect_to_database"] = {
            "name": "connect_to_database",
            "description": "Connect to Oracle database and verify the connection",
            "http": {"path": "/tools/oracle/connect", "method": "POST"},
            "inputs": {
                "connection_string": "string (optional) — overrides DB_CONNECTION_STRING from .env"
            }
        }

    # Jira
    if enabled_tools.get("jira"):
        tools["jira.createIssue"] = {
            "name": "jira.createIssue",
            "description": "Create an issue in Jira",
            "http": {"path": "/tools/jira/create-issue", "method": "POST"},
            "inputs": {
                "projectKey": "string (required)",
                "summary": "string (required)",
                "description": "string (optional)",
                "issueType": "string (optional, default 'Task')",
                "idempotency_key": "string (optional)"
            }
        }

    # Slack
    if enabled_tools.get("slack"):
        tools["slack.postMessage"] = {
            "name": "slack.postMessage",
            "description": "Post a message to a Slack channel",
            "http": {"path": "/tools/slack/post-message", "method": "POST"},
            "inputs": {
                "channel": "string (required) — channel ID or name",
                "text": "string (required)",
                "blocks": "array (optional) — Slack Block Kit"
            }
        }

    # GCP
    if enabled_tools.get("gcp"):
        tools["gcp.listBuckets"] = {
            "name": "gcp.listBuckets",
            "description": "List GCS buckets in a project",
            "http": {"path": "/tools/gcp/list-buckets", "method": "POST"},
            "inputs": {"projectId": "string (required)"}
        }
        tools["gcp.queryLogs"] = {
            "name": "gcp.queryLogs",
            "description": "Query Google Cloud Logs for a project using a filter",
            "http": {"path": "/tools/gcp/query-logs", "method": "POST"},
            "inputs": {
                "projectId": "string (required)",
                "filter": "string (optional)",
                "limit": "number (optional, default 50, max 1000)",
                "timeRange": "string (optional) — e.g. '1h', '30m'",
                "startTime": "string (optional) — RFC3339 format",
                "endTime": "string (optional) — RFC3339 format"
            }
        }
        tools["gcp.countLogs"] = {
            "name": "gcp.countLogs",
            "description": "Count Google Cloud Logs matching a filter",
            "http": {"path": "/tools/gcp/count-logs", "method": "POST"},
            "inputs": {
                "projectId": "string (required)",
                "filter": "string (optional)",
                "timeRange": "string (optional)",
                "startTime": "string (optional)",
                "endTime": "string (optional)"
            }
        }
        tools["gcp.searchLogsByMessage"] = {
            "name": "gcp.searchLogsByMessage",
            "description": "Search Google Cloud Logs by message content",
            "http": {"path": "/tools/gcp/search-logs-by-message", "method": "POST"},
            "inputs": {
                "projectId": "string (required)",
                "searchTerm": "string (required)",
                "timeRange": "string (optional, default '1h')",
                "limit": "number (optional, default 100)",
                "caseSensitive": "boolean (optional, default false)",
                "filter": "string (optional)",
                "startTime": "string (optional)",
                "endTime": "string (optional)"
            }
        }
        tools["gcp.listLogSinks"] = {
            "name": "gcp.listLogSinks",
            "description": "List log sinks for a project",
            "http": {"path": "/tools/gcp/list-log-sinks", "method": "POST"},
            "inputs": {
                "projectId": "string (required)",
                "parentType": "string (optional, default 'project')"
            }
        }
        tools["gcp.listLogViews"] = {
            "name": "gcp.listLogViews",
            "description": "List log views for a project",
            "http": {"path": "/tools/gcp/list-log-views", "method": "POST"},
            "inputs": {
                "projectId": "string (required)",
                "location": "string (optional, default 'global')",
                "bucketId": "string (optional)"
            }
        }
        tools["gcp.listLogNames"] = {
            "name": "gcp.listLogNames",
            "description": "List log names for a project",
            "http": {"path": "/tools/gcp/list-log-names", "method": "POST"},
            "inputs": {
                "projectId": "string (required)",
                "pageSize": "number (optional, default 1000)"
            }
        }
        tools["gcp.listLogBuckets"] = {
            "name": "gcp.listLogBuckets",
            "description": "List log buckets for a project",
            "http": {"path": "/tools/gcp/list-log-buckets", "method": "POST"},
            "inputs": {
                "projectId": "string (required)",
                "location": "string (optional, default 'global')"
            }
        }

    # Grafana
    if enabled_tools.get("grafana"):
        tools["grafana.getDashboards"] = {
            "name": "grafana.getDashboards",
            "description": "List Grafana dashboards",
            "http": {"path": "/tools/grafana/get-dashboards", "method": "POST"},
            "inputs": {
                "query": "string (optional)", "folderIds": "array<number> (optional)",
                "tags": "array<string> (optional)", "starred": "boolean (optional)",
                "page": "number (optional)", "limit": "number (optional)"
            }
        }
        tools["grafana.getDashboard"] = {
            "name": "grafana.getDashboard",
            "description": "Get a Grafana dashboard by UID",
            "http": {"path": "/tools/grafana/get-dashboard", "method": "POST"},
            "inputs": {"uid": "string (required)"}
        }
        tools["grafana.createDashboard"] = {
            "name": "grafana.createDashboard",
            "description": "Create a new Grafana dashboard",
            "http": {"path": "/tools/grafana/create-dashboard", "method": "POST"},
            "inputs": {"dashboard": "object (required)"}
        }
        tools["grafana.queryPrometheus"] = {
            "name": "grafana.queryPrometheus",
            "description": "Execute Prometheus queries via Grafana",
            "http": {"path": "/tools/grafana/query-prometheus", "method": "POST"},
            "inputs": {
                "expr": "string (required)",
                "time": "number (optional)",
                "datasourceUid": "string (optional)"
            }
        }
        tools["grafana.executeRangeQuery"] = {
            "name": "grafana.executeRangeQuery",
            "description": "Execute time-range queries via Grafana",
            "http": {"path": "/tools/grafana/execute-range-query", "method": "POST"},
            "inputs": {
                "expr": "string (required)",
                "start_ms": "number (required)",
                "end_ms": "number (required)",
                "step": "string (optional, default '60s')",
                "datasourceUid": "string (optional)"
            }
        }
        tools["grafana.listDatasources"] = {
            "name": "grafana.listDatasources",
            "description": "List Grafana datasources",
            "http": {"path": "/tools/grafana/list-datasources", "method": "POST"},
            "inputs": {}
        }

    # Mimir
    if enabled_tools.get("mimir"):
        tools["mimir.queryInstant"] = {
            "name": "mimir.queryInstant",
            "description": "Execute an instant PromQL query against Mimir",
            "http": {"path": "/tools/mimir/query-instant", "method": "POST"},
            "inputs": {
                "query": "string (required)",
                "time": "string (optional)"
            }
        }
        tools["mimir.queryRange"] = {
            "name": "mimir.queryRange",
            "description": "Execute a range PromQL query against Mimir",
            "http": {"path": "/tools/mimir/query-range", "method": "POST"},
            "inputs": {
                "query": "string (required)",
                "startTime": "string (required)",
                "endTime": "string (required)",
                "step": "string (optional, default '15s')"
            }
        }
        tools["mimir.getAlerts"] = {
            "name": "mimir.getAlerts",
            "description": "Get active alerts from Mimir",
            "http": {"path": "/tools/mimir/get-alerts", "method": "POST"},
            "inputs": {}
        }
        tools["mimir.getRules"] = {
            "name": "mimir.getRules",
            "description": "Get recording and alerting rules from Mimir",
            "http": {"path": "/tools/mimir/get-rules", "method": "POST"},
            "inputs": {}
        }

    # Kubernetes
    if enabled_tools.get("k8s"):
        for spec in K8S_TOOL_SPECS:
            tools[spec["tool"]] = {
                "name": spec["tool"],
                "description": spec["description"],
                "http": {"path": spec["http_path"], "method": "POST"},
                "inputs": spec["inputs"],
            }

    # Prometheus
    if enabled_tools.get("prometheus"):
        tools["prometheus.listMetrics"] = {
            "name": "prometheus.listMetrics",
            "description": "List all available Prometheus metrics",
            "http": {"path": "/tools/prometheus/list-metrics", "method": "POST"},
            "inputs": {
                "limit": "number (optional)",
                "offset": "number (optional, default 0)",
                "filterPattern": "string (optional)"
            }
        }
        tools["prometheus.executeQuery"] = {
            "name": "prometheus.executeQuery",
            "description": "Execute a PromQL instant query",
            "http": {"path": "/tools/prometheus/execute-query", "method": "POST"},
            "inputs": {
                "query": "string (required)",
                "time": "string (optional)"
            }
        }
        tools["prometheus.executeRangeQuery"] = {
            "name": "prometheus.executeRangeQuery",
            "description": "Execute a PromQL range query",
            "http": {"path": "/tools/prometheus/execute-range-query", "method": "POST"},
            "inputs": {
                "query": "string (required)",
                "start": "string (required)",
                "end": "string (required)",
                "step": "string (required)"
            }
        }

    return {
        "name": "unified-mcp-server",
        "version": "1.0.0",
        "description": "Unified MCP server with Oracle, GCP, Grafana, OpenSearch, Mimir, K8s, Prometheus tools.",
        "auth": auth_info,
        "tools": tools,
    }