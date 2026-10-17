"""Endpoint smoke tests for original and v2 routers."""
import pytest


@pytest.mark.anyio
async def test_version_endpoint(async_client):
    resp = await async_client.get("/version")
    assert resp.status_code == 200
    data = resp.json()
    assert data["version"] == "2.0.0"
    assert data["default_api"] == "v2"


@pytest.mark.anyio
async def test_v2_health(async_client):
    resp = await async_client.get("/v2/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert "data" in data


@pytest.mark.anyio
async def test_v2_invalid_region_returns_400(async_client):
    resp = await async_client.get("/v2/rankings?region=invalid_xyz")
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_v2_invalid_match_query_returns_400(async_client):
    resp = await async_client.get("/v2/match?q=bad_query")
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_v2_invalid_timespan_returns_400(async_client):
    resp = await async_client.get("/v2/stats?region=na&timespan=45")
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_v2_invalid_event_query_returns_400(async_client):
    resp = await async_client.get("/v2/events?q=bad_query")
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_original_news_not_redirect(async_client):
    """Original /news endpoint should respond directly (not redirect)."""
    resp = await async_client.get("/news", follow_redirects=False)
    # Should not be a 301 redirect — it serves directly
    assert resp.status_code != 301


@pytest.mark.anyio
async def test_original_invalid_match_returns_error(async_client):
    """Original /match with bad q should return error dict, not 400."""
    resp = await async_client.get("/match?q=bad_query", follow_redirects=False)
    assert resp.status_code == 200
    data = resp.json()
    assert "error" in data


@pytest.mark.anyio
async def test_original_player_rejects_invalid_id(async_client):
    resp = await async_client.get("/player?id=abc")
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_original_player_rejects_invalid_timespan(async_client):
    resp = await async_client.get("/player?id=9&timespan=45d")
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_original_match_detail_rejects_invalid_id(async_client):
    resp = await async_client.get("/match/details?match_id=abc")
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_v2_match_detail_exposes_team_ids(async_client, monkeypatch):
    async def fake_match_detail(match_id):
        return {
            "data": {
                "status": 200,
                "segments": [
                    {
                        "match_id": match_id,
                        "teams": [
                            {"id": "100", "name": "Team One"},
                            {"id": "200", "name": "Team Two"},
                        ],
                    }
                ],
            }
        }

    monkeypatch.setattr("routers.v2_router.get_match_detail_data", fake_match_detail)

    resp = await async_client.get("/v2/match/details?match_id=123")
    assert resp.status_code == 200
    assert resp.json()["data"]["segments"][0]["teams"] == [
        {"id": "100", "name": "Team One"},
        {"id": "200", "name": "Team Two"},
    ]


@pytest.mark.anyio
async def test_original_match_detail_strips_team_ids(async_client, monkeypatch):
    async def fake_match_detail(match_id):
        return {
            "data": {
                "status": 200,
                "segments": [
                    {
                        "match_id": match_id,
                        "teams": [
                            {"id": "100", "name": "Team One"},
                            {"id": "200", "name": "Team Two"},
                        ],
                    }
                ],
            }
        }

    monkeypatch.setattr("routers.vlr_router.get_match_detail_data", fake_match_detail)

    resp = await async_client.get("/match/details?match_id=123")
    assert resp.status_code == 200
    assert resp.json()["data"]["segments"][0]["teams"] == [
        {"name": "Team One"},
        {"name": "Team Two"},
    ]


@pytest.mark.anyio
async def test_v2_wrap_propagates_scraper_error_status(async_client, monkeypatch):
    async def fake_news():
        return {"data": {"status": 502, "error": "upstream failure", "segments": []}}

    monkeypatch.setattr("routers.v2_router.get_news_data", fake_news)
    resp = await async_client.get("/v2/news")
    assert resp.status_code == 502
    assert "detail" in resp.json()


@pytest.mark.anyio
async def test_v2_events_propagates_scraper_error_status(async_client, monkeypatch):
    async def fake_events(q, page):
        return {"data": {"status": 503, "error": "events unavailable", "segments": []}}

    monkeypatch.setattr("routers.v2_router.get_events_data", fake_events)

    resp = await async_client.get("/v2/events")

    assert resp.status_code == 503
    assert resp.json()["detail"] == "events unavailable"


@pytest.mark.anyio
async def test_v2_player_propagates_scraper_error_status(async_client, monkeypatch):
    async def fake_player(player_id, timespan):
        return {
            "data": {
                "status": 404,
                "error": f"player {player_id} not found",
                "segments": [],
            }
        }

    monkeypatch.setattr("routers.v2_router.get_player_data", fake_player)

    resp = await async_client.get("/v2/player?id=9")

    assert resp.status_code == 404
    assert resp.json()["detail"] == "player 9 not found"


@pytest.mark.anyio
async def test_v2_match_rejects_oversized_workload(async_client):
    resp = await async_client.get("/v2/match?q=results&num_pages=21")
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_v2_match_rejects_pagination_for_upcoming_query(async_client):
    resp = await async_client.get("/v2/match?q=upcoming&num_pages=2")
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_original_match_rejects_pagination_for_live_score_query(async_client):
    resp = await async_client.get("/match?q=live_score&from_page=2")
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_v2_event_detail_passes_stage_through(async_client, monkeypatch):
    seen = {}

    async def fake_event_detail(event_id, stage=None):
        seen["args"] = (event_id, stage)
        return {"data": {"status": 200, "segments": {"stages": [], "prizes": []}}}

    monkeypatch.setattr("routers.v2_router.get_event_detail_data", fake_event_detail)

    resp = await async_client.get("/v2/event/2766?stage=playoffs")

    assert resp.status_code == 200
    assert seen["args"] == ("2766", "playoffs")


@pytest.mark.anyio
@pytest.mark.parametrize("stage", ["Playoffs", "group_stage", "../x", "-playoffs"])
async def test_v2_event_detail_rejects_invalid_stage_slug(async_client, stage):
    resp = await async_client.get("/v2/event/2766", params={"stage": stage})
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_v2_match_logs_passes_game_id_through(async_client, monkeypatch):
    seen = {}

    async def fake_logs(match_id, game_id=None):
        seen["args"] = (match_id, game_id)
        return {"data": {"status": 200, "segments": [{"match_id": match_id, "game_id": game_id, "rounds": []}]}}

    monkeypatch.setattr("routers.v2_router.get_match_logs_data", fake_logs)

    resp = await async_client.get("/v2/match/logs?match_id=766311&game_id=285688")

    assert resp.status_code == 200
    assert seen["args"] == ("766311", "285688")
    assert resp.json()["data"]["segments"][0]["game_id"] == "285688"


@pytest.mark.anyio
async def test_v2_match_logs_allows_missing_game_id(async_client, monkeypatch):
    seen = {}

    async def fake_logs(match_id, game_id=None):
        seen["args"] = (match_id, game_id)
        return {"data": {"status": 200, "segments": []}}

    monkeypatch.setattr("routers.v2_router.get_match_logs_data", fake_logs)

    resp = await async_client.get("/v2/match/logs?match_id=766311")

    assert resp.status_code == 200
    assert seen["args"] == ("766311", None)


@pytest.mark.anyio
@pytest.mark.parametrize("query", ["match_id=abc", "match_id=123&game_id=xyz"])
async def test_v2_match_logs_rejects_invalid_ids(async_client, query):
    resp = await async_client.get(f"/v2/match/logs?{query}")
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_original_match_logs_route(async_client, monkeypatch):
    async def fake_logs(match_id, game_id=None):
        return {"data": {"status": 200, "segments": [{"match_id": match_id, "game_id": game_id}]}}

    monkeypatch.setattr("routers.vlr_router.get_match_logs_data", fake_logs)

    resp = await async_client.get("/match/logs?match_id=766311")

    assert resp.status_code == 200
    assert resp.json()["data"]["segments"][0]["match_id"] == "766311"


def test_match_logs_falls_in_the_expensive_rate_limit_tier():
    """A logs request costs two scrapes, so it must not land in a cheap tier."""
    from api.utils.rate_limiter import _match_tier

    assert _match_tier("/v2/match/logs", "") == "expensive"
    assert _match_tier("/match/logs", "") == "expensive"

