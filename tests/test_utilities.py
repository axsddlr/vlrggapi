"""Tests for utility modules: pagination, html_parsers, error_handling, cache_manager."""
import asyncio
import pytest
import httpx
from datetime import timedelta

from fastapi import HTTPException

from utils.pagination import PaginationConfig, scrape_multiple_pages
from utils.http_client import fetch_with_retries
from utils.html_parsers import parse_eta_to_timedelta
from utils.error_handling import validate_region, validate_timespan, validate_match_query, validate_event_query
from utils.cache_manager import CacheManager, cache_manager
from utils.constants import CACHE_TTL_EVENTS, CACHE_TTL_MATCH_DETAIL
from api.scrapers.events import vlr_events
from api.scrapers.match_detail import vlr_match_detail


# --- PaginationConfig.get_page_range ---

class TestPaginationConfig:
    def test_default_single_page(self):
        cfg = PaginationConfig(num_pages=1)
        assert cfg.get_page_range() == (1, 1, 1)

    def test_num_pages_from_start(self):
        cfg = PaginationConfig(num_pages=5)
        assert cfg.get_page_range() == (1, 5, 5)

    def test_from_and_to_page(self):
        cfg = PaginationConfig(from_page=3, to_page=7)
        assert cfg.get_page_range() == (3, 7, 5)

    def test_from_page_with_num_pages(self):
        cfg = PaginationConfig(num_pages=3, from_page=5)
        assert cfg.get_page_range() == (5, 7, 3)

    def test_to_page_with_num_pages(self):
        cfg = PaginationConfig(num_pages=3, to_page=10)
        assert cfg.get_page_range() == (8, 10, 3)

    def test_to_page_clamps_to_1(self):
        cfg = PaginationConfig(num_pages=20, to_page=5)
        assert cfg.get_page_range() == (1, 5, 5)


# --- parse_eta_to_timedelta ---

class TestParseEta:
    def test_hours_minutes(self):
        assert parse_eta_to_timedelta("4h 1m") == timedelta(hours=4, minutes=1)

    def test_days_hours(self):
        assert parse_eta_to_timedelta("1d 2h") == timedelta(days=1, hours=2)

    def test_minutes_only(self):
        assert parse_eta_to_timedelta("30m") == timedelta(minutes=30)

    def test_live_returns_none(self):
        assert parse_eta_to_timedelta("LIVE") is None

    def test_ago_returns_none(self):
        assert parse_eta_to_timedelta("2h ago") is None

    def test_empty_returns_none(self):
        assert parse_eta_to_timedelta("") is None

    def test_none_returns_none(self):
        assert parse_eta_to_timedelta(None) is None


# --- Validators ---

