"""Conditional GET (ETag / If-None-Match) behaviour for slow-moving endpoints."""
import hashlib
import re

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.applications import Starlette
from starlette.background import BackgroundTask
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from starlette.routing import Route

from api.utils.rate_limiter import RateLimitMiddleware
from main import app
from utils.conditional import ConditionalGetMiddleware, _is_conditional_request

_ETAG_RE = re.compile(r'^"[0-9a-f]{64}"$')


async def _fake_rankings(region):
    return {"data": {"status": 200, "segments": [{"region": region, "teams": []}]}}


async def _fake_news():
    return {"data": {"status": 200, "segments": [{"title": "Patch notes"}]}}


async def _fake_team_roster(team_id):
    return {"data": {"status": 200, "segments": [{"id": team_id, "players": []}]}}


async def _fake_rankings_error(region):
    return {"data": {"status": 502, "error": "upstream unavailable", "segments": []}}


# ---------------------------------------------------------------------------
# Round trip: 200 + ETag, then 304 with the same tag
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_rankings_returns_etag_then_304(async_client, monkeypatch):
    monkeypatch.setattr("routers.v2_router.get_rankings_data", _fake_rankings)

    first = await async_client.get("/v2/rankings?region=na")
    assert first.status_code == 200
    etag = first.headers["etag"]
    assert _ETAG_RE.match(etag)
    # Strong validator: sha256 of the exact body bytes, quoted.
    assert etag == '"' + hashlib.sha256(first.content).hexdigest() + '"'
    assert "cache-control" not in first.headers

    second = await async_client.get(
        "/v2/rankings?region=na", headers={"If-None-Match": etag}
    )
    assert second.status_code == 304
    assert second.headers["etag"] == etag
    assert second.content == b""
    # A 304 is a bodiless response: no content-type, no cache-control.
    assert "content-type" not in second.headers
    assert "cache-control" not in second.headers


@pytest.mark.anyio
async def test_mismatched_if_none_match_returns_full_body(async_client, monkeypatch):
    monkeypatch.setattr("routers.v2_router.get_rankings_data", _fake_rankings)

    first = await async_client.get("/v2/rankings?region=na")
    etag = first.headers["etag"]

    second = await async_client.get(
        "/v2/rankings?region=na", headers={"If-None-Match": '"deadbeef"'}
    )
    assert second.status_code == 200
    assert second.headers["etag"] == etag
    assert second.content


# ---------------------------------------------------------------------------
# If-None-Match grammar: *, weak tags, comma-separated lists
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_wildcard_matches(async_client, monkeypatch):
    monkeypatch.setattr("routers.v2_router.get_rankings_data", _fake_rankings)

    resp = await async_client.get(
        "/v2/rankings?region=na", headers={"If-None-Match": "*"}
    )

    assert resp.status_code == 304
    assert resp.content == b""
    assert _ETAG_RE.match(resp.headers["etag"])


@pytest.mark.anyio
async def test_weak_client_tag_matches(async_client, monkeypatch):
    monkeypatch.setattr("routers.v2_router.get_rankings_data", _fake_rankings)

    first = await async_client.get("/v2/rankings?region=na")
    etag = first.headers["etag"]

    resp = await async_client.get(
        "/v2/rankings?region=na", headers={"If-None-Match": f"W/{etag}"}
    )

    assert resp.status_code == 304
    assert resp.headers["etag"] == etag


@pytest.mark.anyio
async def test_comma_separated_list_containing_the_tag_matches(async_client, monkeypatch):
    monkeypatch.setattr("routers.v2_router.get_rankings_data", _fake_rankings)

    first = await async_client.get("/v2/rankings?region=na")
    etag = first.headers["etag"]

    resp = await async_client.get(
        "/v2/rankings?region=na",
        headers={"If-None-Match": f'"nope", {etag}, W/"other"'},
    )

    assert resp.status_code == 304


# ---------------------------------------------------------------------------
# Scope: only the slow movers get an ETag
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_unlisted_path_never_gets_an_etag(async_client, monkeypatch):
    monkeypatch.setattr("routers.v2_router.get_news_data", _fake_news)

    resp = await async_client.get(
        "/v2/news", headers={"If-None-Match": "*"}
    )

    assert resp.status_code == 200
    assert "etag" not in resp.headers
    assert resp.content


@pytest.mark.anyio
async def test_team_roster_subresource_gets_an_etag(async_client, monkeypatch):
    monkeypatch.setattr("routers.v2_router.get_team_roster_data", _fake_team_roster)

    resp = await async_client.get("/v2/team?id=1&q=roster")

    assert resp.status_code == 200
    assert _ETAG_RE.match(resp.headers["etag"])


@pytest.mark.anyio
async def test_error_response_gets_no_etag(async_client, monkeypatch):
    monkeypatch.setattr("routers.v2_router.get_rankings_data", _fake_rankings_error)

    resp = await async_client.get(
        "/v2/rankings?region=na", headers={"If-None-Match": "*"}
    )

    assert resp.status_code == 502
    assert "etag" not in resp.headers


@pytest.mark.anyio
async def test_version_endpoint_gets_no_etag(async_client):
    resp = await async_client.get("/version", headers={"If-None-Match": "*"})

    assert resp.status_code == 200
    assert "etag" not in resp.headers


