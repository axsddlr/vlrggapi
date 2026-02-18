"""
Error handling utilities for VLR.GG API
"""
import asyncio
import logging
from functools import wraps

import httpx
from fastapi import HTTPException

from utils.constants import (
    MAX_MATCH_PAGE_WINDOW,
    MAX_MATCH_RETRIES,
    MAX_MATCH_TIMEOUT,
)
from utils.utils import region

logger = logging.getLogger(__name__)

VALID_TIMESPANS = {"30", "60", "90", "all"}
VALID_PLAYER_TIMESPANS = {"30d", "60d", "90d", "all"}
VALID_MATCH_QUERIES = {"upcoming", "upcoming_extended", "live_score", "results"}
VALID_EVENT_QUERIES = {"upcoming", "completed", None}


def handle_scraper_errors(func):
    """Decorator to handle common scraper errors. Works with both sync and async functions."""
    def _raise_http_error(exc: Exception):
        if isinstance(exc, HTTPException):
            raise exc

        if isinstance(exc, httpx.TimeoutException):
            logger.error("Timeout in %s: %s", func.__name__, exc)
            raise HTTPException(status_code=504, detail="Upstream request timed out")

        if isinstance(exc, httpx.HTTPError):
            logger.error("HTTP error in %s: %s", func.__name__, exc)
            raise HTTPException(status_code=502, detail="Failed to fetch data from VLR.GG")

        logger.exception("Unexpected error in %s", func.__name__)
        raise HTTPException(status_code=500, detail="Internal server error")

    if asyncio.iscoroutinefunction(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as exc:
                _raise_http_error(exc)
        return wrapper
    else:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                _raise_http_error(exc)
        return wrapper


def validate_region(key: str) -> str:
    """Validate region key and return the full region name. Raises 400 on invalid."""
    if key not in region:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid region '{key}'. Valid regions: {', '.join(sorted(region.keys()))}",
        )
    return region[key]


def validate_timespan(ts: str):
    """Validate timespan value. Raises 400 on invalid."""
    if ts not in VALID_TIMESPANS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid timespan '{ts}'. Valid values: {', '.join(sorted(VALID_TIMESPANS))}",
        )


def validate_match_query(q: str):
    """Validate match query parameter. Raises 400 on invalid."""
    if q not in VALID_MATCH_QUERIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid match query '{q}'. Valid values: {', '.join(sorted(VALID_MATCH_QUERIES))}",
        )


def validate_event_query(q: str | None):
    """Validate event query parameter. Raises 400 on invalid."""
    if q not in VALID_EVENT_QUERIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid event query '{q}'. Valid values: upcoming, completed",
        )


def validate_player_timespan(ts: str):
    """Validate player timespan value. Raises 400 on invalid."""
    if ts not in VALID_PLAYER_TIMESPANS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid timespan '{ts}'. Valid values: {', '.join(sorted(VALID_PLAYER_TIMESPANS))}",
        )


def validate_id_param(value: str, name: str = "id"):
    """Validate that an ID parameter is a positive integer string. Raises 400 on invalid."""
    if not value or not value.isdigit():
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {name} '{value}'. Must be a numeric ID.",
        )


def validate_page_param(page: int, max_page: int = 100) -> int:
    """Validate and clamp page parameter."""
    if page < 1:
        return 1
    if page > max_page:
        return max_page
    return page


def validate_match_workload(
    num_pages: int,
    from_page: int | None,
    to_page: int | None,
    max_retries: int,
    timeout: int,
):
    """Validate expensive match scraping options to avoid resource exhaustion."""
    if from_page is not None and to_page is not None:
        requested_pages = max(1, to_page - from_page + 1)
    else:
        requested_pages = num_pages

    if requested_pages > MAX_MATCH_PAGE_WINDOW:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Requested page window ({requested_pages}) exceeds the maximum "
                f"allowed ({MAX_MATCH_PAGE_WINDOW})."
            ),
        )

    if max_retries > MAX_MATCH_RETRIES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Max retries ({max_retries}) exceeds the maximum allowed "
                f"({MAX_MATCH_RETRIES})."
            ),
        )

    if timeout > MAX_MATCH_TIMEOUT:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Timeout ({timeout}s) exceeds the maximum allowed "
                f"({MAX_MATCH_TIMEOUT}s)."
            ),
        )
