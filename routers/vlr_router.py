"""
Original unversioned API router — preserved for backwards compatibility.
"""
from fastapi import APIRouter, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from api.scrapers import (
    vlr_events,
    vlr_live_score,
    vlr_match_results,
    vlr_news,
    vlr_rankings,
    vlr_stats,
    vlr_upcoming_matches,
    vlr_upcoming_matches_extended,
    check_health,
)
from utils.constants import RATE_LIMIT

router = APIRouter(tags=["Default"])
limiter = Limiter(key_func=get_remote_address)


@router.get("/news")
@limiter.limit(RATE_LIMIT)
async def VLR_news(request: Request):
    return await vlr_news()


@router.get("/stats")
@limiter.limit(RATE_LIMIT)
async def VLR_stats(
    request: Request,
    region: str = Query(..., description="Region shortname"),
    timespan: str = Query(..., description="Timespan (30, 60, 90, or all)"),
):
    """
    Get VLR stats with query parameters.

    region shortnames:\n
        "na": "north-america",\n
        "eu": "europe",\n
        "ap": "asia-pacific",\n
        "sa": "latin-america",\n
        "jp": "japan",\n
        "oce": "oceania",\n
        "mn": "mena"\n
    """
    return await vlr_stats(region, timespan)


@router.get("/rankings")
@limiter.limit(RATE_LIMIT)
async def VLR_ranks(
    request: Request, region: str = Query(..., description="Region shortname")
):
    """
    Get VLR rankings for a specific region.

    region shortnames:\n
        "na": "north-america",\n
        "eu": "europe",\n
        "ap": "asia-pacific",\n
        "la": "latin-america",\n
        "la-s": "la-s",\n
        "la-n": "la-n",\n
        "oce": "oceania",\n
        "kr": "korea",\n
        "mn": "mena",\n
        "gc": "game-changers",\n
        "br": "Brazil",\n
        "cn": "china",\n
        "jp": "japan",\n
        "col": "collegiate",\n
    """
    data = await vlr_rankings(region)
    # Return old shape: {"status": int, "data": [...]}
    if "data" in data and "segments" in data["data"]:
        return {
            "status": data["data"]["status"],
            "data": data["data"]["segments"],
        }
    return data


@router.get("/match")
@limiter.limit(RATE_LIMIT)
async def VLR_match(
    request: Request,
    q: str,
    num_pages: int = Query(1, description="Number of pages to scrape (default: 1)", ge=1, le=600),
    from_page: int = Query(None, description="Starting page number (1-based, optional)", ge=1, le=600),
    to_page: int = Query(None, description="Ending page number (1-based, inclusive, optional)", ge=1, le=600),
    max_retries: int = Query(3, description="Maximum retry attempts per page (default: 3)", ge=1, le=5),
    request_delay: float = Query(1.0, description="Delay between requests in seconds (default: 1.0)", ge=0.5, le=5.0),
    timeout: int = Query(30, description="Request timeout in seconds (default: 30)", ge=10, le=120)
):
    """
    query parameters:\n
        "upcoming": upcoming matches (from homepage),\n
        "upcoming_extended": upcoming matches (from paginated /matches page),\n
        "live_score": live match scores,\n
        "results": match results,\n

    Page Range Options:
    - num_pages: Number of pages from page 1 (ignored if from_page/to_page specified)
    - from_page: Starting page number (1-based, optional)
    - to_page: Ending page number (1-based, inclusive, optional)
    """
    if q == "upcoming":
        return await vlr_upcoming_matches(num_pages, from_page, to_page)
    elif q == "upcoming_extended":
        return await vlr_upcoming_matches_extended(num_pages, from_page, to_page, max_retries, request_delay, timeout)
    elif q == "live_score":
        return await vlr_live_score(num_pages, from_page, to_page)
    elif q == "results":
        return await vlr_match_results(num_pages, from_page, to_page, max_retries, request_delay, timeout)
    else:
        return {"error": "Invalid query parameter"}


@router.get("/events")
@limiter.limit(RATE_LIMIT)
async def VLR_events(
    request: Request,
    q: str = Query(
        None,
        description="Event type filter",
        example="completed",
        enum=["upcoming", "completed"]
    ),
    page: int = Query(
        1,
        description="Page number for pagination (only applies to completed events)",
        example=1,
        ge=1,
        le=100
    )
):
    """
    Get Valorant events from VLR.GG with optional filtering and pagination.
    """
    if q == "upcoming":
        return await vlr_events(upcoming=True, completed=False, page=page)
    elif q == "completed":
        return await vlr_events(upcoming=False, completed=True, page=page)
    else:
        return await vlr_events(upcoming=True, completed=True, page=page)


@router.get("/health")
async def health():
    return await check_health()
