"""Path-based V2 sub-resource routes and the deprecated query-style counterparts."""
import pytest

from main import app


@pytest.fixture(autouse=True)
def _isolated_rate_limiter():
    """Keep the shared in-memory limiter out of these tests.

    They make far more expensive-tier requests than the 20/min bucket allows, so
    without isolation they would assert a 429 instead of the route behaviour
    under test. Tier selection itself is asserted separately below.
    """
    from api.utils.rate_limiter import get_rate_limiter

    stores = get_rate_limiter()._stores
    stores.clear()
    yield
    stores.clear()


def _ok() -> dict:
    return {"data": {"status": 200, "segments": []}}


# ---------------------------------------------------------------------------
# Player sub-resources
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_v2_player_profile_path_defaults_timespan(async_client, monkeypatch):
    seen = {}

    async def fake_player(player_id, timespan):
        seen["args"] = (player_id, timespan)
        return _ok()

    monkeypatch.setattr("routers.v2_router.get_player_data", fake_player)

    resp = await async_client.get("/v2/player/9")

    assert resp.status_code == 200
    assert resp.json()["status"] == "success"
    assert seen["args"] == ("9", "90d")
    assert isinstance(seen["args"][0], str)


@pytest.mark.anyio
async def test_v2_player_profile_path_passes_timespan(async_client, monkeypatch):
    seen = {}

    async def fake_player(player_id, timespan):
        seen["args"] = (player_id, timespan)
        return _ok()

    monkeypatch.setattr("routers.v2_router.get_player_data", fake_player)

    resp = await async_client.get("/v2/player/9?timespan=30d")

    assert resp.status_code == 200
    assert seen["args"] == ("9", "30d")


@pytest.mark.anyio
async def test_v2_player_profile_path_rejects_invalid_timespan(async_client):
    resp = await async_client.get("/v2/player/9?timespan=45d")
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_v2_player_matches_path_defaults_page(async_client, monkeypatch):
    seen = {}

    async def fake_matches(player_id, page):
        seen["args"] = (player_id, page)
        return _ok()

    monkeypatch.setattr("routers.v2_router.get_player_matches_data", fake_matches)

    resp = await async_client.get("/v2/player/9/matches")

    assert resp.status_code == 200
    assert seen["args"] == ("9", 1)


@pytest.mark.anyio
async def test_v2_player_matches_path_passes_page(async_client, monkeypatch):
    seen = {}

    async def fake_matches(player_id, page):
        seen["args"] = (player_id, page)
        return _ok()

    monkeypatch.setattr("routers.v2_router.get_player_matches_data", fake_matches)

    resp = await async_client.get("/v2/player/9/matches?page=2")

    assert resp.status_code == 200
    assert seen["args"] == ("9", 2)


# ---------------------------------------------------------------------------
# Team sub-resources
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_v2_team_profile_path(async_client, monkeypatch):
    seen = {}

    async def fake_team(team_id):
        seen["args"] = (team_id,)
        return _ok()

    monkeypatch.setattr("routers.v2_router.get_team_data", fake_team)

    resp = await async_client.get("/v2/team/77")

    assert resp.status_code == 200
    assert seen["args"] == ("77",)
    assert isinstance(seen["args"][0], str)


@pytest.mark.anyio
async def test_v2_team_matches_path(async_client, monkeypatch):
    seen = {}

    async def fake_team_matches(team_id, page):
        seen["args"] = (team_id, page)
        return _ok()

    monkeypatch.setattr("routers.v2_router.get_team_matches_data", fake_team_matches)

    resp = await async_client.get("/v2/team/77/matches?page=3")

    assert resp.status_code == 200
    assert seen["args"] == ("77", 3)


@pytest.mark.anyio
async def test_v2_team_transactions_path(async_client, monkeypatch):
    seen = {}

    async def fake_transactions(team_id):
        seen["args"] = (team_id,)
        return _ok()

    monkeypatch.setattr(
        "routers.v2_router.get_team_transactions_data", fake_transactions
    )

    resp = await async_client.get("/v2/team/77/transactions")

    assert resp.status_code == 200
    assert seen["args"] == ("77",)


