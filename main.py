import asyncio
import logging
import os                     
import re
import time
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()                   
from fastmcp import FastMCP

from adapters.oracle import OracleAdapter
from schemas.oracle import (
    OracleExecuteSQLInput,
    OracleGetTableDetailsInput,
    OracleGetColumnDetailsInput,
)

oracle_adapter = OracleAdapter() 

mcp = FastMCP(name="unified-mcp-server")

# load .env early
load_dotenv()


from adapters.gcp import GcpAdapter
from adapters.grafana import GrafanaAdapter
from adapters.jira import JiraAdapter
from adapters.k8s import KubernetesAdapter
from adapters.mimir import MimirAdapter
from adapters.opensearch import OpenSearchAdapter
from adapters.prometheus import PrometheusAdapter
from adapters.slack import SlackAdapter
from adapters.tempo import TempoAdapter
from manifest import build_manifest
from schemas.grafana import (
    GrafanaCreateDashboardInput,
    GrafanaExecuteRangeQueryInput,
    GrafanaGetDashboardInput,
    GrafanaListDashboardsInput,
    GrafanaQueryPrometheusInput,
)
from schemas.gcp import (
    GcpCountLogsInput,
    GcpListBucketsInput,
    GcpListLogBucketsInput,
    GcpListLogNamesInput,
    GcpListLogScopesInput,
    GcpListLogSinksInput,
    GcpListLogViewsInput,
    GcpQueryLogsInput,
    GcpSearchLogsByMessageInput,
)
from schemas.jira import JiraCreateIssueInput
from schemas.k8s import get_k8s_input_schema
from schemas.mimir import (
    MimirLabelValuesInput,
    MimirLabelsInput,
    MimirQueryInstantInput,
    MimirQueryRangeInput,
    MimirSeriesInput,
)
from schemas.opensearch import (
    OpenSearchAliasInput,
    OpenSearchCatNodesInput,
    OpenSearchClusterStateInput,
    OpenSearchCountInput,
    OpenSearchDocumentInput,
    OpenSearchExplainInput,
    OpenSearchGetNodesInput,
    OpenSearchIndexMetricInput,
    OpenSearchIndexInput,
    OpenSearchIndexOptionalInput,
    OpenSearchLongRunningTasksInput,
    OpenSearchMsearchInput,
    OpenSearchSearchInput,
    OpenSearchSearchWithTimeRangeInput,
    OpenSearchTasksInput,
    OpenSearchTemplatesInput,
)
from schemas.prometheus import (
    PrometheusExecuteQueryInput,
    PrometheusExecuteRangeQueryInput,
    PrometheusListMetricsInput,
    PrometheusMetricInput,
)
from schemas.slack import SlackPostMessageInput
from schemas.tempo import (
    TempoGetTraceInput,
    TempoQueryMetricsInput,
    TempoSearchTagsInput,
    TempoSearchTagValuesInput,
    TempoSearchTracesInput,
)
from schemas.utils import ConfigureLoggingInput, IdempotencySetIfNotExistsInput
from tool_specs.k8s import K8S_TOOL_SPECS
from utils.auth import require_mcp_auth_and_rate
from utils.config import settings
from utils.errors import MCPError, ProviderError
from utils.http_client import SharedAsyncClient
from utils.idempotency_redis import IdempotencyStoreRedis
from utils.logging_config import configure_logging
from utils.ratelimit_redis import RedisRateLimiter

logger = configure_logging(ConfigureLoggingInput())

def convert_time_to_ms(time_str: str):
    """
    Convert relative or absolute time expressions into millisecond timestamps.

    All times are interpreted as UTC to ensure consistency across different server timezones.

    Supports:
      - ISO 8601 format: "2025-10-24T07:00:00Z", "2025-10-24T07:00:00+00:00"
      - Relative times: "1 hour ago", "30 minutes ago", "2 hours ago"
      - Absolute times: "12:20pm", "12:20", "from 11:30 to 12:30" (interpreted as UTC)
      - Full date-time: "2025-10-24 12:30pm", "2025-10-24 12:30" (interpreted as UTC)
      - Keyword: "now"

    Returns:
      dict with start_ms and/or end_ms depending on format (all values are integers in UTC)
    """

    now = datetime.now()
    current_ms = int(time.time() * 1000)

    # Handle "now"
    if time_str.strip().lower() == "now":
        return {"end_ms": current_ms}

    # Handle ISO 8601 format (e.g. "2025-10-24T07:00:00Z", "2025-10-24T07:00:00+00:00")
    if 'T' in time_str.strip():
        try:
            # Replace Z with +00:00 for compatibility
            iso_str = time_str.strip().replace('Z', '+00:00')
            dt = datetime.fromisoformat(iso_str)
            # If timezone-naive, assume UTC
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            # Convert to UTC if it has timezone info
            dt = dt.astimezone(timezone.utc)
            timestamp_ms = int(dt.timestamp() * 1000)
            return {"start_ms": timestamp_ms, "end_ms": timestamp_ms}
        except (ValueError, AttributeError):
            pass  # Fall through to other patterns

    # Handle relative times (e.g. "1 hour ago", "30 minutes ago")
    match = re.match(r"(\d+)\s*(minute|minutes|hour|hours)\s*ago", time_str.lower())
    if match:
        amount, unit = int(match.group(1)), match.group(2)
        delta_ms = amount * 60_000 if "minute" in unit else amount * 3_600_000
        return {"start_ms": int(current_ms - delta_ms), "end_ms": int(current_ms)}

    # Handle full date-time format (e.g. "2025-10-24 12:30pm")
    full_datetime_pattern = re.match(r"(\d{4}-\d{1,2}-\d{1,2})\s+(\d{1,2}:\d{2}(?:\s*[apAP][mM]?)?)", time_str.strip())
    if full_datetime_pattern:
        date_str, time_str_part = full_datetime_pattern.groups()
        time_str_part = time_str_part.strip().lower()
        try:
            # Parse the full date-time - try with AM/PM first, then 24-hour format
            if 'am' in time_str_part or 'pm' in time_str_part:
                dt = datetime.strptime(f"{date_str} {time_str_part}", "%Y-%m-%d %I:%M%p")
            else:
                dt = datetime.strptime(f"{date_str} {time_str_part}", "%Y-%m-%d %H:%M")
            # Make it timezone-aware (UTC) to avoid timezone issues
            dt = dt.replace(tzinfo=timezone.utc)
            timestamp_ms = int(dt.timestamp() * 1000)
            return {"start_ms": timestamp_ms, "end_ms": timestamp_ms}
        except ValueError:
            pass  # Fall through to other patterns

    # Handle absolute times (e.g. "12:30pm", "12:30", "from 12:20pm to 1:20pm")
    # Find all time patterns (both 12-hour with AM/PM and 24-hour format)
    time_patterns = re.findall(r"(\d{1,2}:\d{2}(?:\s*[apAP][mM]?)?)", time_str)
    if time_patterns:
        times = []
        # Get current UTC date for consistency across timezones
        now_utc = datetime.now(timezone.utc)
        for t in time_patterns:
            t = t.strip().lower()
            try:
                # Try 12-hour format first (with AM/PM)
                if 'am' in t or 'pm' in t:
                    time_obj = datetime.strptime(t, "%I:%M%p")
                else:
                    # Try 24-hour format
                    time_obj = datetime.strptime(t, "%H:%M")
                # Combine with today's UTC date and make timezone-aware
                dt = datetime.combine(now_utc.date(), time_obj.time())
                dt = dt.replace(tzinfo=timezone.utc)
                times.append(int(dt.timestamp() * 1000))
            except ValueError:
                # Skip invalid time formats
                continue

        if len(times) == 1:
            return {"start_ms": int(times[0]), "end_ms": int(times[0])}
        elif len(times) == 2:
            return {"start_ms": int(times[0]), "end_ms": int(times[1])}

    raise ValueError(f"Unsupported time format: '{time_str}'")

# create FastMCP instance with transport set
mcp = FastMCP(name="unified-mcp-server")

# Shared resources
idempotency_store: IdempotencyStoreRedis | None = None
rate_limiter: RedisRateLimiter | None = None

# Track which providers are actually available (after registration)
gcp_available = False

# -- resources (use absolute HTTP URLs so FastMCP accepts them) --
@mcp.resource("resource://manifest")
def manifest_resource():
    enabled = {
        "jira": bool(settings.JIRA_API_TOKEN and settings.JIRA_EMAIL and settings.JIRA_BASE),
        "slack": bool(settings.SLACK_BOT_TOKEN),
        "gcp": gcp_available,  # Use actual registration status
        "grafana": bool(settings.GRAFANA_BASE_URL and (
            settings.GRAFANA_API_KEY or
            (settings.GRAFANA_USERNAME and settings.GRAFANA_PASSWORD)
        )),
        "opensearch": bool(settings.OPENSEARCH_URL),
        "mimir": bool(settings.MIMIR_URL),
        "k8s": bool(settings.K8S_ENABLED),
        "prometheus": bool(settings.PROMETHEUS_ENDPOINT),
        "tempo": bool(settings.TEMPO_URL)
    }
    return build_manifest(enabled)

