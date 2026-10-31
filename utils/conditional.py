"""
Conditional GET support for the slow-moving JSON endpoints.

The rankings, stats and team endpoints sit behind long-lived in-process TTL
caches, so their payloads change slowly. This middleware labels those
successful JSON responses with a strong ``ETag`` (the SHA-256 of the exact
response body) and answers a matching ``If-None-Match`` with ``304 Not
Modified``, letting repeat clients skip the body entirely.

It deliberately owns no cache: the ETag is derived from whatever body the
application (and its TTL cache) already produced, and no ``Cache-Control``
header is added. This layer also runs inside ``RateLimitMiddleware`` so a 304
still consumes rate-limit budget and still carries the ``X-RateLimit-*``
headers.

Path normalisation mirrors ``api.utils.rate_limiter._normalise`` so both layers
agree on what a given path is.
"""

import hashlib

from starlette.types import ASGIApp, Message, Receive, Scope, Send

# Endpoints whose payloads are backed by long TTL caches.
_SLOW_MOVER_PREFIXES = ("/rankings", "/stats", "/team")

_JSON_CONTENT_TYPE = b"application/json"


def _normalise(path: str) -> str:
    """Strip ``/v2`` prefix and trailing slash for uniform matching."""
    p = path.rstrip("/").lower()
    if p.startswith("/v2"):
        p = p[3:] or "/"
    return p or "/"


def _is_slow_mover(path: str) -> bool:
    """Return True when *path* is a slow mover or a sub-resource of one.

    Prefixes match as a whole path segment (``/team`` or ``/team/123/roster``),
    never as a string prefix (``/teamsomething`` does not match).
    """
    normalised = _normalise(path)
    return any(
        normalised == prefix or normalised.startswith(prefix + "/")
        for prefix in _SLOW_MOVER_PREFIXES
    )


def _is_conditional_request(method: str, path: str) -> bool:
    """Return True when conditional GET handling applies to this request."""
    return method == "GET" and _is_slow_mover(path)


def _make_etag(body: bytes) -> str:
    """Build a strong, quoted ETag from the exact response body bytes."""
    return f'"{hashlib.sha256(body).hexdigest()}"'


def _opaque_tag(value: str) -> str | None:
    """Return the quoted opaque tag of one entity-tag, dropping any ``W/``.

    ``If-None-Match`` uses weak comparison, so a weak client tag still matches
    our strong one. Anything that is not a well-formed quoted tag is ignored.
    """
    value = value.strip()
    if value[:2].lower() == "w/":
        value = value[2:].lstrip()
    if len(value) >= 2 and value.startswith('"') and value.endswith('"'):
        return value
    return None


def _if_none_match_hits(header: str, etag: str) -> bool:
    """Evaluate an ``If-None-Match`` field value against our ETag.

    Supports ``*``, comma-separated lists and weak (``W/``) client tags.
    Malformed entries are skipped, never raised on.
    """
    if not header:
        return False
    for candidate in header.split(","):
        candidate = candidate.strip()
        if not candidate:
            continue
        if candidate == "*":
            return True
        opaque = _opaque_tag(candidate)
        if opaque is not None and opaque == etag:
            return True
    return False


def _header_value(headers: list[tuple[bytes, bytes]], name: bytes) -> bytes | None:
    for key, value in headers:
        if key.lower() == name:
            return value
    return None


async def _send_response(
    send: Send, status: int, headers: list[tuple[bytes, bytes]], body: bytes
) -> None:
    await send(
        {"type": "http.response.start", "status": status, "headers": headers}
    )
    await send({"type": "http.response.body", "body": body, "more_body": False})


class ConditionalGetMiddleware:
    """Add ``ETag``/``304 Not Modified`` support to cached JSON GET endpoints.

    Usage in ``main.py`` (registered inside the rate limiter)::

        app.add_middleware(ConditionalGetMiddleware)

    Implemented as a pure ASGI middleware so the downstream response's headers
    and ``background`` task are left untouched: the application still runs
    normally, and only the bytes handed to the client are rewritten.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not _is_conditional_request(
            scope.get("method", ""), scope.get("path", "")
        ):
            await self.app(scope, receive, send)
            return

        start: Message | None = None
        chunks: list[bytes] = []

        async def capture(message: Message) -> None:
            nonlocal start
            if message["type"] == "http.response.start":
                start = message
            elif message["type"] == "http.response.body":
                chunks.append(message.get("body", b""))

        await self.app(scope, receive, capture)

        if start is None:
            # The app never started a response; an exception has already
            # propagated and the outer error middleware owns the outcome.
            return

        status: int = start["status"]
        headers: list[tuple[bytes, bytes]] = list(start["headers"])
        body = b"".join(chunks)
        content_type = _header_value(headers, b"content-type")

        is_cached_json = (
            status == 200
            and bool(body)
            and content_type is not None
            and content_type.strip().lower().startswith(_JSON_CONTENT_TYPE)
        )
        if not is_cached_json:
            await _send_response(send, status, headers, body)
            return

        etag = _make_etag(body)
        # Replace any downstream ETag rather than emitting a duplicate.
        headers = [(key, value) for key, value in headers if key.lower() != b"etag"]
        etag_header = (b"etag", etag.encode("latin-1"))
        headers.append(etag_header)

        if_none_match = _header_value(scope["headers"], b"if-none-match")
        if if_none_match is not None and _if_none_match_hits(
            if_none_match.decode("latin-1", "replace"), etag
        ):
            # A 304 has no body, so drop representation-specific headers.
            not_modified_headers = [
                (key, value)
                for key, value in headers
                if key.lower() not in (b"content-type", b"content-length")
            ]
            await _send_response(send, 304, not_modified_headers, b"")
            return

        await _send_response(send, status, headers, body)