@pytest.mark.anyio
async def test_v2_team_stats_path_defaults_date_start(async_client, monkeypatch):
    seen = {}

    async def fake_stats(team_id, date_start=""):
        seen["args"] = (team_id, date_start)
        return _ok()

    monkeypatch.setattr("routers.v2_router.get_team_stats_data", fake_stats)

    resp = await async_client.get("/v2/team/77/stats")

    assert resp.status_code == 200
    assert seen["args"] == ("77", "")


@pytest.mark.anyio
async def test_v2_team_stats_path_passes_date_start(async_client, monkeypatch):
    seen = {}

    async def fake_stats(team_id, date_start=""):
        seen["args"] = (team_id, date_start)
        return _ok()

    monkeypatch.setattr("routers.v2_router.get_team_stats_data", fake_stats)

    resp = await async_client.get("/v2/team/77/stats?date_start=2026-01-01")

    assert resp.status_code == 200
    assert seen["args"] == ("77", "2026-01-01")


@pytest.mark.anyio
async def test_v2_team_stats_path_rejects_invalid_date_start(async_client):
    resp = await async_client.get("/v2/team/77/stats?date_start=2026-13-45")
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_v2_team_roster_path(async_client, monkeypatch):
    seen = {}

    async def fake_roster(team_id):
        seen["args"] = (team_id,)
        return _ok()

    monkeypatch.setattr("routers.v2_router.get_team_roster_data", fake_roster)

    resp = await async_client.get("/v2/team/77/roster")

    assert resp.status_code == 200
    assert seen["args"] == ("77",)


@pytest.mark.anyio
async def test_v2_team_schedule_path(async_client, monkeypatch):
    seen = {}

    async def fake_schedule(team_id):
        seen["args"] = (team_id,)
        return _ok()

    monkeypatch.setattr("routers.v2_router.get_team_schedule_data", fake_schedule)

    resp = await async_client.get("/v2/team/77/schedule")

    assert resp.status_code == 200
    assert seen["args"] == ("77",)


# ---------------------------------------------------------------------------
# Match sub-resources
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_v2_match_details_path_defaults_light(async_client, monkeypatch):
    seen = {}

    async def fake_detail(match_id, light=False):
        seen["args"] = (match_id,)
        seen["kwargs"] = {"light": light}
        return _ok()

    monkeypatch.setattr("routers.v2_router.get_match_detail_data", fake_detail)

    resp = await async_client.get("/v2/match/123/details")

    assert resp.status_code == 200
    assert seen["args"] == ("123",)
    assert seen["kwargs"] == {"light": False}


@pytest.mark.anyio
async def test_v2_match_details_path_passes_light(async_client, monkeypatch):
    seen = {}

    async def fake_detail(match_id, light=False):
        seen["args"] = (match_id,)
        seen["kwargs"] = {"light": light}
        return _ok()

    monkeypatch.setattr("routers.v2_router.get_match_detail_data", fake_detail)

    resp = await async_client.get("/v2/match/123/details?light=true")

    assert resp.status_code == 200
    assert seen["args"] == ("123",)
    assert seen["kwargs"] == {"light": True}


@pytest.mark.anyio
async def test_v2_match_logs_path_allows_missing_game_id(async_client, monkeypatch):
    seen = {}

    async def fake_logs(match_id, game_id=None):
        seen["args"] = (match_id, game_id)
        return _ok()

    monkeypatch.setattr("routers.v2_router.get_match_logs_data", fake_logs)

    resp = await async_client.get("/v2/match/766311/logs")

    assert resp.status_code == 200
    assert seen["args"] == ("766311", None)


