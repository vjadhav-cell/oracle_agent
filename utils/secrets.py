import json
import os
from typing import Dict, Optional
from schemas.utils import TenantInput
from utils.config import settings


def get_jira_credentials(data: TenantInput) -> Optional[Dict[str, str]]:
    base = os.getenv("JIRA_BASE")
    email = os.getenv("JIRA_EMAIL")
    token = os.getenv("JIRA_API_TOKEN")
    if base and email and token:
        return {"base_url": base.rstrip("/"), "email": email, "api_token": token}
    return None

def get_slack_credentials(data: TenantInput) -> Optional[Dict[str, str]]:
    token = os.getenv("SLACK_BOT_TOKEN")
    if token:
        return {"bot_token": token}
    return None

def get_gcp_credentials(data: TenantInput) -> Optional[Dict[str, str]]:
    v = os.getenv("GCP_SA_JSON")
    if not v:
        return None
    return {"service_account_json": v}

def get_grafana_credentials(data: TenantInput) -> Optional[Dict[str, str]]:
    base_url = os.getenv("GRAFANA_BASE_URL")

    # Try username/password first (new method)
    username = os.getenv("GRAFANA_USERNAME")
    password = os.getenv("GRAFANA_PASSWORD")
    if base_url and username and password:
        return {"base_url": base_url.rstrip("/"), "username": username, "password": password, "auth_type": "basic"}

    # Fallback to API key (legacy method)
    api_key = os.getenv("GRAFANA_API_KEY")
    if base_url and api_key:
        return {"base_url": base_url.rstrip("/"), "api_key": api_key, "auth_type": "bearer"}

    return None

def get_opensearch_credentials(data: TenantInput) -> Optional[Dict[str, str]]:
    url = os.getenv("OPENSEARCH_URL")
    username = os.getenv("OPENSEARCH_USERNAME")
    password = os.getenv("OPENSEARCH_PASSWORD")
    if url:
        return {"url": url, "username": username, "password": password}
    return None

def get_mimir_credentials(data: TenantInput) -> Optional[Dict[str, str]]:
    url = os.getenv("MIMIR_URL")
    username = os.getenv("MIMIR_USERNAME")
    password = os.getenv("MIMIR_PASSWORD")
    tenant_id = os.getenv("MIMIR_TENANT_ID")
    if url:
        return {"url": url, "username": username, "password": password, "tenant_id": tenant_id}
    return None

def get_k8s_credentials(data: TenantInput) -> Optional[Dict[str, str]]:
    """Get Kubernetes credentials from environment variables."""
    kubeconfig = os.getenv("K8S_KUBECONFIG")
    context = os.getenv("K8S_CONTEXT")
    namespace = os.getenv("K8S_NAMESPACE")
    verify_ssl = os.getenv("K8S_VERIFY_SSL", "true").lower() == "true"
    timeout = int(os.getenv("K8S_TIMEOUT", "30"))

    # If kubeconfig is not set, we'll use in-cluster config
    return {
        "kubeconfig": kubeconfig,
        "context": context,
        "namespace": namespace,
        "verify_ssl": verify_ssl,
        "timeout": timeout
    }

def get_prometheus_credentials(data: TenantInput) -> Optional[Dict[str, str]]:
    endpoint = os.getenv("PROMETHEUS_ENDPOINT")
    if endpoint:
        return {
            "url": endpoint.rstrip("/"),
            "username": os.getenv("PROMETHEUS_USERNAME"),
            "password": os.getenv("PROMETHEUS_PASSWORD")
        }
    return None

def get_tempo_credentials(data: TenantInput) -> Optional[Dict[str, str]]:
    """Get Tempo credentials from environment variables."""
    url = os.getenv("TEMPO_URL")
    if url:
        return {
            "url": url.rstrip("/"),
            "username": os.getenv("TEMPO_USERNAME"),
            "password": os.getenv("TEMPO_PASSWORD"),
            "token": os.getenv("TEMPO_TOKEN"),
            "org_id": os.getenv("TEMPO_ORG_ID"),
        }
    return None

def get_oracle_credentials(data=None):
    connection_string = os.getenv("DB_CONNECTION_STRING")

    if not connection_string:
        return None

    return {
        "connection_string": connection_string
    }