# ---------------------------------------------------------------------------
# Ordering consequence: the conditional layer sits inside the rate limiter
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_304_still_consumes_rate_limit_budget(async_client, monkeypatch):
    monkeypatch.setattr("routers.v2_router.get_rankings_data", _fake_rankings)

    first = await async_client.get("/v2/rankings?region=na")
    etag = first.headers["etag"]
    assert "x-ratelimit-remaining" in first.headers
    first_remaining = int(first.headers["x-ratelimit-remaining"])

    second = await async_client.get(
        "/v2/rankings?region=na", headers={"If-None-Match": etag}
    )
    assert second.status_code == 304
    assert "x-ratelimit-limit" in second.headers
    assert "x-ratelimit-remaining" in second.headers
    # The 304 passed through the limiter, so it consumed one slot.
    assert int(second.headers["x-ratelimit-remaining"]) == first_remaining - 1


# ---------------------------------------------------------------------------
# Robustness: malformed clients must never break the response
# ---------------------------------------------------------------------------


@pytest.mark.anyio
@pytest.mark.parametrize("header", ['"abc', ",,,", '"a,b"', "garbage", 'W/'])
async def test_malformed_if_none_match_returns_200(async_client, monkeypatch, header):
    monkeypatch.setattr("routers.v2_router.get_rankings_data", _fake_rankings)

    resp = await async_client.get(
        "/v2/rankings?region=na", headers={"If-None-Match": header}
    )

    assert resp.status_code == 200
    assert resp.content


@pytest.mark.anyio
async def test_post_is_ignored(async_client):
    # No POST route exists, so the request 405s; the key point is that the
    # conditional layer never sees it and therefore never adds an ETag.
    resp = await async_client.post("/v2/rankings?region=na")

    assert resp.status_code == 405
    assert "etag" not in resp.headers


# ---------------------------------------------------------------------------
# The middleware must not disturb what the application already produced
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_background_task_and_downstream_headers_are_preserved():
    ran: list[str] = []

    async def handler(request):
        return JSONResponse(
            {"ok": True},
            headers={"X-Custom": "kept"},
            background=BackgroundTask(ran.append, "done"),
        )

    wrapped = ConditionalGetMiddleware(Starlette(routes=[Route("/team", handler)]))
    transport = ASGITransport(app=wrapped)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        first = await client.get("/team")
        assert first.status_code == 200
        assert first.headers["x-custom"] == "kept"
        assert ran == ["done"]

        second = await client.get(
            "/team", headers={"If-None-Match": first.headers["etag"]}
        )
        assert second.status_code == 304
        assert second.headers["x-custom"] == "kept"
        # The downstream app still ran normally to produce the validator.
        assert ran == ["done", "done"]


@pytest.mark.anyio
async def test_non_json_200_on_a_slow_mover_gets_no_etag():
    async def handler(request):
        return JSONResponse({"ok": True}, media_type="text/plain")

    wrapped = ConditionalGetMiddleware(Starlette(routes=[Route("/stats", handler)]))
    transport = ASGITransport(app=wrapped)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/stats")

    assert resp.status_code == 200
    assert "etag" not in resp.headers


# ---------------------------------------------------------------------------
# Path matching unit tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
@pytest.mark.parametrize(
    "path",
    [
        "/rankings",
        "/rankings/",
        "/v2/rankings",
        "/v2/rankings/",
        "/stats",
        "/v2/stats",
        "/v2/stats/",
        "/team",
        "/v2/team",
        "/v2/team/",
        "/v2/team/123",
        "/v2/team/123/roster",
        "/v2/Team/123/Roster",
    ],
)
async def test_slow_mover_paths_match(path):
    assert _is_conditional_request("GET", path)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "path",
    [
        "/v2/teamsomething",
        "/teamsomething",
        "/v2/teamwork",
        "/v2/rankings-archive",
        "/v2/news",
        "/news",
        "/version",
        "/v2/health",
    ],
)
async def test_non_slow_mover_paths_do_not_match(path):
    assert not _is_conditional_request("GET", path)


@pytest.mark.anyio
@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"])
async def test_non_get_methods_are_rejected(method):
    assert not _is_conditional_request(method, "/v2/rankings")


# ---------------------------------------------------------------------------
# Middleware registration order
# ---------------------------------------------------------------------------


def test_middleware_order_is_cors_rate_limit_conditional_get():
    classes = [middleware.cls for middleware in app.user_middleware]

    assert classes[:3] == [CORSMiddleware, RateLimitMiddleware, ConditionalGetMiddleware]


# ---------------------------------------------------------------------------
# Path normalisation parity with the rate limiter
# ---------------------------------------------------------------------------
# utils.conditional._normalise is a deliberate copy of the rate limiter's
# helper rather than a shared import: utils must not depend on api. Both layers
# have to agree on what a path is - the limiter decides whether a request is
# admitted, conditional GET decides whether its body can be skipped - so this
# parity test is what keeps the copies from drifting apart.


@pytest.mark.parametrize(
    "path",
    [
        "/rankings",
        "/v2/rankings",
        "/v2/stats/",
        "/Team/123",
        "/v2/team/123/roster",
        "/v2",
        "/",
        "",
        "/v2/news",
        "/v2/teamwork",
        "/v3/team",
    ],
)
def test_normalisation_matches_the_rate_limiter(path):
    from api.utils.rate_limiter import _normalise as limiter_normalise
    from utils.conditional import _normalise as conditional_normalise

    assert conditional_normalise(path) == limiter_normalise(path)
