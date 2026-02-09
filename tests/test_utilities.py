"""Tests for utility modules: pagination, html_parsers, error_handling, cache_manager."""
import pytest
from datetime import timedelta

from fastapi import HTTPException

from utils.pagination import PaginationConfig
from utils.html_parsers import parse_eta_to_timedelta
from utils.error_handling import validate_region, validate_timespan, validate_match_query, validate_event_query
from utils.cache_manager import CacheManager


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
