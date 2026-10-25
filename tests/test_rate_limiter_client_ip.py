"""Client identity and memory-bound tests for the in-process rate limiter."""
import pytest
from starlette.requests import Request
from starlette.responses import Response

from api.utils import rate_limiter


def make_request(client_host: str | None, forwarded: str | None = None) -> Request:
    headers = []
    if forwarded is not None:
        headers.append((b"x-forwarded-for", forwarded.encode()))
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/v2/match/details",
        "raw_path": b"/v2/match/details",
        "query_string": b"",
        "root_path": "",
        "headers": headers,
        "client": (client_host, 4321) if client_host else None,
        "server": ("testserver", 80),
    }
    return Request(scope)


def client_ip(request: Request) -> str:
    return rate_limiter.SlidingWindowRateLimiter._client_ip(request)


def test_forwarded_header_is_ignored_from_an_untrusted_peer():
    request = make_request("203.0.113.7", "198.51.100.5")
    assert client_ip(request) == "203.0.113.7"


def test_forwarded_header_is_honoured_from_a_trusted_peer():
    request = make_request("127.0.0.1", "198.51.100.5")
    assert client_ip(request) == "198.51.100.5"


def test_rightmost_untrusted_hop_wins_over_a_spoofed_leftmost_entry():
    """An append-mode proxy leaves the attacker's value first; it must be ignored."""
    request = make_request("127.0.0.1", "203.0.113.99, 198.51.100.5, 127.0.0.1")
    assert client_ip(request) == "198.51.100.5"


def test_malformed_hop_falls_back_to_the_peer():
    request = make_request("127.0.0.1", "not-an-ip")
    assert client_ip(request) == "127.0.0.1"


def test_missing_client_scope_returns_unknown():
    assert client_ip(make_request(None)) == "unknown"


def test_trusted_proxies_are_configurable(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXIES", "10.9.8.7, 2001:db8::/32")

    assert client_ip(make_request("10.9.8.7", "198.51.100.5")) == "198.51.100.5"
    assert client_ip(make_request("2001:db8::1", "198.51.100.5")) == "198.51.100.5"
    assert client_ip(make_request("127.0.0.1", "198.51.100.5")) == "127.0.0.1"


def test_invalid_trusted_proxy_entries_are_ignored_without_being_logged(monkeypatch, caplog):
    monkeypatch.setenv("TRUSTED_PROXIES", "not-a-network,127.0.0.1")

    with caplog.at_level("WARNING"):
        assert client_ip(make_request("127.0.0.1", "198.51.100.5")) == "198.51.100.5"

    assert "TRUSTED_PROXIES" in caplog.text
    assert "not-a-network" not in caplog.text
    assert client_ip(make_request("127.0.0.1", "198.51.100.5")) == "198.51.100.5"


def test_spoofed_headers_cannot_multiply_buckets():
    """Rotating the header must not buy a fresh bucket per request."""
    limiter = rate_limiter.SlidingWindowRateLimiter()

    for octet in range(5):
        ip = limiter._client_ip(make_request("203.0.113.7", f"10.0.0.{octet}"))
        limiter.check("expensive", f"expensive:{ip}")

    assert list(limiter._stores["expensive"]) == ["expensive:203.0.113.7"]


def test_bucket_tracking_is_bounded(monkeypatch):
    monkeypatch.setattr(rate_limiter, "_MAX_TRACKED_CLIENTS", 50)
    limiter = rate_limiter.SlidingWindowRateLimiter()

    for octet in range(500):
        limiter.check("expensive", f"expensive:198.51.100.{octet}")

    assert len(limiter._stores["expensive"]) <= 50


@pytest.mark.anyio
async def test_middleware_keys_requests_by_peer_not_by_header(monkeypatch):
    limiter = rate_limiter.SlidingWindowRateLimiter()
    monkeypatch.setattr(rate_limiter, "get_rate_limiter", lambda: limiter)
    middleware = rate_limiter.RateLimitMiddleware(app=None)

    async def call_next(_request):
        return Response(status_code=200)

    for spoofed in ("1.1.1.1", "2.2.2.2", "3.3.3.3"):
        response = await middleware.dispatch(make_request("203.0.113.7", spoofed), call_next)
        assert response.status_code == 200

    assert list(limiter._stores["expensive"]) == ["expensive:203.0.113.7"]
