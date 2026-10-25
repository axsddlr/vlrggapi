"""
Sliding-window in-memory rate limiter with per-endpoint tiers.

Replaces slowapi with a leaner, more precise implementation:
  - Sliding window (not fixed) — no burst abuse at window boundaries
  - Tiered limits — cheap endpoints don't compete with expensive ones
  - Single shared state — no orphaned limiter instances
  - Zero new dependencies — pure asyncio + deque

Not safe across multiple workers — each worker process has its own counter.
For multi-worker deployments, pair with a Redis-backed store or use
a reverse-proxy layer (e.g. Nginx, Vercel Edge middleware).

Clients are keyed by the peer address the server actually accepted, unless that
peer is listed in ``TRUSTED_PROXIES`` (comma-separated IPs/CIDRs, default
``127.0.0.1,::1``). Only then is ``X-Forwarded-For`` consulted, and the
rightmost hop that is not itself a trusted proxy is used.
"""

import ipaddress
import logging
import os
import time
from collections import defaultdict, deque
from functools import lru_cache
from urllib.parse import parse_qs

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tier definitions
# ---------------------------------------------------------------------------
#   cheap:    200 req/min — health checks, version pings (no outbound scrape)
#   moderate:  60 req/min — 1–2 scrapes per request
#   expensive: 20 req/min — 3+ sub-scrapes (match detail, player, team, stats)
# ---------------------------------------------------------------------------
TIERS: dict[str, tuple[int, int]] = {
    "cheap": (200, 60),
    "moderate": (60, 60),
    "expensive": (20, 60),
}

# `/match` sub-queries that need a stricter tier than the path alone implies.
_MODERATE_MATCH_Q = frozenset({"upcoming", "live_score"})


def _normalise(path: str) -> str:
    """Strip ``/v2`` prefix and trailing slash for uniform matching."""
    p = path.rstrip("/").lower()
    if p.startswith("/v2"):
        p = p[3:] or "/"
    return p or "/"


def _match_tier(path: str, query: str) -> str | None:
    """Resolve a URL path + query string to a rate-limit tier.

    Returns ``None`` for unlimited paths (docs, OpenAPI, etc.).
    """
    normalised = _normalise(path)

    # Order matters: more specific paths are listed first.
    tiers: list[tuple[str, str | None]] = [
        ("/match/details", "expensive"),
        ("/events/matches", "moderate"),
        ("/health", "cheap"),
        ("/version", "cheap"),
        ("/rankings", "moderate"),
        ("/news", "moderate"),
        ("/events", "moderate"),
        ("/event/", "moderate"),
        ("/search", "moderate"),
        ("/stats", "expensive"),
        ("/match/", "expensive"),
        ("/player", "expensive"),
        ("/team", "expensive"),
        ("/match", None),
    ]

    for prefix, tier in tiers:
        if normalised == prefix:
            if tier is not None:
                return tier
            params = parse_qs(query)
            q_vals = params.get("q", [])
            q = q_vals[0].lower() if q_vals else ""
            return "moderate" if q in _MODERATE_MATCH_Q else "expensive"

        prefix_base = prefix.rstrip("/")
        if normalised.startswith(prefix_base + "/"):
            if tier is not None:
                return tier
            continue

    return None


# ---------------------------------------------------------------------------
# Client identity
# ---------------------------------------------------------------------------
# X-Forwarded-For is client-supplied unless the immediate peer is a proxy we
# trust, so it is only consulted to extend a chain that starts at a trusted
# peer. uvicorn already rewrites request.client for peers listed in
# --forwarded-allow-ips, which makes request.client the primary source.
TRUSTED_PROXIES_ENV = "TRUSTED_PROXIES"
_DEFAULT_TRUSTED_PROXIES = "127.0.0.1,::1"


@lru_cache(maxsize=8)
def _parse_trusted_networks(raw: str) -> tuple:
    """Parse a comma-separated IP/CIDR list, skipping unusable entries."""
    networks = []
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        try:
            networks.append(ipaddress.ip_network(entry, strict=False))
        except ValueError:
            # Deliberately a constant message: the raw entry (and the env-var name
            # itself) is environment-derived data and must not be logged in clear.
            logger.warning("Ignoring an invalid entry in TRUSTED_PROXIES")
    return tuple(networks)


def _trusted_networks() -> tuple:
    return _parse_trusted_networks(
        os.environ.get(TRUSTED_PROXIES_ENV, _DEFAULT_TRUSTED_PROXIES)
    )