@mcp.resource("resource://health/{action}")
async def health_resource(action: str):
    info = {"status": "ok", "providers": {
        "jira": bool(settings.JIRA_API_TOKEN),
        "slack": bool(settings.SLACK_BOT_TOKEN),
        "gcp": bool(settings.GCP_SA_JSON),
        "grafana": bool(settings.GRAFANA_BASE_URL and (
            settings.GRAFANA_API_KEY or
            (settings.GRAFANA_USERNAME and settings.GRAFANA_PASSWORD)
        ))
    }}
    # redis check
    try:
        import redis.asyncio as redis
        r = redis.from_url(settings.REDIS_URL)
        pong = await r.ping()
        info["redis"] = "ok" if pong else "error"
        await r.aclose()
    except Exception as ex:
        info["redis"] = f"unavailable: {ex}"
        info["redis_note"] = "Redis services (idempotency, rate limiting) are disabled"

    # optional provider checks (HEALTHCHECK_FULL)
    if settings.HEALTHCHECK_FULL:
        if settings.SLACK_BOT_TOKEN:
            try:
                s = SlackAdapter(None)
                client = SharedAsyncClient.get_client()
                resp = await client.get("https://slack.com/api/auth.test", headers={"Authorization": f"Bearer {s.token}"})
                info["slack_auth_ok"] = resp.json().get("ok", False)
            except Exception:
                info["slack_auth_ok"] = False
        if settings.JIRA_API_TOKEN:
            try:
                j = JiraAdapter(None)
                client = SharedAsyncClient.get_client()
                resp = await client.get(f"{j.base}/rest/api/3/myself", auth=j.auth)
                info["jira_auth_ok"] = getattr(resp, "status_code", None) == 200
            except Exception:
                info["jira_auth_ok"] = False
    return {"ok": True, "info": info}

# -- initialization --
async def init_services():
    global idempotency_store, rate_limiter
    logger.info("init: starting shared resources")
    SharedAsyncClient.get_client()

    # Initialize idempotency store only if Redis is available and TTL is set
    if getattr(settings, "IDEMPOTENCY_TTL", 0) > 0:
        try:
            idempotency_store = IdempotencyStoreRedis(settings.REDIS_URL)
            logger.info("init: idempotency store configured")
        except Exception as e:
            idempotency_store = None
            logger.warning(f"init: idempotency store disabled - Redis unavailable: {e}")
    else:
        idempotency_store = None
        logger.info("init: idempotency disabled")

    # Initialize rate limiter only if Redis is available
    try:
        rate_limiter = RedisRateLimiter(settings.REDIS_URL, settings.RATE_LIMIT_CAPACITY, settings.RATE_LIMIT_REFILL_SECONDS, fail_open=settings.RATE_LIMIT_FAIL_OPEN)
        await rate_limiter.init()
        logger.info("init: rate limiter ready")
    except Exception as e:
        rate_limiter = None
        logger.warning(f"init: rate limiter disabled - Redis unavailable: {e}")

