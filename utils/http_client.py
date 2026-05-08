"""
Async HTTP client singleton using httpx.
"""
import asyncio
import logging
import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

import httpx

from utils.constants import (
    CIRCUIT_FAIL_MAX,
    CIRCUIT_RESET_TIMEOUT,
    DEFAULT_REQUEST_DELAY,
    DEFAULT_RETRIES,
    DEFAULT_TIMEOUT,
)
from utils.utils import headers

logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class CircuitOpenError(Exception):
    """Raised when the circuit breaker is open for a host."""


class CircuitBreaker:
    """Per-host open/half-open/closed circuit breaker.

    Trips after fail_max consecutive failures and re-probes after reset_timeout seconds.
    Only network errors and 5xx responses count as failures; 429 does not.
    """

    _CLOSED = "closed"
    _OPEN = "open"
    _HALF_OPEN = "half_open"

    def __init__(self, fail_max: int = CIRCUIT_FAIL_MAX, reset_timeout: float = CIRCUIT_RESET_TIMEOUT) -> None:
        self.fail_max = fail_max
        self.reset_timeout = reset_timeout
        self._failures: dict[str, int] = {}
        self._state: dict[str, str] = {}
        self._opened_at: dict[str, float] = {}

    @staticmethod
    def _host(url: str) -> str:
        return urlparse(url).netloc

    def _current_state(self, host: str) -> str:
        state = self._state.get(host, self._CLOSED)
        if state == self._OPEN:
            if time.monotonic() - self._opened_at.get(host, 0.0) >= self.reset_timeout:
                self._state[host] = self._HALF_OPEN
                return self._HALF_OPEN
        return state

    def allow_request(self, url: str) -> bool:
        """Return True if a request should proceed; False when the circuit is open."""
        return self._current_state(self._host(url)) != self._OPEN

    def record_success(self, url: str) -> None:
        host = self._host(url)
        self._failures[host] = 0
        self._state[host] = self._CLOSED

    def record_failure(self, url: str) -> None:
        host = self._host(url)
        count = self._failures.get(host, 0) + 1
        self._failures[host] = count
        if count >= self.fail_max:
            self._state[host] = self._OPEN
            self._opened_at[host] = time.monotonic()
            logger.warning("Circuit opened for %s after %d consecutive failures", host, count)

    def reset(self) -> None:
        """Clear all state. Intended for use in tests."""
        self._failures.clear()
        self._state.clear()
        self._opened_at.clear()


circuit_breaker = CircuitBreaker()


def _parse_retry_after(response: httpx.Response) -> float | None:
    """Parse the Retry-After header into seconds. Returns None if absent or unparseable."""
    value = response.headers.get("Retry-After")
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        pass
    try:
        dt = parsedate_to_datetime(value)
        delta = (dt - datetime.now(tz=UTC)).total_seconds()
        return max(0.0, delta)
    except Exception:
        return None


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
    """Fetch a URL with bounded retries for transient upstream failures.

    Raises CircuitOpenError immediately if the per-host circuit is open.
    Records a failure against the circuit only after all retries are exhausted.
    429 responses use the Retry-After header for backoff but do not count as
    circuit failures (they indicate rate-limiting, not a service outage).
    """
    if not circuit_breaker.allow_request(url):
        raise CircuitOpenError(
            f"Circuit open for {urlparse(url).netloc} — request to {url} blocked"
        )

    client = client or get_http_client()
    retries = max(1, max_retries)
    last_response: httpx.Response | None = None

    for attempt in range(1, retries + 1):
        try:
            response = await client.get(url, timeout=timeout)
        except httpx.RequestError as exc:
            if attempt >= retries:
                circuit_breaker.record_failure(url)
                raise
            logger.warning(
                "Retrying %s after request error on attempt %d/%d: %s",
                url, attempt, retries, exc,
            )
            await asyncio.sleep(request_delay * (2 ** (attempt - 1)))
            continue

        last_response = response

        if response.status_code not in RETRYABLE_STATUS_CODES or attempt >= retries:
            if response.status_code not in RETRYABLE_STATUS_CODES:
                circuit_breaker.record_success(url)
            elif response.status_code != 429:
                circuit_breaker.record_failure(url)
            return response

        if response.status_code == 429:
            backoff = _parse_retry_after(response) or request_delay * (2 ** (attempt - 1))
        else:
            backoff = request_delay * (2 ** (attempt - 1))

        logger.warning(
            "Retrying %s after upstream status %d on attempt %d/%d (backoff %.1fs)",
            url, response.status_code, attempt, retries, backoff,
        )
        await asyncio.sleep(backoff)

    if last_response is not None:
        return last_response
    raise RuntimeError(f"Failed to fetch {url} without producing a response")


async def close_http_client():
    """Close the HTTP client. Call during app shutdown."""
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
        _client = None