@pytest.mark.anyio
async def test_v2_match_logs_path_passes_game_id(async_client, monkeypatch):
    seen = {}

    async def fake_logs(match_id, game_id=None):
        seen["args"] = (match_id, game_id)
        return _ok()

    monkeypatch.setattr("routers.v2_router.get_match_logs_data", fake_logs)

    resp = await async_client.get("/v2/match/766311/logs?game_id=285688")

    assert resp.status_code == 200
    assert seen["args"] == ("766311", "285688")


# ---------------------------------------------------------------------------
# Validation, 404 and pagination bounds
# ---------------------------------------------------------------------------


@pytest.mark.anyio
@pytest.mark.parametrize(
    "path",
    [
        "/v2/player/abc",
        "/v2/team/abc",
        "/v2/match/abc/details",
        "/v2/match/abc/logs",
        "/v2/player/abc/matches",
        "/v2/team/abc/matches",
        "/v2/team/abc/transactions",
        "/v2/team/abc/stats",
        "/v2/team/abc/roster",
        "/v2/team/abc/schedule",
        "/v2/match/123/logs?game_id=xyz",
    ],
)
async def test_v2_subresource_rejects_invalid_ids(async_client, path):
    resp = await async_client.get(path)
    assert resp.status_code == 400


@pytest.mark.anyio
@pytest.mark.parametrize("page", ["0", "101"])
async def test_v2_team_matches_rejects_out_of_range_page(async_client, page):
    resp = await async_client.get(f"/v2/team/77/matches?page={page}")
    assert resp.status_code == 400


@pytest.mark.anyio
@pytest.mark.parametrize("page", ["0", "101"])
async def test_v2_player_matches_rejects_out_of_range_page(async_client, page):
    resp = await async_client.get(f"/v2/player/9/matches?page={page}")
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_v2_unknown_team_subresource_is_a_real_404(async_client):
    resp = await async_client.get("/v2/team/1/nope")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# The query-style routes keep working, with q marked deprecated
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_v2_team_query_style_stats_still_works(async_client, monkeypatch):
    seen = {}

    async def fake_stats(team_id, date_start=""):
        seen["args"] = (team_id, date_start)
        return _ok()

    monkeypatch.setattr("routers.v2_router.get_team_stats_data", fake_stats)

    resp = await async_client.get("/v2/team?id=77&q=stats&date_start=2026-01-01")

    assert resp.status_code == 200
    assert seen["args"] == ("77", "2026-01-01")


@pytest.mark.anyio
async def test_v2_player_query_style_profile_still_works(async_client, monkeypatch):
    seen = {}

    async def fake_player(player_id, timespan):
        seen["args"] = (player_id, timespan)
        return _ok()

    monkeypatch.setattr("routers.v2_router.get_player_data", fake_player)

    resp = await async_client.get("/v2/player?id=9&q=profile")

    assert resp.status_code == 200
    assert seen["args"] == ("9", "90d")


def _query_param(schema: dict, path: str, name: str) -> dict:
    operation = schema["paths"][path]["get"]
    return next(p for p in operation["parameters"] if p["name"] == name)


def test_q_is_deprecated_only_on_the_entity_routes():
    """q selects an entity sub-resource on /v2/player and /v2/team only."""
    schema = app.openapi()

    assert _query_param(schema, "/v2/player", "q").get("deprecated") is True
    assert _query_param(schema, "/v2/team", "q").get("deprecated") is True
    # /v2/match's q is a list filter (upcoming/results/live), not an entity selector.
    assert _query_param(schema, "/v2/match", "q").get("deprecated") in (None, False)


# ---------------------------------------------------------------------------
# Rate limiting: path-based sub-resources must not fall into an unlimited tier
# ---------------------------------------------------------------------------


def test_subresource_paths_fall_in_the_expensive_rate_limit_tier():
    from api.utils.rate_limiter import _match_tier

    assert _match_tier("/v2/team/1/roster", "") == "expensive"
    assert _match_tier("/v2/player/9/matches", "") == "expensive"
    assert _match_tier("/v2/match/766311/logs", "") == "expensive"
    assert _match_tier("/v2/match/766311/details", "") == "expensive"