def register_tools():
    # Test tool (always available) - Auth disabled for stateless mode testing
    async def test_tool(params: dict, ctx=None):
        """Simple test tool to verify MCP server functionality.

        Parameters:
            message (optional): Message to echo back.
        """
        # await require_mcp_auth_and_rate(ctx, rate_limiter)
        message = params.get("message", "Hello from MCP server!")
        return {
            "ok": True,
            "response": f"Test successful: {message}",
            "timestamp": str(asyncio.get_event_loop().time()),
            "server_name": "unified-mcp-server",
            "auth_note": "Authentication temporarily disabled for stateless mode testing"
        }
    mcp.tool(name="test.echo")(test_tool)

    # Jira
    if settings.JIRA_API_TOKEN and settings.JIRA_EMAIL and settings.JIRA_BASE:
        jira_adapter = JiraAdapter(None)
        async def jira_create_issue(params: dict, ctx=None):
            """Create an issue in Jira.

            Required parameters:
                projectKey: Project key for the issue.
                summary: Issue summary/title.

            Optional parameters:
                description: Issue description.
                issueType: Issue type (default: 'Task').
                idempotency_key: Server will return cached response if present.
            """
            # await require_mcp_auth_and_rate(ctx, rate_limiter)  # Disabled for stateless mode
            idemp_key = params.get("idempotency_key")
            if idemp_key and idempotency_store:
                existing = await idempotency_store.get(idemp_key)
                if existing:
                    return existing
            issue_input = JiraCreateIssueInput.parse_or_error(
                {
                    "project_key": params.get("projectKey"),
                    "summary": params.get("summary"),
                    "description": params.get("description", ""),
                    "issue_type": params.get("issueType", "Task"),
                },
                "jira",
            )
            created = await jira_adapter.create_issue(issue_input)
            out = {"ok": True, "issueKey": created.get("key"), "id": created.get("id")}
            if idemp_key and idempotency_store:
                await idempotency_store.set_if_not_exists(
                    IdempotencySetIfNotExistsInput(raw_key=idemp_key, payload=out)
                )
            return out
        mcp.tool(name="jira.createIssue", tags=["jira"])(jira_create_issue)

    # Slack
    if settings.SLACK_BOT_TOKEN:
        slack_adapter = SlackAdapter(None)
        async def slack_post_message(params: dict, ctx=None):
            """Post a message to a Slack channel.

            Required parameters:
                channel: Channel ID or name.
                text: Message text.

            Optional parameters:
                blocks: Slack Block Kit array.
            """
            # await require_mcp_auth_and_rate(ctx, rate_limiter)  # Disabled for stateless mode
            msg_input = SlackPostMessageInput.parse_or_error(
                {"channel": params.get("channel"), "text": params.get("text"), "blocks": params.get("blocks")},
                "slack",
            )
            res = await slack_adapter.post_message(msg_input)
            return {"ok": True, "ts": res.get("ts"), "channel": res.get("channel")}
        mcp.tool(name="slack.postMessage", tags=["slack"])(slack_post_message)

    # GCP - supports service account or Application Default Credentials (ADC)
    global gcp_available
    try:
        gcp_adapter = GcpAdapter(None)
        async def gcp_list_buckets(params: dict, ctx=None):
            """
            List GCS buckets in a GCP project.

            Args:
                params: Dictionary containing:
                    - projectId (str, required): GCP project ID

            Returns:
                dict: {"ok": True, "buckets": [...]} where buckets contain name, timeCreated, location
            """
            # await require_mcp_auth_and_rate(ctx, rate_limiter)  # Disabled for stateless mode
            loop = asyncio.get_running_loop()
            items = await loop.run_in_executor(
                None,
                gcp_adapter.list_buckets,
                GcpListBucketsInput.parse_or_error({"project_id": params.get("projectId")}, "gcp"),
            )
            out = [{"name": b.get("name"), "timeCreated": b.get("timeCreated"), "location": b.get("location")} for b in items]
            return {"ok": True, "buckets": out}
        mcp.tool(name="gcp.listBuckets", tags=["gcp"])(gcp_list_buckets)

        async def gcp_query_logs(params: dict, ctx=None):
            """
            Query Google Cloud Logs for a project using a filter.

            Args:
                params: Dictionary containing:
                    - projectId (str, required): GCP project ID
                    - filter (str, optional): Logging filter string (e.g., 'severity>=ERROR')
                    - limit (int, optional, default: 50, max: 1000): Maximum number of log entries to return
                    - timeRange (str, optional): Relative time range (e.g., '1h', '30m', '2d', '1w').
                      Ignored if startTime is provided.
                    - startTime (str, optional): Start time in RFC3339 format (e.g., '2025-11-20T10:00:00Z')
                    - endTime (str, optional): End time in RFC3339 format (e.g., '2025-11-20T12:00:00Z')

            Returns:
                dict: {"ok": True, "logs": [...], "logs_length": N} where logs is a list of log entry dictionaries

            Note:
                Either filter, timeRange, or startTime/endTime must be provided.
            """
            # await require_mcp_auth_and_rate(ctx, rate_limiter)  # Disabled for stateless mode
            loop = asyncio.get_running_loop()
            logs = await loop.run_in_executor(
                None,
                gcp_adapter.query_logs,
                GcpQueryLogsInput.parse_or_error(
                    {
                        "project_id": params.get("projectId"),
                        "filter_": params.get("filter"),
                        "limit": params.get("limit", 50),
                        "start_time": params.get("startTime"),
                        "end_time": params.get("endTime"),
                        "time_range": params.get("timeRange"),
                    },
                    "gcp",
                ),
            )
            return {"ok": True, "logs": logs, "logs_length": len(logs)}
        mcp.tool(name="gcp.queryLogs", tags=["gcp"])(gcp_query_logs)

        async def gcp_count_logs(params: dict, ctx=None):
            """
            Count Google Cloud Logs for a project using a filter.

            Args:
                params: Dictionary containing:
                    - projectId (str, required): GCP project ID
                    - filter (str, optional): Logging filter string (e.g., 'severity>=ERROR')
                    - timeRange (str, optional): Relative time range (e.g., '1h', '30m', '2d', '1w').
                      Ignored if startTime is provided.
                    - startTime (str, optional): Start time in RFC3339 format (e.g., '2025-11-20T10:00:00Z')
                    - endTime (str, optional): End time in RFC3339 format (e.g., '2025-11-20T12:00:00Z')

            Returns:
                dict: {"ok": True, "count": N} where count is the number of log entries matching the filter

            Note:
                Either filter, timeRange, or startTime/endTime must be provided.
            """
            # await require_mcp_auth_and_rate(ctx, rate_limiter)  # Disabled for stateless mode
            loop = asyncio.get_running_loop()
            count = await loop.run_in_executor(
                None,
                gcp_adapter.count_logs,
                GcpCountLogsInput.parse_or_error(
                    {
                        "project_id": params.get("projectId"),
                        "filter_": params.get("filter"),
                        "start_time": params.get("startTime"),
                        "end_time": params.get("endTime"),
                        "time_range": params.get("timeRange"),
                    },
                    "gcp",
                ),
            )
            return {"ok": True, "count": count}
        mcp.tool(name="gcp.countLogs", tags=["gcp"])(gcp_count_logs)

        async def gcp_search_logs_by_message(params: dict, ctx=None):
            """
            Search Google Cloud Logs by message content.

            Args:
                params: Dictionary containing:
                    - projectId (str, required): GCP project ID
                    - searchTerm (str, required): Text to search for in log messages
                    - timeRange (str, optional, default: "1h"): Relative time range (e.g., '1h', '30m', '2d', '1w').
                      Ignored if startTime is provided.
                    - limit (int, optional, default: 100, max: 1000): Maximum number of log entries to return
                    - caseSensitive (bool, optional, default: False): Whether search should be case sensitive
                    - filter (str, optional): Additional filter (e.g., 'resource.type="gce_instance"')
                    - startTime (str, optional): Start time in RFC3339 format (e.g., '2025-11-20T10:00:00Z')
                    - endTime (str, optional): End time in RFC3339 format (e.g., '2025-11-20T12:00:00Z')

            Returns:
                dict: {"ok": True, "summary": "...", "search_term": "...", "time_range": "...",
                      "case_sensitive": bool, "results": [...]} where results contain log entries with
                      timestamp, severity, message, resource, log_name, and full_entry.
            """
            # await require_mcp_auth_and_rate(ctx, rate_limiter)  # Disabled for stateless mode
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None,
                gcp_adapter.search_logs_by_message,
                GcpSearchLogsByMessageInput.parse_or_error(
                    {
                        "project_id": params.get("projectId"),
                        "search_term": params.get("searchTerm"),
                        "time_range": params.get("timeRange", "1h"),
                        "limit": params.get("limit", 100),
                        "case_sensitive": params.get("caseSensitive", False),
                        "filter_": params.get("filter"),
                        "start_time": params.get("startTime"),
                        "end_time": params.get("endTime"),
                    },
                    "gcp",
                ),
            )
            return {"ok": True, **result}
        mcp.tool(name="gcp.searchLogsByMessage", tags=["gcp"])(gcp_search_logs_by_message)

        async def gcp_list_log_sinks(params: dict, ctx=None):
            """
            List log sinks for a project, organization, folder, or billing account.

            Args:
                params: Dictionary containing:
                    - projectId (str, required): Project ID, organization ID, folder ID, or billing account ID
                    - parentType (str, optional, default: "project"): Type of parent resource.
                      Must be one of: 'project', 'organization', 'folder', or 'billingAccount'

            Returns:
                dict: {"ok": True, "sinks": [...], "count": N} where sinks is a list of log sink dictionaries
            """
            # await require_mcp_auth_and_rate(ctx, rate_limiter)  # Disabled for stateless mode
            loop = asyncio.get_running_loop()
            sinks = await loop.run_in_executor(
                None,
                gcp_adapter.list_log_sinks,
                GcpListLogSinksInput.parse_or_error(
                    {"project_id": params.get("projectId"), "parent_type": params.get("parentType", "project")},
                    "gcp",
                ),
            )
            return {"ok": True, "sinks": sinks, "count": len(sinks)}
        mcp.tool(name="gcp.listLogSinks", tags=["gcp"])(gcp_list_log_sinks)

        async def gcp_list_log_views(params: dict, ctx=None):
            """
            List log views for a project.

            Args:
                params: Dictionary containing:
                    - projectId (str, required): GCP project ID
                    - location (str, optional, default: "global"): Location of the log bucket
                      (e.g., 'global', 'us-central1')
                    - bucketId (str, optional): Log bucket ID. If not provided, lists views across all buckets

            Returns:
                dict: {"ok": True, "views": [...], "count": N} where views is a list of log view dictionaries
            """
            # await require_mcp_auth_and_rate(ctx, rate_limiter)  # Disabled for stateless mode
            loop = asyncio.get_running_loop()
            views = await loop.run_in_executor(
                None,
                gcp_adapter.list_log_views,
                GcpListLogViewsInput.parse_or_error(
                    {
                        "project_id": params.get("projectId"),
                        "location": params.get("location", "global"),
                        "bucket_id": params.get("bucketId"),
                    },
                    "gcp",
                ),
            )
            return {"ok": True, "views": views, "count": len(views)}
        mcp.tool(name="gcp.listLogViews", tags=["gcp"])(gcp_list_log_views)

        async def gcp_list_log_scopes(params: dict, ctx=None):
            """
            List log scopes for a folder, organization, or project.

            Args:
                params: Dictionary containing:
                    - parentId (str, required): GCP folder ID, organization ID, or project ID
                    - parentType (str, optional, default: "folder"): Type of parent resource.
                      Must be one of: 'folder', 'organization', or 'project'
                    - location (str, optional, default: "global"): Location (e.g., 'global', 'us-central1')

            Returns:
                dict: {"ok": True, "scopes": [...], "count": N} where scopes is a list of log scope dictionaries
            """
            # await require_mcp_auth_and_rate(ctx, rate_limiter)  # Disabled for stateless mode
            loop = asyncio.get_running_loop()
            scopes = await loop.run_in_executor(
                None,
                gcp_adapter.list_log_scopes,
                GcpListLogScopesInput.parse_or_error(
                    {
                        "parent_id": params.get("parentId"),
                        "parent_type": params.get("parentType", "folder"),
                        "location": params.get("location", "global"),
                    },
                    "gcp",
                ),
            )
            return {"ok": True, "scopes": scopes, "count": len(scopes)}
        mcp.tool(name="gcp.listLogScopes", tags=["gcp"])(gcp_list_log_scopes)

        async def gcp_list_log_names(params: dict, ctx=None):
            """
            List log names (log types) for a project.

            Args:
                params: Dictionary containing:
                    - projectId (str, required): GCP project ID
                    - pageSize (int, optional, default: 1000): Number of log names to retrieve per page

            Returns:
                dict: {"ok": True, "logNames": [...], "count": N} where logNames is a list of log name strings
                      (e.g., "projects/xxx/logs/cloudaudit.googleapis.com")
            """
            # await require_mcp_auth_and_rate(ctx, rate_limiter)  # Disabled for stateless mode
            loop = asyncio.get_running_loop()
            log_names = await loop.run_in_executor(
                None,
                gcp_adapter.list_log_names,
                GcpListLogNamesInput.parse_or_error(
                    {"project_id": params.get("projectId"), "page_size": params.get("pageSize", 1000)},
                    "gcp",
                ),
            )
            return {"ok": True, "logNames": log_names, "count": len(log_names)}
        mcp.tool(name="gcp.listLogNames", tags=["gcp"])(gcp_list_log_names)

        async def gcp_list_log_buckets(params: dict, ctx=None):
            """
            List log buckets for a project in a specific location.

            Args:
                params: Dictionary containing:
                    - projectId (str, required): GCP project ID
                    - location (str, optional, default: "global"): Location of the log buckets
                      (e.g., 'global', 'us-central1')

            Returns:
                dict: {"ok": True, "buckets": [...], "count": N} where buckets is a list of log bucket dictionaries
            """
            # await require_mcp_auth_and_rate(ctx, rate_limiter)  # Disabled for stateless mode
            loop = asyncio.get_running_loop()
            buckets = await loop.run_in_executor(
                None,
                gcp_adapter.list_log_buckets,
                GcpListLogBucketsInput.parse_or_error(
                    {"project_id": params.get("projectId"), "location": params.get("location", "global")},
                    "gcp",
                ),
            )
            return {"ok": True, "buckets": buckets, "count": len(buckets)}
        mcp.tool(name="gcp.listLogBuckets", tags=["gcp"])(gcp_list_log_buckets)
        gcp_available = True
        logger.info("GCP adapter registered successfully")
    except Exception as ex:
        gcp_available = False
        logger.warning(f"GCP adapter not available: {ex}")

    # Grafana tools
    if settings.GRAFANA_BASE_URL and (settings.GRAFANA_API_KEY or (settings.GRAFANA_USERNAME and settings.GRAFANA_PASSWORD)):
        grafana_adapter = GrafanaAdapter(None)

        async def grafana_get_dashboards(params: dict, ctx=None):
            """List Grafana dashboards (supports filters).

            Optional parameters:
                query: Search query string.
                folderIds: Array of folder IDs.
                tags: Array of tag strings.
                starred: Boolean filter for starred dashboards.
                page: Page number.
                limit: Results limit.
            """
            # await require_mcp_auth_and_rate(ctx, rate_limiter)  # Disabled for stateless mode
            dashboards = await grafana_adapter.list_dashboards(
                GrafanaListDashboardsInput.parse_or_error(params, "grafana")
            )
            return {"ok": True, "dashboards": dashboards}

        async def grafana_get_dashboard(params: dict, ctx=None):
            """Get a specific Grafana dashboard by UID.

            Required parameters:
                uid: Dashboard UID.
            """
            # await require_mcp_auth_and_rate(ctx, rate_limiter)  # Disabled for stateless mode
            dashboard = await grafana_adapter.get_dashboard(
                GrafanaGetDashboardInput.parse_or_error(params, "grafana")
            )
            return {"ok": True, "dashboard": dashboard}

        async def grafana_create_dashboard(params: dict, ctx=None):
            """Create a new Grafana dashboard.

            Required parameters:
                dashboard: Dashboard configuration object.
            """
            # await require_mcp_auth_and_rate(ctx, rate_limiter)  # Disabled for stateless mode
            result = await grafana_adapter.create_dashboard(
                GrafanaCreateDashboardInput.parse_or_error(params, "grafana")
            )
            return {"ok": True, "result": result}

        async def grafana_get_dashboard_by_uid(params: dict, ctx=None):
            """Get full dashboard details by UID.

            Required parameters:
                uid: Dashboard UID.
            """
            # await require_mcp_auth_and_rate(ctx, rate_limiter)  # Disabled for stateless mode
            dashboard = await grafana_adapter.get_dashboard_by_uid(
                GrafanaGetDashboardInput.parse_or_error(params, "grafana")
            )
            return {"ok": True, "dashboard": dashboard}

        async def grafana_get_dashboard_panel_queries(params: dict, ctx=None):
            """Get queries from dashboard panels.

            Required parameters:
                uid: Dashboard UID.
            """
            # await require_mcp_auth_and_rate(ctx, rate_limiter)  # Disabled for stateless mode
            queries = await grafana_adapter.get_dashboard_panel_queries(
                GrafanaGetDashboardInput.parse_or_error(params, "grafana")
            )
            return {"ok": True, "queries": queries}

        async def grafana_query_prometheus(params: dict, ctx=None):
            """Execute Prometheus queries for metrics (with analysis).

            Required parameters:
                expr: PromQL query expression.

            Optional parameters:
                time: Unix timestamp in seconds.
                datasourceUid: Datasource UID.
            """
            # await require_mcp_auth_and_rate(ctx, rate_limiter)  # Disabled for stateless mode
            res = await grafana_adapter.query_prometheus(
                GrafanaQueryPrometheusInput.parse_or_error(
                    {
                        "expr": params.get("expr"),
                        "time": params.get("time"),
                        "datasource_uid": params.get("datasourceUid"),
                    },
                    "grafana",
                )
            )
            return {"ok": True, "result": res}

        async def grafana_execute_range_query(params: dict, ctx=None):
            """Execute time-range queries.

            Required parameters:
                expr: PromQL query expression.
                start_ms: Start time in milliseconds.
                end_ms: End time in milliseconds.

            Optional parameters:
                step: Query resolution step width (default: '60s').
                datasourceUid: Datasource UID.
            """
            # await require_mcp_auth_and_rate(ctx, rate_limiter)  # Disabled for stateless mode

            # Handle time conversion - check if we have time strings or millisecond values
            start_param = params.get("start_ms")
            end_param = params.get("end_ms")

            # If the parameters are strings, they're time strings that need conversion
            if isinstance(start_param, str):
                start_data = convert_time_to_ms(start_param)
                start_ms = start_data.get("start_ms") or start_data.get("end_ms")
            else:
                start_ms = start_param

            if isinstance(end_param, str):
                end_data = convert_time_to_ms(end_param)
                end_ms = end_data.get("end_ms") or end_data.get("start_ms")
            else:
                end_ms = end_param


            # Ensure we have valid integer timestamps
            if start_ms is None or end_ms is None:
                raise ValueError("Both start_ms and end_ms (or start_time and end_time) must be provided")

            # Convert to int if they're strings
            start_ms = int(start_ms)
            end_ms = int(end_ms)

            res = await grafana_adapter.execute_range_query(
                GrafanaExecuteRangeQueryInput.parse_or_error(
                    {
                        "expr": params.get("expr"),
                        "start_ms": start_ms,
                        "end_ms": end_ms,
                        "step": params.get("step", "60s"),
                        "datasource_uid": params.get("datasourceUid"),
                    },
                    "grafana",
                )
            )
            return {"ok": True, "result": res}

        mcp.tool(name="grafana.getDashboards")(grafana_get_dashboards)
        mcp.tool(name="grafana.getDashboard")(grafana_get_dashboard)
        mcp.tool(name="grafana.createDashboard")(grafana_create_dashboard)
        mcp.tool(name="grafana.getDashboardByUid")(grafana_get_dashboard_by_uid)
        mcp.tool(name="grafana.getDashboardPanelQueries")(grafana_get_dashboard_panel_queries)
        mcp.tool(name="grafana.queryPrometheus")(grafana_query_prometheus)
        mcp.tool(name="grafana.executeRangeQuery")(grafana_execute_range_query)

        async def grafana_list_datasources(params: dict, ctx=None):
            """List Grafana datasources.

            No required parameters.
            """
            # await require_mcp_auth_and_rate(ctx, rate_limiter)  # Disabled for stateless mode
            dss = await grafana_adapter.list_datasources()
            return {"ok": True, "datasources": dss}

        async def grafana_get_default_prometheus_uid(params: dict, ctx=None):
            """Get default Prometheus datasource UID if available.

            No required parameters.
            """
            # await require_mcp_auth_and_rate(ctx, rate_limiter)  # Disabled for stateless mode
            uid = await grafana_adapter.get_default_prometheus_uid()
            return {"ok": True, "uid": uid}

        mcp.tool(name="grafana.listDatasources")(grafana_list_datasources)
        mcp.tool(name="grafana.getDefaultPrometheusUid")(grafana_get_default_prometheus_uid)

    # OpenSearch
    if settings.OPENSEARCH_URL:
        opensearch_adapter = OpenSearchAdapter(None)

        async def opensearch_list_indices(params: dict, ctx=None):
            """List all indices or get info for a specific index.

            Optional parameters:
                index: Index name.
            """
            return {"ok": True, "indices": await opensearch_adapter.list_indices(OpenSearchIndexOptionalInput.parse_or_error(params, "opensearch"))}

        async def opensearch_get_index_mapping(params: dict, ctx=None):
            """Get mapping and settings for an index.

            Required parameters:
                index: Index name.
            """
            return {"ok": True, **(await opensearch_adapter.get_index_mapping(OpenSearchIndexInput.parse_or_error(params, "opensearch")))}

        async def opensearch_search_index(params: dict, ctx=None):
            """Search an index using OpenSearch Query DSL.

            Required parameters:
                index: Index name.
                body: OpenSearch Query DSL object.
            """
            return {"ok": True, "result": await opensearch_adapter.search_index(OpenSearchSearchInput.parse_or_error({"index": params.get("index"), "query": params.get("body")}, "opensearch"))}

        async def opensearch_search_with_time_range(params: dict, ctx=None):
            """Search an index with time-based filtering. Supports 'now-1h', RFC3339, or Unix timestamps.

            Required parameters:
                index: Index name.
                time_field: Timestamp field name (e.g., '@timestamp').
                start_time: Start time.
                end_time: End time.

            Optional parameters:
                matches: Dict of {field: value} for match queries.
                kubernetes_host: Kubernetes host/node name to filter by.
                additional_query: Extra query clauses.
                size: Result limit.
            """
            return {"ok": True, "result": await opensearch_adapter.search_with_time_range(OpenSearchSearchWithTimeRangeInput.parse_or_error(params, "opensearch"))}

        async def opensearch_get_shards(params: dict, ctx=None):
            """Get shard info for an index.

            Required parameters:
                index: Index name.
            """
            return {"ok": True, "shards": await opensearch_adapter.get_shards(OpenSearchIndexInput.parse_or_error(params, "opensearch"))}

        async def opensearch_cluster_health(params: dict, ctx=None):
            """Get health of the cluster or a specific index.

            Optional parameters:
                index: Index name.
            """
            return {"ok": True, "health": await opensearch_adapter.cluster_health(OpenSearchIndexOptionalInput.parse_or_error(params, "opensearch"))}

        async def opensearch_count(params: dict, ctx=None):
            """Count documents matching a query.

            Optional parameters:
                index: Index name.
                body: Query body.
            """
            return {"ok": True, **(await opensearch_adapter.count(OpenSearchCountInput.parse_or_error(params, "opensearch")))}

        async def opensearch_explain(params: dict, ctx=None):
            """Explain why a document matches/doesn't match a query.

            Required parameters:
                index: Index name.
                id: Document ID.
                body: Query body.
            """
            return {"ok": True, "explanation": await opensearch_adapter.explain(OpenSearchExplainInput.parse_or_error(params, "opensearch"))}

        async def opensearch_msearch(params: dict, ctx=None):
            """Multi-search (batch search) in OpenSearch. Body must be NDJSON string.

            Required parameters:
                body: NDJSON string.

            Optional parameters:
                index: Index name.
            """
            return {"ok": True, "result": await opensearch_adapter.msearch(OpenSearchMsearchInput.parse_or_error(params, "opensearch"))}

        async def opensearch_get_cluster_state(params: dict, ctx=None):
            """Get cluster state (nodes, settings, etc).

            Optional parameters:
                metric: Metric name.
                index: Index name.
            """
            return {"ok": True, "state": await opensearch_adapter.get_cluster_state(OpenSearchClusterStateInput.parse_or_error(params, "opensearch"))}

        async def opensearch_get_segments(params: dict, ctx=None):
            """Get Lucene segment info for indices.

            Optional parameters:
                index: Index name.
            """
            return {"ok": True, "segments": await opensearch_adapter.get_segments(OpenSearchIndexOptionalInput.parse_or_error(params, "opensearch"))}

        async def opensearch_cat_nodes(params: dict, ctx=None):
            """Get node metrics (CPU, RAM, disk, etc).

            Optional parameters:
                metrics: Metrics string.
            """
            return {"ok": True, "nodes": await opensearch_adapter.cat_nodes(OpenSearchCatNodesInput.parse_or_error(params, "opensearch"))}

        async def opensearch_get_nodes(params: dict, ctx=None):
            """Get detailed node info (JVM, OS, plugins, etc).

            Optional parameters:
                node_id: Node ID.
                metric: Metric name.
            """
            return {"ok": True, "nodes": await opensearch_adapter.get_nodes(OpenSearchGetNodesInput.parse_or_error(params, "opensearch"))}

        async def opensearch_get_index_info(params: dict, ctx=None):
            """Get detailed index info (mappings, settings, aliases).

            Required parameters:
                index: Index name.
            """
            return {"ok": True, "info": await opensearch_adapter.get_index_info(OpenSearchIndexInput.parse_or_error(params, "opensearch"))}

        async def opensearch_get_index_stats(params: dict, ctx=None):
            """Get index stats (docs, store size, performance).

            Required parameters:
                index: Index name.

            Optional parameters:
                metric: Metric name.
            """
            return {"ok": True, "stats": await opensearch_adapter.get_index_stats(OpenSearchIndexMetricInput.parse_or_error(params, "opensearch"))}

        async def opensearch_get_query_insights(params: dict, ctx=None):
            """Get top query insights.

            No required parameters.
            """
            return {"ok": True, "insights": await opensearch_adapter.get_query_insights()}

        async def opensearch_get_nodes_hot_threads(params: dict, ctx=None):
            """Get hot threads info.

            No required parameters.
            """
            return {"ok": True, "hot_threads": await opensearch_adapter.get_nodes_hot_threads()}

        async def opensearch_get_allocation(params: dict, ctx=None):
            """Get shard allocation info.

            No required parameters.
            """
            return {"ok": True, "allocation": await opensearch_adapter.get_allocation()}

        async def opensearch_get_long_running_tasks(params: dict, ctx=None):
            """Get long-running tasks in the cluster.

            Optional parameters:
                limit: Task limit (default: 10).
            """
            return {"ok": True, "tasks": await opensearch_adapter.get_long_running_tasks(OpenSearchLongRunningTasksInput.parse_or_error({"limit": params.get("limit", 10)}, "opensearch"))}

        async def opensearch_get_nodes_stats(params: dict, ctx=None):
            """Get nodes statistics.

            Optional parameters:
                node_id: Node ID.
                metric: Metric name.
            """
            return {"ok": True, "nodes_stats": await opensearch_adapter.get_nodes_stats(OpenSearchGetNodesInput.parse_or_error(params, "opensearch"))}

        async def opensearch_get_cluster_stats(params: dict, ctx=None):
            """Get cluster statistics.

            No required parameters.
            """
            return {"ok": True, "cluster_stats": await opensearch_adapter.get_cluster_stats()}

        async def opensearch_get_tasks(params: dict, ctx=None):
            """Get tasks information.

            Optional parameters:
                task_id: Task ID.
            """
            return {"ok": True, "tasks": await opensearch_adapter.get_tasks(OpenSearchTasksInput.parse_or_error(params, "opensearch"))}

        # New methods based on your examples
        async def opensearch_get_aliases(params: dict, ctx=None):
            """Get index aliases.

            Optional parameters:
                index: Index name.
            """
            return {"ok": True, "aliases": await opensearch_adapter.get_aliases(OpenSearchIndexOptionalInput.parse_or_error(params, "opensearch"))}

        async def opensearch_get_templates(params: dict, ctx=None):
            """Get index templates.

            Optional parameters:
                template_name: Template name.
            """
            return {"ok": True, "templates": await opensearch_adapter.get_templates(OpenSearchTemplatesInput.parse_or_error(params, "opensearch"))}

        async def opensearch_get_mapping(params: dict, ctx=None):
            """Get mapping for all indices or a specific index.

            Optional parameters:
                index: Index name.
            """
            return {"ok": True, "mapping": await opensearch_adapter.get_mapping(OpenSearchIndexOptionalInput.parse_or_error(params, "opensearch"))}

        # async def opensearch_create_template(params: dict, ctx=None):
        #     return {"ok": True, "result": await opensearch_adapter.create_template(params["template_name"], params["template_body"])}

        # async def opensearch_delete_template(params: dict, ctx=None):
        #     return {"ok": True, "result": await opensearch_adapter.delete_template(params["template_name"])}

        async def opensearch_create_alias(params: dict, ctx=None):
            """Create an alias for an index.

            Required parameters:
                index: Index name.
                alias: Alias name.
            """
            return {"ok": True, "result": await opensearch_adapter.create_alias(OpenSearchAliasInput.parse_or_error(params, "opensearch"))}

        # async def opensearch_delete_alias(params: dict, ctx=None):
        #     return {"ok": True, "result": await opensearch_adapter.delete_alias(params["index"], params["alias"])}

        # async def opensearch_bulk_index(params: dict, ctx=None):
        #     return {"ok": True, "result": await opensearch_adapter.bulk_index(params["body"])}

        async def opensearch_get_document(params: dict, ctx=None):
            """Get a document by ID.

            Required parameters:
                index: Index name.
                id: Document ID.
            """
            return {"ok": True, "document": await opensearch_adapter.get_document(OpenSearchDocumentInput.parse_or_error(params, "opensearch"))}

        # async def opensearch_index_document(params: dict, ctx=None):
        #     return {"ok": True, "result": await opensearch_adapter.index_document(params["index"], params["body"], params.get("id"))}

        # async def opensearch_update_document(params: dict, ctx=None):
        #     return {"ok": True, "result": await opensearch_adapter.update_document(params["index"], params["id"], params["body"])}

        # async def opensearch_delete_document(params: dict, ctx=None):
        #     return {"ok": True, "result": await opensearch_adapter.delete_document(params["index"], params["id"])}

        mcp.tool(name="opensearch.listIndices")(opensearch_list_indices)
        mcp.tool(name="opensearch.getIndexMapping")(opensearch_get_index_mapping)
        mcp.tool(name="opensearch.searchIndex")(opensearch_search_index)
        mcp.tool(name="opensearch.searchWithTimeRange")(opensearch_search_with_time_range)
        mcp.tool(name="opensearch.getShards")(opensearch_get_shards)
        mcp.tool(name="opensearch.clusterHealth")(opensearch_cluster_health)
        mcp.tool(name="opensearch.count")(opensearch_count)
        mcp.tool(name="opensearch.explain")(opensearch_explain)
        mcp.tool(name="opensearch.msearch")(opensearch_msearch)
        mcp.tool(name="opensearch.getClusterState")(opensearch_get_cluster_state)
        mcp.tool(name="opensearch.getSegments")(opensearch_get_segments)
        mcp.tool(name="opensearch.catNodes")(opensearch_cat_nodes)
        mcp.tool(name="opensearch.getNodes")(opensearch_get_nodes)
        mcp.tool(name="opensearch.getIndexInfo")(opensearch_get_index_info)
        mcp.tool(name="opensearch.getIndexStats")(opensearch_get_index_stats)
        mcp.tool(name="opensearch.getQueryInsights")(opensearch_get_query_insights)
        mcp.tool(name="opensearch.getNodesHotThreads")(opensearch_get_nodes_hot_threads)
        mcp.tool(name="opensearch.getAllocation")(opensearch_get_allocation)
        mcp.tool(name="opensearch.getLongRunningTasks")(opensearch_get_long_running_tasks)
        mcp.tool(name="opensearch.getNodesStats")(opensearch_get_nodes_stats)
        mcp.tool(name="opensearch.getClusterStats")(opensearch_get_cluster_stats)
        mcp.tool(name="opensearch.getTasks")(opensearch_get_tasks)

        # Register new methods
        mcp.tool(name="opensearch.getAliases")(opensearch_get_aliases)
        mcp.tool(name="opensearch.getTemplates")(opensearch_get_templates)
        mcp.tool(name="opensearch.getMapping")(opensearch_get_mapping)
        # mcp.tool(name="opensearch.createTemplate")(opensearch_create_template)
        # mcp.tool(name="opensearch.deleteTemplate")(opensearch_delete_template)
        mcp.tool(name="opensearch.createAlias")(opensearch_create_alias)
        # mcp.tool(name="opensearch.deleteAlias")(opensearch_delete_alias)
        # mcp.tool(name="opensearch.bulkIndex")(opensearch_bulk_index)
        mcp.tool(name="opensearch.getDocument")(opensearch_get_document)
        # mcp.tool(name="opensearch.indexDocument")(opensearch_index_document)
        # mcp.tool(name="opensearch.updateDocument")(opensearch_update_document)
        # mcp.tool(name="opensearch.deleteDocument")(opensearch_delete_document)

    # Mimir tools
    if settings.MIMIR_URL:
        mimir_adapter = MimirAdapter(None)

        async def mimir_query_instant(params: dict, ctx=None):
            """Execute an instant query against Mimir (Prometheus-compatible).

            Required parameters:
                query: PromQL query string.

            Optional parameters:
                time: RFC3339 timestamp or Unix timestamp.
            """
            # await require_mcp_auth_and_rate(ctx, rate_limiter)  # Disabled for stateless mode
            return {"ok": True, "result": await mimir_adapter.query_instant(MimirQueryInstantInput.parse_or_error(params, "mimir"))}

        async def mimir_query_range(params: dict, ctx=None):
            """Execute a range query against Mimir (Prometheus-compatible).

            Required parameters:
                query: PromQL query string.
                startTime: Start time in RFC3339 format.
                endTime: End time in RFC3339 format.

            Optional parameters:
                step: Query resolution step width (default: '15s').
            """
            return {"ok": True, "result": await mimir_adapter.query_range(MimirQueryRangeInput.parse_or_error({"query": params.get("query"), "start_time": params.get("startTime"), "end_time": params.get("endTime"), "step": params.get("step", "15s")}, "mimir"))}

        async def mimir_get_series(params: dict, ctx=None):
            """Get series metadata from Mimir.

            Required parameters:
                match: List of series selectors.

            Optional parameters:
                startTime: Start time in RFC3339 format.
                endTime: End time in RFC3339 format.
            """
            return {"ok": True, "result": await mimir_adapter.get_series(MimirSeriesInput.parse_or_error({"match": params.get("match"), "start_time": params.get("startTime"), "end_time": params.get("endTime")}, "mimir"))}

        async def mimir_get_labels(params: dict, ctx=None):
            """Get label names from Mimir.

            Optional parameters:
                match: List of series selectors.
                startTime: Start time in RFC3339 format.
                endTime: End time in RFC3339 format.
            """
            return {"ok": True, "result": await mimir_adapter.get_labels(MimirLabelsInput.parse_or_error({"match": params.get("match"), "start_time": params.get("startTime"), "end_time": params.get("endTime")}, "mimir"))}

        async def mimir_get_label_values(params: dict, ctx=None):
            """Get label values for a specific label name.

            Required parameters:
                labelName: Name of the label.

            Optional parameters:
                match: List of series selectors.
                startTime: Start time in RFC3339 format.
                endTime: End time in RFC3339 format.
            """
            return {"ok": True, "result": await mimir_adapter.get_label_values(MimirLabelValuesInput.parse_or_error({"label_name": params.get("labelName"), "match": params.get("match"), "start_time": params.get("startTime"), "end_time": params.get("endTime")}, "mimir"))}

        async def mimir_get_metadata(params: dict, ctx=None):
            """Get metric metadata from Mimir.

            Optional parameters:
                match: List of series selectors.
                startTime: Start time in RFC3339 format.
                endTime: End time in RFC3339 format.
            """
            return {"ok": True, "result": await mimir_adapter.get_metadata(
                MimirLabelsInput.parse_or_error(
                    {
                        "match": params.get("match"),
                        "start_time": params.get("startTime"),
                        "end_time": params.get("endTime"),
                    },
                    "mimir",
                )
            )}

        async def mimir_get_targets(params: dict, ctx=None):
            """Get active targets from Mimir.

            No required parameters.
            """
            return {"ok": True, "result": await mimir_adapter.get_targets()}

        async def mimir_get_alerts(params: dict, ctx=None):
            """Get active alerts from Mimir.

            No required parameters.
            """
            return {"ok": True, "result": await mimir_adapter.get_alerts()}

        async def mimir_get_rules(params: dict, ctx=None):
            """Get recording and alerting rules from Mimir.

            No required parameters.
            """
            return {"ok": True, "result": await mimir_adapter.get_rules()}

        async def mimir_get_status(params: dict, ctx=None):
            return {"ok": True, "result": await mimir_adapter.get_status()}

        async def mimir_get_tenant_stats(params: dict, ctx=None):
            return {"ok": True, "result": await mimir_adapter.get_tenant_stats()}

        async def mimir_get_blocks(params: dict, ctx=None):
            return {"ok": True, "result": await mimir_adapter.get_blocks()}

        async def mimir_get_compactor_status(params: dict, ctx=None):
            return {"ok": True, "result": await mimir_adapter.get_compactor_status()}

        async def mimir_get_ingester_status(params: dict, ctx=None):
            return {"ok": True, "result": await mimir_adapter.get_ingester_status()}

        async def mimir_get_store_gateway_status(params: dict, ctx=None):
            return {"ok": True, "result": await mimir_adapter.get_store_gateway_status()}

        async def mimir_get_distributor_status(params: dict, ctx=None):
            return {"ok": True, "result": await mimir_adapter.get_distributor_status()}

        mcp.tool(name="mimir.queryInstant")(mimir_query_instant)
        mcp.tool(name="mimir.queryRange")(mimir_query_range)
        mcp.tool(name="mimir.getSeries")(mimir_get_series)
        mcp.tool(name="mimir.getLabels")(mimir_get_labels)
        mcp.tool(name="mimir.getLabelValues")(mimir_get_label_values)
        mcp.tool(name="mimir.getMetadata")(mimir_get_metadata)
        mcp.tool(name="mimir.getTargets")(mimir_get_targets)
        mcp.tool(name="mimir.getAlerts")(mimir_get_alerts)
        mcp.tool(name="mimir.getRules")(mimir_get_rules)
        # Commented out - these endpoints return 404 in this Mimir instance
        # mcp.tool(name="mimir.getStatus")(mimir_get_status)
        # mcp.tool(name="mimir.getTenantStats")(mimir_get_tenant_stats)
        # mcp.tool(name="mimir.getBlocks")(mimir_get_blocks)
        # mcp.tool(name="mimir.getCompactorStatus")(mimir_get_compactor_status)
        # mcp.tool(name="mimir.getIngesterStatus")(mimir_get_ingester_status)
        # mcp.tool(name="mimir.getStoreGatewayStatus")(mimir_get_store_gateway_status)
        # mcp.tool(name="mimir.getDistributorStatus")(mimir_get_distributor_status)

    # Kubernetes tools
    logger.info("=" * 80)
    logger.info("Kubernetes Tools Registration")
    logger.info("=" * 80)
    logger.info("Checking K8S_ENABLED setting: %s", settings.K8S_ENABLED)

    if settings.K8S_ENABLED:
        logger.info("K8S_ENABLED is True - proceeding with Kubernetes adapter initialization")
        logger.info("Loading K8S_TOOL_SPECS...")
        logger.info("  Total tool specs available: %d", len(K8S_TOOL_SPECS))

        k8s_adapter = None
        adapter_error = None
        try:
            logger.info("Initializing KubernetesAdapter...")
            logger.debug("  Tenant ID: None (default)")
            logger.debug("  K8S_KUBECONFIG: %s", settings.K8S_KUBECONFIG or "Not set (will use default)")
            logger.debug("  K8S_CONTEXT: %s", settings.K8S_CONTEXT or "Not set (will use current-context)")
            logger.debug("  K8S_NAMESPACE: %s", settings.K8S_NAMESPACE or "default")
            logger.debug("  K8S_VERIFY_SSL: %s", settings.K8S_VERIFY_SSL)
            logger.debug("  K8S_TIMEOUT: %s seconds", settings.K8S_TIMEOUT)

            k8s_adapter = KubernetesAdapter(None)
            logger.info("✓ Kubernetes adapter initialized successfully")
            logger.info("  Adapter mode: read-only (compatible with container.viewer role)")
            logger.info("  All operations are read-only (list, get, describe) - no create, update, or delete")
        except ProviderError as exc:
            adapter_error = str(exc)
            logger.error("=" * 80)
            logger.error("Kubernetes Adapter Initialization Failed (ProviderError)")
            logger.error("=" * 80)
            logger.error("Error type: ProviderError")
            logger.error("Error message: %s", str(exc))
            logger.error("")
            logger.error("This is typically caused by:")
            logger.error("  1. Missing or invalid kubeconfig file")
            logger.error("  2. Kubernetes cluster not accessible")
            logger.error("  3. Authentication/authorization issues")
            logger.error("")
            logger.error("For GKE clusters, ensure:")
            logger.error("  1. Kubeconfig is configured: gcloud container clusters get-credentials CLUSTER_NAME --zone ZONE --project PROJECT_ID")
            logger.error("  2. ADC is set up: gcloud auth application-default login")
            logger.error("  3. Your account has 'container.viewer' role or equivalent read permissions")
            logger.error("")
            logger.error("Check your configuration:")
            logger.error("  K8S_KUBECONFIG: %s", settings.K8S_KUBECONFIG or "Not set")
            logger.error("  K8S_CONTEXT: %s", settings.K8S_CONTEXT or "Not set")
        except Exception as exc:
            adapter_error = str(exc)
            logger.error("=" * 80)
            logger.error("Kubernetes Adapter Initialization Failed (Unexpected Error)")
            logger.error("=" * 80)
            logger.error("Error type: %s", type(exc).__name__)
            logger.error("Error message: %s", str(exc))
            import traceback
            logger.debug("Full traceback:\n%s", traceback.format_exc())
            logger.error("This is an unexpected error - check server logs for details")

        if k8s_adapter is not None:
            logger.info("=" * 80)
            logger.info("Registering Kubernetes Tools")
            logger.info("=" * 80)
            logger.info("K8s adapter is available - proceeding with tool registration")
            logger.info("Total tool specs to register: %d", len(K8S_TOOL_SPECS))

            def build_k8s_handler(spec):
                tool_name = spec.get("tool", "UNKNOWN")
                logger.debug("Building handler for tool: %s", tool_name)

                # Validate spec is a dict
                if not isinstance(spec, dict):
                    logger.warning("k8s: invalid spec type %s (expected dict) for tool %s, skipping",
                                 type(spec).__name__, tool_name)
                    return None

                if "method" not in spec or "tool" not in spec:
                    logger.warning("k8s: spec missing required fields (method or tool) for tool %s, skipping", tool_name)
                    return None

                method_name = spec.get("method")
                logger.debug("  Method name: %s", method_name)
                method = getattr(k8s_adapter, method_name, None)
                if method is None:
                    logger.warning("k8s: missing adapter method '%s' for tool %s, skipping", method_name, tool_name)
                    return None

                logger.debug("  Method found: %s", method_name)
                logger.debug("  Description: %s", spec.get("description", "No description")[:100])

                # Build description first (before creating handler)
                req_params = spec.get("required", [])
                inputs = spec.get("inputs", {})
                logger.debug("  Required parameters: %s", req_params or "None")
                logger.debug("  Optional parameters: %s", [k for k in inputs.keys() if k not in req_params] or "None")

                desc_lines = [spec.get("description", "Kubernetes tool.")]
                if req_params:
                    desc_lines.append("\nRequired parameters:")
                    for param in req_params:
                        param_desc = inputs.get(param, "string")
                        desc_lines.append(f"    {param}: {param_desc}")
                if inputs:
                    optional = [k for k in inputs.keys() if k not in req_params]
                    if optional:
                        desc_lines.append("\nOptional parameters:")
                        for param in optional:
                            desc_lines.append(f"    {param}: {inputs[param]}")
                tool_description = "\n".join(desc_lines)
                logger.debug("  Tool description built (%d characters)", len(tool_description))

                # Create handler function with docstring set inline
                # FastMCP reads handler.__doc__ for tool descriptions
                # We set it immediately after function creation to ensure it's available
                async def handler(params: dict = None, ctx=None):
                    try:
                        logger.info("K8s tool invoked: %s", tool_name)
                        logger.debug("  Raw params: %s", params)
                    except Exception:
                        pass  # Don't fail if logging fails

                    # Handle nested params structure from FastMCP (arguments.params)
                    # FastMCP passes arguments directly to handler, which may contain nested "params"
                    if params is None:
                        actual_params = {}
                        logger.debug("  Params is None, using empty dict")
                    elif isinstance(params, dict):
                        # FastMCP JSON-RPC format: {"arguments": {"params": {...}}}
                        # The handler receives the "arguments" dict, which may contain "params"
                        if "params" in params:
                            # If "params" key exists, use it (handles nested structure)
                            nested = params.get("params")
                            if isinstance(nested, dict):
                                actual_params = nested
                                logger.debug("  Using nested params from params['params']")
                            else:
                                # If params["params"] is not a dict, use params directly
                                actual_params = params
                                logger.debug("  params['params'] is not a dict, using params directly")
                        else:
                            # No "params" key, use params directly
                            actual_params = params
                            logger.debug("  No 'params' key, using params directly")
                    else:
                        actual_params = {}
                        logger.warning("  Params is not a dict (type: %s), using empty dict", type(params).__name__)

                    logger.debug("  Resolved actual_params: %s", actual_params)

                    # Map request payload keys to adapter kwargs.
                    logger.debug("  Mapping parameters for schema validation...")
                    raw_kwargs = {}
                    param_map = spec.get("param_map", {})
                    logger.debug("  Parameter map: %s", param_map)

                    for arg, payload_key in param_map.items():
                        # Try actual_params first, then fall back to original params
                        value = None
                        if payload_key in actual_params:
                            value = actual_params[payload_key]
                            logger.debug("    Found '%s' (%s) in actual_params: %s", payload_key, arg, value)
                        elif isinstance(params, dict) and payload_key in params:
                            value = params[payload_key]
                            logger.debug("    Found '%s' (%s) in original params: %s", payload_key, arg, value)

                        # Skip empty strings so required fields fail validation.
                        if value is not None and value != "":
                            raw_kwargs[arg] = value
                            logger.debug("      Mapped '%s' -> '%s': %s", payload_key, arg, value)

                    # Validate and coerce via Pydantic schema like other adapters.
                    input_schema = get_k8s_input_schema(method_name)
                    validated_input = input_schema.parse_or_error(raw_kwargs, "k8s")
                    kwargs = validated_input.model_dump(exclude_none=True)
                    logger.debug("  Validated kwargs: %s", kwargs)

                    logger.info("  Executing adapter method: %s", method_name)
                    logger.debug("  Method kwargs: %s", kwargs)

                    # Execute adapter method
                    try:
                        result = await k8s_adapter.execute_with_input(method_name, validated_input)
                        logger.info("  ✓ Method executed successfully")
                        logger.debug("  Result type: %s", type(result).__name__)
                        if isinstance(result, dict):
                            logger.debug("  Result keys: %s", list(result.keys())[:10])
                            if "ok" in result:
                                logger.debug("  Result ok status: %s", result.get("ok"))
                    except ProviderError as pe:
                        logger.error("  ✗ ProviderError in %s: %s", tool_name, str(pe))
                        logger.debug("  ProviderError status: %s", getattr(pe, 'status', 'unknown'))
                        raise  # Re-raise ProviderError as-is
                    except Exception as exc:
                        logger.error("  ✗ Unexpected error in %s", tool_name)
                        logger.exception("  Exception details:")
                        raise ProviderError("k8s", f"Error executing {spec['tool']}: {str(exc)}", status=500)

                    # Format response
                    logger.debug("  Formatting response...")
                    # Check if result already has an 'ok' field (e.g., from graceful 404 handling)
                    if isinstance(result, dict) and "ok" in result:
                        # Preserve the ok status from adapter (e.g., ok: False for 404s)
                        logger.debug("    Result already has 'ok' field: %s", result.get("ok"))
                        logger.info("  ✓ Response formatted (preserved existing ok status)")
                        return result

                    # Format response normally
                    if spec.get("passthrough"):
                        payload = result if isinstance(result, dict) else {"result": result}
                        logger.debug("    Using passthrough format")
                    elif spec.get("result_key"):
                        payload = {spec["result_key"]: result}
                        logger.debug("    Using result_key format: %s", spec["result_key"])
                    elif isinstance(result, dict):
                        payload = result
                        logger.debug("    Using result as-is (dict)")
                    else:
                        payload = {"result": result}
                        logger.debug("    Wrapping result in 'result' key")

                    logger.info("  ✓ Response formatted successfully")
                    return {"ok": True, **payload}

                # CRITICAL: Set docstring immediately after function creation
                # FastMCP reads handler.__doc__ when mcp.tool() is called
                # This must be set before the decorator is applied
                handler.__doc__ = tool_description

                return handler

            # Register all K8s tools
            logger.info("Starting tool registration loop...")
            registered_count = 0
            failed_tools = []

            for idx, spec in enumerate(K8S_TOOL_SPECS, 1):
                tool_name = spec.get("tool", f"UNKNOWN_{idx}")
                logger.debug("Processing tool %d/%d: %s", idx, len(K8S_TOOL_SPECS), tool_name)

                handler = build_k8s_handler(spec)
                if handler:
                    try:
                        # Register tool - FastMCP will read description from handler.__doc__
                        # The docstring was set in build_k8s_handler before returning
                        mcp.tool(name=spec["tool"], tags=["k8s"])(handler)
                        registered_count += 1
                        logger.debug("  ✓ Registered: %s", tool_name)
                    except Exception as reg_error:
                        logger.error("  ✗ Failed to register %s: %s", tool_name, str(reg_error))
                        failed_tools.append(tool_name)
                else:
                    logger.warning("  ✗ Failed to build handler for tool: %s", tool_name)
                    failed_tools.append(tool_name)

            logger.info("=" * 80)
            logger.info("Kubernetes Tools Registration Summary")
            logger.info("=" * 80)
            logger.info("Total tool specs: %d", len(K8S_TOOL_SPECS))
            logger.info("Successfully registered: %d", registered_count)
            logger.info("Failed: %d", len(failed_tools))

            if failed_tools:
                logger.warning("Failed tools: %s", failed_tools)
            else:
                logger.info("✓ All tools registered successfully")

            logger.info("=" * 80)
        else:
            logger.error("=" * 80)
            logger.error("Kubernetes Adapter is None - Tools Will NOT Be Registered")
            logger.error("=" * 80)
            logger.error("The Kubernetes adapter failed to initialize, so no K8s tools will be available.")
            logger.error("")

            if adapter_error:
                logger.error("Adapter initialization error: %s", adapter_error)
                logger.error("")
                logger.error("Troubleshooting steps:")
                logger.error("  1. Verify kubeconfig is configured:")
                logger.error("     kubectl cluster-info")
                logger.error("     kubectl get pods")
                logger.error("")
                logger.error("  2. For GKE clusters:")
                logger.error("     gcloud container clusters get-credentials CLUSTER_NAME --zone ZONE --project PROJECT_ID")
                logger.error("     gcloud auth application-default login")
                logger.error("")
                logger.error("  3. Check environment variables:")
                logger.error("     K8S_KUBECONFIG: %s", settings.K8S_KUBECONFIG or "Not set (will use ~/.kube/config)")
                logger.error("     K8S_CONTEXT: %s", settings.K8S_CONTEXT or "Not set (will use current-context)")
                logger.error("     K8S_NAMESPACE: %s", settings.K8S_NAMESPACE or "default")
            else:
                logger.error("No error message available - check server logs for initialization details")

            logger.error("=" * 80)
    else:
        logger.info("K8S_ENABLED is False - skipping Kubernetes tool registration")
        logger.info("To enable K8s tools, set K8S_ENABLED=true in your .env file")
    # Prometheus tools
    if settings.PROMETHEUS_ENDPOINT:
        prometheus_adapter = PrometheusAdapter(None)

        async def prometheus_list_metrics(params: dict, ctx=None):
            """
            List all available metrics in Prometheus with optional pagination support.

            Args:
                params: Dictionary containing:
                    - limit (int, optional): Maximum number of metrics to return
                    - offset (int, optional, default: 0): Number of metrics to skip for pagination
                    - filterPattern (str, optional): Optional substring to filter metric names (case-insensitive)

            Returns:
                dict: {"ok": True, "metrics": [...], "total_count": N, "returned_count": M,
                      "offset": O, "has_more": bool}
            """
            # await require_mcp_auth_and_rate(ctx, rate_limiter)  # Disabled for stateless mode
            result = await prometheus_adapter.list_metrics(
                PrometheusListMetricsInput.parse_or_error(
                    {
                        "limit": params.get("limit"),
                        "offset": params.get("offset", 0),
                        "filter_pattern": params.get("filterPattern"),
                    },
                    "prometheus",
                )
            )
            return {"ok": True, **result}
        mcp.tool(name="prometheus.listMetrics", tags=["prometheus"])(prometheus_list_metrics)

        async def prometheus_get_metric_metadata(params: dict, ctx=None):
            """
            Get metadata for a specific metric.

            Args:
                params: Dictionary containing:
                    - metric (str, required): The name of the metric to retrieve metadata for

            Returns:
                dict: {"ok": True, "metadata": [...]} where metadata is a list of metadata entries
            """
            # await require_mcp_auth_and_rate(ctx, rate_limiter)  # Disabled for stateless mode
            metadata = await prometheus_adapter.get_metric_metadata(
                PrometheusMetricInput.parse_or_error(params, "prometheus")
            )
            return {"ok": True, "metadata": metadata}
        mcp.tool(name="prometheus.getMetricMetadata", tags=["prometheus"])(prometheus_get_metric_metadata)

        async def prometheus_get_targets(params: dict, ctx=None):
            """
            Get information about all Prometheus scrape targets.

            Args:
                params: Dictionary (no parameters required)

            Returns:
                dict: {"ok": True, "activeTargets": [...], "droppedTargets": [...]}
            """
            # await require_mcp_auth_and_rate(ctx, rate_limiter)  # Disabled for stateless mode
            result = await prometheus_adapter.get_targets()
            return {"ok": True, **result}
        mcp.tool(name="prometheus.getTargets", tags=["prometheus"])(prometheus_get_targets)

        async def prometheus_execute_query(params: dict, ctx=None):
            """
            Execute a PromQL instant query against Prometheus.

            Args:
                params: Dictionary containing:
                    - query (str, required): PromQL query string
                    - time (str, optional): RFC3339 or Unix timestamp (default: current time)

            Returns:
                dict: {"ok": True, "resultType": "...", "result": [...]}
            """
            # await require_mcp_auth_and_rate(ctx, rate_limiter)  # Disabled for stateless mode
            result = await prometheus_adapter.execute_query(
                PrometheusExecuteQueryInput.parse_or_error(params, "prometheus")
            )
            return {"ok": True, **result}
        mcp.tool(name="prometheus.executeQuery", tags=["prometheus"])(prometheus_execute_query)

        async def prometheus_execute_range_query(params: dict, ctx=None):
            """
            Execute a PromQL range query with start time, end time, and step interval.

            Args:
                params: Dictionary containing:
                    - query (str, required): PromQL query string
                    - start (str, required): Start time as RFC3339 or Unix timestamp
                    - end (str, required): End time as RFC3339 or Unix timestamp
                    - step (str, required): Query resolution step width (e.g., '15s', '1m', '1h')

            Returns:
                dict: {"ok": True, "resultType": "...", "result": [...]}
            """
            # await require_mcp_auth_and_rate(ctx, rate_limiter)  # Disabled for stateless mode
            result = await prometheus_adapter.execute_range_query(
                PrometheusExecuteRangeQueryInput.parse_or_error(params, "prometheus")
            )
            return {"ok": True, **result}
        mcp.tool(name="prometheus.executeRangeQuery", tags=["prometheus"])(prometheus_execute_range_query)

    # Tempo tools (distributed tracing)
    if settings.TEMPO_URL:
        tempo_adapter = TempoAdapter(None)

        async def tempo_search_traces(params: dict, ctx=None):
            """
            Search for traces using TraceQL query.

            Args:
                params: Dictionary containing:
                    - query (str, required): TraceQL query string (e.g., '{ resource.service.name = "my-service" }')
                    - start (str, optional): Start time (default: 1h ago). Supports "now", "-1h", RFC3339, etc.
                    - end (str, optional): End time (default: now)
                    - limit (int, optional, default: 20): Maximum number of traces to return
                    - minDuration (str, optional): Minimum trace duration filter (e.g., "100ms", "1s")
                    - maxDuration (str, optional): Maximum trace duration filter (e.g., "5s", "1m")

            Returns:
                dict: {"ok": True, "traces": [...], "total_count": N, "metrics": {...}}
            """
            result = await tempo_adapter.search_traces(
                TempoSearchTracesInput.parse_or_error(
                    {
                        "query": params.get("query"),
                        "start": params.get("start"),
                        "end": params.get("end"),
                        "limit": params.get("limit", 20),
                        "min_duration": params.get("minDuration"),
                        "max_duration": params.get("maxDuration"),
                    },
                    "tempo",
                )
            )
            return {"ok": True, **result}
        mcp.tool(name="tempo.searchTraces", tags=["tempo"])(tempo_search_traces)

        async def tempo_get_trace(params: dict, ctx=None):
            """
            Get a specific trace by its ID.

            Args:
                params: Dictionary containing:
                    - traceId (str, required): The trace ID to retrieve

            Returns:
                dict: {"ok": True, "trace": {...}} containing the full trace data with all spans
            """
            result = await tempo_adapter.get_trace(
                TempoGetTraceInput.parse_or_error({"trace_id": params.get("traceId")}, "tempo")
            )
            return {"ok": True, "trace": result}
        mcp.tool(name="tempo.getTrace", tags=["tempo"])(tempo_get_trace)

        async def tempo_search_tags(params: dict, ctx=None):
            """
            Get available tag names for searching.

            Args:
                params: Dictionary containing:
                    - scope (str, optional): Scope to filter tags (e.g., "span", "resource", "intrinsic")

            Returns:
                dict: {"ok": True, "tagNames": [...], "scopes": [...]}
            """
            result = await tempo_adapter.search_tags(
                TempoSearchTagsInput.parse_or_error(params, "tempo")
            )
            return {"ok": True, **result}
        mcp.tool(name="tempo.searchTags", tags=["tempo"])(tempo_search_tags)

        async def tempo_search_tag_values(params: dict, ctx=None):
            """
            Get values for a specific tag.

            Args:
                params: Dictionary containing:
                    - tagName (str, required): The tag name to get values for
                    - start (str, optional): Start time for filtering values
                    - end (str, optional): End time for filtering values
                    - query (str, optional): TraceQL query to filter values

            Returns:
                dict: {"ok": True, "tagValues": [...]}
            """
            result = await tempo_adapter.search_tag_values(
                TempoSearchTagValuesInput.parse_or_error(
                    {
                        "tag_name": params.get("tagName"),
                        "start": params.get("start"),
                        "end": params.get("end"),
                        "query": params.get("query"),
                    },
                    "tempo",
                )
            )
            return {"ok": True, **result}
        mcp.tool(name="tempo.searchTagValues", tags=["tempo"])(tempo_search_tag_values)

        async def tempo_query_metrics(params: dict, ctx=None):
            """
            Execute a TraceQL metrics query.

            Args:
                params: Dictionary containing:
                    - query (str, required): TraceQL metrics query string
                    - start (str, optional): Start time (default: 1h ago)
                    - end (str, optional): End time (default: now)
                    - step (str, optional, default: "60s"): Step interval for metrics

            Returns:
                dict: {"ok": True, "data": {...}} containing metrics data
            """
            result = await tempo_adapter.query_metrics(
                TempoQueryMetricsInput.parse_or_error(
                    {
                        "query": params.get("query"),
                        "start": params.get("start"),
                        "end": params.get("end"),
                        "step": params.get("step", "60s"),
                    },
                    "tempo",
                )
            )
            return {"ok": True, "data": result}
        mcp.tool(name="tempo.queryMetrics", tags=["tempo"])(tempo_query_metrics)

        async def tempo_check_health(params: dict, ctx=None):
            """
            Check Tempo backend health status.

            Args:
                params: Dictionary (no parameters required)

            Returns:
                dict: {"ok": True, "ready": bool, "status_code": int, "message": str}
            """
            result = await tempo_adapter.check_health()
            return {"ok": True, **result}
        mcp.tool(name="tempo.checkHealth", tags=["tempo"])(tempo_check_health)

