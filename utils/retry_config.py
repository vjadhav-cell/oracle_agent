# utils/retry_config.py
from functools import wraps
import httpx
from tenacity import (retry, retry_if_exception_type, stop_after_attempt,
                      wait_exponential)

from utils.config import settings


def create_retry_decorator():
    """
    Creates a retry decorator with configurable parameters from environment variables.

    Returns:
        A retry decorator configured with:
        - RETRY_MAX_ATTEMPTS: Maximum number of retry attempts (default: 3)
        - RETRY_MULTIPLIER: Exponential backoff multiplier (default: 0.5)
        - RETRY_MAX_WAIT: Maximum wait time in seconds (default: 4)
    """
    return retry(
        stop=stop_after_attempt(settings.RETRY_MAX_ATTEMPTS),
        wait=wait_exponential(multiplier=settings.RETRY_MULTIPLIER, max=settings.RETRY_MAX_WAIT),
        retry=retry_if_exception_type(httpx.RequestError)
    )

# Convenience decorator for common retry pattern
retry_on_request_error = create_retry_decorator()
