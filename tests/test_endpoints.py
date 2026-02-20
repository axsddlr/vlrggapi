"""Endpoint smoke tests for original and v2 routers."""
import pytest
from httpx import ASGITransport, AsyncClient

from main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.anyio
async def test_version_endpoint(client):
    resp = await client.get("/version")
    assert resp.status_code == 200
    data = resp.json()
    assert data["version"] == "2.0.0"
    assert data["default_api"] == "v2"


@pytest.mark.anyio
async def test_v2_health(client):
    resp = await client.get("/v2/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert "data" in data


@pytest.mark.anyio
async def test_v2_invalid_region_returns_400(client):
    resp = await client.get("/v2/rankings?region=invalid_xyz")
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_v2_invalid_match_query_returns_400(client):
    resp = await client.get("/v2/match?q=bad_query")
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_v2_invalid_timespan_returns_400(client):
    resp = await client.get("/v2/stats?region=na&timespan=45")
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_v2_invalid_event_query_returns_400(client):
    resp = await client.get("/v2/events?q=bad_query")
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_original_news_not_redirect(client):
    """Original /news endpoint should respond directly (not redirect)."""
    resp = await client.get("/news", follow_redirects=False)
    # Should not be a 301 redirect — it serves directly
    assert resp.status_code != 301


@pytest.mark.anyio
async def test_original_invalid_match_returns_error(client):
    """Original /match with bad q should return error dict, not 400."""
    resp = await client.get("/match?q=bad_query", follow_redirects=False)
    assert resp.status_code == 200
    data = resp.json()
    assert "error" in data


@pytest.mark.anyio
async def test_v2_wrap_propagates_scraper_error_status(client, monkeypatch):
    async def fake_news():
        return {"data": {"status": 502, "error": "upstream failure", "segments": []}}

    monkeypatch.setattr("routers.v2_router.get_news_data", fake_news)
    resp = await client.get("/v2/news")
    assert resp.status_code == 502
    assert "detail" in resp.json()


@pytest.mark.anyio
async def test_v2_match_rejects_oversized_workload(client):
    resp = await client.get("/v2/match?q=results&num_pages=21")
    assert resp.status_code == 400
