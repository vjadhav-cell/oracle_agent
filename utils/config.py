# core/config.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Required for server auth
    MCP_API_KEY: str

    # Server config
    MCP_TRANSPORT: str = "http"
    HOST: str = "0.0.0.0"
    PORT: int = 8080

    # Oracle Configuration
    DEBUG: bool = False

    ORACLE_ENABLED: bool = True

    DB_CONNECTION_STRING: str | None = None

    COMMENT_DB_CONNECTION_STRING: str | None = None

    QUERY_LIMIT_SIZE: int = 50

    TABLE_WHITE_LIST: str | None = None

    COLUMN_WHITE_LIST: str | None = None

    # Redis for idempotency and rate-limiter
    REDIS_URL: str = "redis://localhost:6379/0"
    IDEMPOTENCY_TTL: int = 0  # Set to 0 to disable idempotency by default
    RATE_LIMIT_CAPACITY: int = 120
    RATE_LIMIT_REFILL_SECONDS: int = 60
    RATE_LIMIT_FAIL_OPEN: bool = True

    # Optional provider credentials
    SLACK_BOT_TOKEN: str | None = None
    JIRA_BASE: str | None = None
    JIRA_EMAIL: str | None = None
    JIRA_API_TOKEN: str | None = None
    GCP_SA_JSON: str | None = None
    GRAFANA_BASE_URL: str | None = None
    GRAFANA_API_KEY: str | None = None
    GRAFANA_USERNAME: str | None = None
    GRAFANA_PASSWORD: str | None = None
    OPENSEARCH_URL: str | None = None
    OPENSEARCH_USERNAME: str | None = None
    OPENSEARCH_PASSWORD: str | None = None
    OPENSEARCH_DATA_SOURCE_ID: str | None = None
    OPENSEARCH_USE_PROXY: bool = False
    OPENSEARCH_PROXY_PATH: str = "/api/console/proxy"
    OPENSEARCH_VERIFY_SSL: bool = False
    MIMIR_URL: str | None = None
    MIMIR_USERNAME: str | None = None
    MIMIR_PASSWORD: str | None = None
    MIMIR_TENANT_ID: str | None = None
    MIMIR_DISABLE_SSL: bool = False
    MIMIR_TIMEOUT: int = 30
    PROMETHEUS_ENDPOINT: str | None = None
    PROMETHEUS_USERNAME: str | None = None
    PROMETHEUS_PASSWORD: str | None = None

    # Tempo config (distributed tracing)
    TEMPO_URL: str | None = None
    TEMPO_USERNAME: str | None = None
    TEMPO_PASSWORD: str | None = None
    TEMPO_TOKEN: str | None = None  # Bearer token for authentication
    TEMPO_ORG_ID: str | None = None  # X-Scope-OrgID header for multi-tenant setups

    # Kubernetes config
    K8S_ENABLED: bool = False  # Explicit flag to enable Kubernetes tools
    K8S_KUBECONFIG: str | None = None  # Path to kubeconfig file, or None for in-cluster config
    K8S_CONTEXT: str | None = None  # Kubernetes context name (optional)
    K8S_NAMESPACE: str | None = None  # Default namespace (optional)
    K8S_VERIFY_SSL: bool = True  # Verify SSL certificates
    K8S_TIMEOUT: int = 30  # Request timeout in seconds

    # Healthcheck
    HEALTHCHECK_FULL: bool = False

    # Retry configuration
    RETRY_MAX_ATTEMPTS: int = 3
    RETRY_MULTIPLIER: float = 0.5
    RETRY_MAX_WAIT: int = 4

    model_config = {
    "env_file": ".env",
    "case_sensitive": True,
    "extra": "ignore"
}

settings = Settings()