# -- cleanup --
async def cleanup():
    logger.info("cleanup: shutting down shared resources")
    try:
        await SharedAsyncClient.aclose()
    except Exception:
        logger.exception("cleanup: http client close error")
    try:
        if idempotency_store:
            await idempotency_store.close()
    except Exception:
        logger.exception("cleanup: idempotency store close error")
    try:
        if rate_limiter:
            await rate_limiter.close()
    except Exception:
        logger.exception("cleanup: rate limiter close error")


    def register_tools():
        @mcp.tool()
        async def connect_to_database(connection_string: str):
            """Connect to Oracle database and verify connection."""
            return await oracle_adapter.connect_to_database(connection_string)
        
        @mcp.tool()
        async def execute_sql(sql_statement: str):
            """Execute any SQL statement against Oracle database."""
            return await oracle_adapter.execute_sql(sql_statement)
        
        @mcp.tool()
        async def oracle_test_connection():
            """Test Oracle database connection."""
            return await oracle_adapter.test_connection()
        
        @mcp.tool()
        async def oracle_get_tables():
            """Get all tables in the Oracle database."""
            return await oracle_adapter.get_tables()
        
        @mcp.tool()
        async def oracle_get_columns(table_name: str):
            """Get columns for a specific Oracle table."""
            return await oracle_adapter.get_columns(
                OracleGetColumnDetailsInput(table_name=table_name)
                )
            
        @mcp.tool()
        async def oracle_get_schema():
            """Get full schema of all Oracle tables."""
            return await oracle_adapter.get_schema()

    

