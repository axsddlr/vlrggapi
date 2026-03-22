"""
Async HTTP client singleton using httpx.
"""
import asyncio
import logging

import httpx

from utils.utils import headers
from utils.constants import DEFAULT_REQUEST_DELAY, DEFAULT_RETRIES, DEFAULT_TIMEOUT

logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = {500, 502, 503, 504}

_client: httpx.AsyncClient | None = None


def get_http_client() -> httpx.AsyncClient:
    """Get or create the singleton async HTTP client."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            headers=headers,
            timeout=httpx.Timeout(DEFAULT_TIMEOUT),
            follow_redirects=True,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
    return _client


async def fetch_with_retries(
    url: str,
    *,
    client: httpx.AsyncClient | None = None,
    timeout: int | float | httpx.Timeout | None = None,
    max_retries: int = DEFAULT_RETRIES,
    request_delay: float = DEFAULT_REQUEST_DELAY,
) -> httpx.Response:
    """Fetch a URL with bounded retries for transient upstream failures."""
    client = client or get_http_client()
    retries = max(1, max_retries)
    last_response: httpx.Response | None = None

    for attempt in range(1, retries + 1):
        try:
            response = await client.get(url, timeout=timeout)
        except httpx.RequestError as exc:
            if attempt >= retries:
                raise
            logger.warning(
                "Retrying %s after request error on attempt %d/%d: %s",
                url, attempt, retries, exc,
            )
            await asyncio.sleep(request_delay * (2 ** (attempt - 1)))
            continue

        last_response = response
        if response.status_code not in RETRYABLE_STATUS_CODES or attempt >= retries:
            return response

        logger.warning(
            "Retrying %s after upstream status %d on attempt %d/%d",
            url, response.status_code, attempt, retries,
        )
        await asyncio.sleep(request_delay * (2 ** (attempt - 1)))

    if last_response is not None:
        return last_response
    raise RuntimeError(f"Failed to fetch {url} without producing a response")


async def close_http_client():
    """Close the HTTP client. Call during app shutdown."""
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
        _client = None
