"""
Error handling utilities for VLR.GG API
"""
import asyncio
import logging
from functools import wraps

import httpx
from fastapi import HTTPException

from utils.utils import region

logger = logging.getLogger(__name__)

VALID_TIMESPANS = {"30", "60", "90", "all"}
VALID_MATCH_QUERIES = {"upcoming", "upcoming_extended", "live_score", "results"}
VALID_EVENT_QUERIES = {"upcoming", "completed", None}


def handle_scraper_errors(func):
    """Decorator to handle common scraper errors. Works with both sync and async functions."""
    if asyncio.iscoroutinefunction(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except HTTPException:
                raise
            except httpx.HTTPError as e:
                logger.error("Request failed in %s: %s", func.__name__, e)
                return {
                    "data": {
                        "status": 500,
                        "error": "Failed to fetch data from VLR.GG",
                        "segments": [],
                    }
                }
            except Exception as e:
                logger.error("Unexpected error in %s: %s", func.__name__, e)
                return {
                    "data": {
                        "status": 500,
                        "error": "Internal server error",
                        "segments": [],
                    }
                }
        return wrapper
    else:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except HTTPException:
                raise
            except httpx.HTTPError as e:
                logger.error("Request failed in %s: %s", func.__name__, e)
                return {
                    "data": {
                        "status": 500,
                        "error": "Failed to fetch data from VLR.GG",
                        "segments": [],
                    }
                }
            except Exception as e:
                logger.error("Unexpected error in %s: %s", func.__name__, e)
                return {
                    "data": {
                        "status": 500,
                        "error": "Internal server error",
                        "segments": [],
                    }
                }
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


def validate_page_param(page: int, max_page: int = 100) -> int:
    """Validate and clamp page parameter."""
    if page < 1:
        return 1
    if page > max_page:
        return max_page
    return page