if __name__ == "__main__":
    import asyncio

    logger.info("=" * 80)
    logger.info("MCP Server Startup")
    logger.info("=" * 80)
    logger.info("Initializing services...")

    asyncio.run(init_services())

    logger.info("Registering tools...")
    logger.info("  OPENSEARCH_URL: %s", settings.OPENSEARCH_URL or "Not set")
    logger.info("  K8S_ENABLED: %s", settings.K8S_ENABLED)


    register_tools()

    # Log registered tools count
    from tool_specs.k8s import K8S_TOOL_SPECS
    if settings.K8S_ENABLED:
        logger.info("K8S_ENABLED=True, expecting %d K8s tools to be registered", len(K8S_TOOL_SPECS))
    else:
        logger.info("K8S_ENABLED=False, K8s tools will not be registered")

    logger.info("MCP Server Configuration:")
    logger.info("  Transport: %s", settings.MCP_TRANSPORT)
    logger.info("  Host: %s", settings.HOST)
    logger.info("  Port: %s", settings.PORT)
    logger.info("  Stateless HTTP: True")
    logger.info("=" * 80)
    logger.info("Starting MCP server...")
    logger.info("=" * 80)

    mcp.run(transport=settings.MCP_TRANSPORT, host=settings.HOST, port=settings.PORT, stateless_http=True)


