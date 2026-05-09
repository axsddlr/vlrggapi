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
"""

import logging
import time
from collections import defaultdict, deque
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

# URL-pattern → tier mapping. Order matters: more specific paths first.
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
# Core limiter
# ---------------------------------------------------------------------------


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
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

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
        store = self._stores[tier][key]

        while store and store[0] < cutoff:
            store.popleft()

        if len(store) >= limit:
            retry_after = int(store[0] - (now - window)) if store else window
            return False, 0, retry_after

        store.append(now)
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