class TestValidators:
    def test_validate_region_valid(self):
        assert validate_region("na") == "north-america"
        assert validate_region("eu") == "europe"

    def test_validate_region_invalid(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_region("invalid_region")
        assert exc_info.value.status_code == 400

    def test_validate_timespan_valid(self):
        for ts in ("30", "60", "90", "all"):
            validate_timespan(ts)  # Should not raise

    def test_validate_timespan_invalid(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_timespan("45")
        assert exc_info.value.status_code == 400

    def test_validate_match_query_valid(self):
        for q in ("upcoming", "upcoming_extended", "live_score", "results"):
            validate_match_query(q)  # Should not raise

    def test_validate_match_query_invalid(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_match_query("invalid")
        assert exc_info.value.status_code == 400

    def test_validate_event_query_valid(self):
        for q in ("upcoming", "completed", None):
            validate_event_query(q)  # Should not raise

    def test_validate_event_query_invalid(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_event_query("invalid")
        assert exc_info.value.status_code == 400


# --- CacheManager ---

class TestCacheManager:
    def test_get_set(self):
        cm = CacheManager()
        cm.set(60, "value1", "key1")
        assert cm.get(60, "key1") == "value1"

    def test_get_missing(self):
        cm = CacheManager()
        assert cm.get(60, "nonexistent") is None

    def test_different_args_different_keys(self):
        cm = CacheManager()
        cm.set(60, "a", "key1")
        cm.set(60, "b", "key2")
        assert cm.get(60, "key1") == "a"
        assert cm.get(60, "key2") == "b"

    def test_invalidate(self):
        cm = CacheManager()
        cm.set(60, "value", "key1")
        cm.invalidate(60, "key1")
        assert cm.get(60, "key1") is None

    def test_clear_all(self):
        cm = CacheManager()
        cm.set(60, "a", "k1")
        cm.set(120, "b", "k2")
        cm.clear_all()
        assert cm.get(60, "k1") is None
        assert cm.get(120, "k2") is None

    def test_make_cache_key_deterministic(self):
        key1 = CacheManager.make_cache_key("a", "b", x=1)
        key2 = CacheManager.make_cache_key("a", "b", x=1)
        assert key1 == key2

    def test_make_cache_key_different_args(self):
        key1 = CacheManager.make_cache_key("a")
        key2 = CacheManager.make_cache_key("b")
        assert key1 != key2

    def test_set_if_cacheable_skips_error_statuses(self):
        cm = CacheManager()
        stored = cm.set_if_cacheable(60, {"data": {"status": 503, "segments": []}}, "key1")
        assert stored is False
        assert cm.get(60, "key1") is None

    def test_set_if_cacheable_skips_error_payloads(self):
        cm = CacheManager()
        stored = cm.set_if_cacheable(60, {"data": {"status": 200, "error": "bad gateway"}}, "key1")
        assert stored is False
        assert cm.get(60, "key1") is None

    @pytest.mark.anyio
    async def test_get_or_create_async_coalesces_concurrent_calls(self):
        cm = CacheManager()
        calls = 0

        async def producer():
            nonlocal calls
            calls += 1
            await asyncio.sleep(0)
            return {"data": {"status": 200, "segments": ["ok"]}}

        results = await asyncio.gather(
            cm.get_or_create_async(60, producer, "key1"),
            cm.get_or_create_async(60, producer, "key1"),
            cm.get_or_create_async(60, producer, "key1"),
        )

        assert calls == 1
        assert results == [
            {"data": {"status": 200, "segments": ["ok"]}},
            {"data": {"status": 200, "segments": ["ok"]}},
            {"data": {"status": 200, "segments": ["ok"]}},
        ]
        assert cm.get(60, "key1") == {"data": {"status": 200, "segments": ["ok"]}}

    @pytest.mark.anyio
    async def test_get_or_create_async_does_not_cache_non_cacheable_results(self):
        cm = CacheManager()
        calls = 0

        async def producer():
            nonlocal calls
            calls += 1
            await asyncio.sleep(0)
            return {"data": {"status": 503, "segments": []}}

        first, second = await asyncio.gather(
            cm.get_or_create_async(60, producer, "key1"),
            cm.get_or_create_async(60, producer, "key1"),
        )
        third = await cm.get_or_create_async(60, producer, "key1")

        assert calls == 2
        assert first == {"data": {"status": 503, "segments": []}}
        assert second == {"data": {"status": 503, "segments": []}}
        assert third == {"data": {"status": 503, "segments": []}}
        assert cm.get(60, "key1") is None


class FakeResponse:
    def __init__(self, status_code: int, text: str = "<html></html>"):
        self.status_code = status_code
        self.text = text


class FakeAsyncClient:
    def __init__(self, responses: dict[str, list[FakeResponse | Exception]]):
        self._responses = responses
        self.calls: list[tuple[str, int | None]] = []

    async def get(self, url: str, timeout=None):
        self.calls.append((url, timeout))
        response = self._responses[url].pop(0)
        if isinstance(response, Exception):
            raise response
        return response


@pytest.mark.anyio
async def test_scrape_multiple_pages_raises_when_any_page_exhausts_retries(monkeypatch):
    client = FakeAsyncClient(
        {
            "https://example.test/page-1": [FakeResponse(200)],
            "https://example.test/page-2": [FakeResponse(503), FakeResponse(503)],
        }
    )

    async def fake_sleep(_delay):
        return None

    monkeypatch.setattr("utils.pagination.get_http_client", lambda: client)
    monkeypatch.setattr("utils.pagination.asyncio.sleep", fake_sleep)

    def parse_func(_html, page: int):
        return [{"page": page}]

    config = PaginationConfig(
        num_pages=2,
        max_retries=2,
        request_delay=0.1,
        timeout=5,
    )

    with pytest.raises(HTTPException) as exc_info:
        await scrape_multiple_pages(
            base_url="https://example.test",
            parse_func=parse_func,
            config=config,
            page_url_func=lambda _base, page: f"https://example.test/page-{page}",
        )

    assert exc_info.value.status_code == 502
    assert "Pages with exhausted retries: 2" in exc_info.value.detail
    assert client.calls == [
        ("https://example.test/page-1", 5),
        ("https://example.test/page-2", 5),
        ("https://example.test/page-2", 5),
    ]


@pytest.mark.anyio
async def test_vlr_events_does_not_cache_non_200_responses(monkeypatch):
    cache_manager.clear_all()
    client = FakeAsyncClient(
        {
            "https://www.vlr.gg/events": [
                FakeResponse(503),
                FakeResponse(503),
                FakeResponse(503),
                FakeResponse(200),
            ],
        }
    )

    monkeypatch.setattr("api.scrapers.events.get_http_client", lambda: client)

    first = await vlr_events()
    second = await vlr_events()

    assert first["data"]["status"] == 503
    assert second["data"]["status"] == 200
    assert client.calls == [
        ("https://www.vlr.gg/events", None),
        ("https://www.vlr.gg/events", None),
        ("https://www.vlr.gg/events", None),
        ("https://www.vlr.gg/events", None),
    ]
    assert cache_manager.get(CACHE_TTL_EVENTS, "events", True, True, 1) == second
    cache_manager.clear_all()


@pytest.mark.anyio
async def test_vlr_match_detail_does_not_cache_non_200_responses(monkeypatch):
    cache_manager.clear_all()
    client = FakeAsyncClient(
        {
            "https://www.vlr.gg/123": [
                FakeResponse(503),
                FakeResponse(503),
                FakeResponse(503),
                FakeResponse(200),
            ],
        }
    )

    monkeypatch.setattr("api.scrapers.match_detail.get_http_client", lambda: client)

    first = await vlr_match_detail("123")
    second = await vlr_match_detail("123")

    assert first["data"]["status"] == 503
    assert second["data"]["status"] == 200
    assert client.calls == [
        ("https://www.vlr.gg/123", None),
        ("https://www.vlr.gg/123", None),
        ("https://www.vlr.gg/123", None),
        ("https://www.vlr.gg/123", None),
    ]
    assert cache_manager.get(CACHE_TTL_MATCH_DETAIL, "match_detail", "123") == second
    cache_manager.clear_all()


@pytest.mark.anyio
async def test_fetch_with_retries_retries_retryable_status_codes(monkeypatch):
    client = FakeAsyncClient(
        {
            "https://example.test/resource": [FakeResponse(503), FakeResponse(200)],
        }
    )

    async def fake_sleep(_delay):
        return None

    monkeypatch.setattr("utils.http_client.asyncio.sleep", fake_sleep)

    response = await fetch_with_retries(
        "https://example.test/resource",
        client=client,
        max_retries=2,
        request_delay=0.1,
    )

    assert response.status_code == 200
    assert client.calls == [
        ("https://example.test/resource", None),
        ("https://example.test/resource", None),
    ]


@pytest.mark.anyio
async def test_fetch_with_retries_retries_request_errors(monkeypatch):
    client = FakeAsyncClient(
        {
            "https://example.test/resource": [
                httpx.ReadTimeout("timed out"),
                FakeResponse(200),
            ],
        }
    )

    async def fake_sleep(_delay):
        return None

    monkeypatch.setattr("utils.http_client.asyncio.sleep", fake_sleep)

    response = await fetch_with_retries(
        "https://example.test/resource",
        client=client,
        max_retries=2,
        request_delay=0.1,
    )

    assert response.status_code == 200
    assert client.calls == [
        ("https://example.test/resource", None),
        ("https://example.test/resource", None),
    ]