def _is_trusted_proxy(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    return any(address in network for network in _trusted_networks())


# ---------------------------------------------------------------------------
# Core limiter
# ---------------------------------------------------------------------------


_MAX_TRACKED_CLIENTS = 5000


class SlidingWindowRateLimiter:
    """Sliding-window counter per (tier, client_key).

    Thread-safe enough for single-process async use (GIL protects deque ops).
    """

    def __init__(self):
        self._stores: dict[str, dict[str, deque[float]]] = defaultdict(
            lambda: defaultdict(deque)
        )

    @staticmethod
    def _client_ip(request: Request) -> str:
        """Resolve the client address without trusting an unvalidated header.

        A forwarded hop is honoured only when the peer we actually accepted the
        connection from is a trusted proxy; the walk then takes the rightmost
        hop that is not itself a trusted proxy, so a spoofed leftmost entry can
        never select a bucket.
        """
        peer = request.client.host if request.client else ""
        if not peer:
            return "unknown"
        if not _is_trusted_proxy(peer):
            return peer

        forwarded = request.headers.get("x-forwarded-for", "")
        hops = [hop.strip() for hop in forwarded.split(",") if hop.strip()]
        for hop in reversed(hops):
            if _is_trusted_proxy(hop):
                continue
            try:
                ipaddress.ip_address(hop)
            except ValueError:
                # Malformed hop: fall back to the proxy rather than invent one.
                return peer
            return hop
        return peer

    @staticmethod
    def _evict_cold_buckets(tier_store: dict[str, deque[float]], cutoff: float) -> None:
        """Keep bucket tracking bounded when keys are attacker-chosen.

        Expired buckets are dropped first, then the oldest-inserted ones until
        the cap is met, so a stream of unique spoofed keys cannot grow memory
        without bound.
        """
        if len(tier_store) <= _MAX_TRACKED_CLIENTS:
            return
        for key in [k for k, v in tier_store.items() if not v or v[-1] < cutoff]:
            del tier_store[key]
        while len(tier_store) > _MAX_TRACKED_CLIENTS:
            tier_store.pop(next(iter(tier_store)), None)

    def check(self, tier: str, key: str) -> tuple[bool, int, int]:
        """Check and record a request against a (tier, key).

        Returns ``(allowed, remaining, retry_after_seconds)``.
        Callers MUST NOT interpret *remaining* when *allowed* is ``False``.
        """
        cfg = TIERS.get(tier)
        if cfg is None:
            return True, -1, 0

        limit, window = cfg
        now = time.time()
        cutoff = now - window
        tier_store = self._stores[tier]
        store = tier_store[key]

        while store and store[0] < cutoff:
            store.popleft()

        if len(store) >= limit:
            retry_after = int(store[0] - (now - window)) if store else window
            return False, 0, retry_after

        store.append(now)
        self._evict_cold_buckets(tier_store, cutoff)
        remaining = limit - len(store)
        return True, remaining, 0


# ---------------------------------------------------------------------------
# ASGI middleware
# ---------------------------------------------------------------------------

_limiter: SlidingWindowRateLimiter | None = None


def get_rate_limiter() -> SlidingWindowRateLimiter:
    global _limiter
    if _limiter is None:
        _limiter = SlidingWindowRateLimiter()
    return _limiter


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI/Starlette middleware that enforces sliding-window rate limits.

    Usage in ``main.py``::

        app.add_middleware(RateLimitMiddleware)
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        query = request.url.query
        tier = _match_tier(path, query)

        if tier is None:
            return await call_next(request)

        limiter = get_rate_limiter()
        ip = limiter._client_ip(request)
        allowed, remaining, retry_after = limiter.check(tier, f"{tier}:{ip}")

        if not allowed:
            limit_val = TIERS.get(tier, (0, 0))[0]
            logger.warning("Rate limit hit — tier=%s ip=%s", tier, ip)
            return JSONResponse(
                status_code=429,
                content={
                    "detail": {
                        "error": "Rate limit exceeded",
                        "tier": tier,
                        "retry_after": retry_after,
                        "limit": limit_val,
                    }
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(limit_val),
                    "X-RateLimit-Remaining": "0",
                },
            )

        response = await call_next(request)

        limit_val = TIERS.get(tier, (None, None))[0]
        if limit_val is not None:
            response.headers["X-RateLimit-Limit"] = str(limit_val)
            response.headers["X-RateLimit-Remaining"] = str(max(remaining, 0))

        return response
