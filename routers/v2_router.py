"""
V2 API router — standardized responses, validation, Pydantic models.
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
from utils.error_handling import validate_match_query, validate_event_query

router = APIRouter(prefix="/v2", tags=["v2"])
limiter = Limiter(key_func=get_remote_address)


def _wrap_v2(scraper_result: dict) -> dict:
    """Wrap scraper result into the standardized V2 response shape."""
    if "data" in scraper_result:
        inner = scraper_result["data"]
        return {
            "status": "success",
            "data": inner,
        }
    return {"status": "success", "data": scraper_result}


@router.get("/news")
@limiter.limit(RATE_LIMIT)
async def v2_news(request: Request):
    """Get the latest Valorant esports news from VLR.GG."""
    result = await vlr_news()
    return _wrap_v2(result)


@router.get("/stats")
@limiter.limit(RATE_LIMIT)
async def v2_stats(
    request: Request,
    region: str = Query(..., description="Region shortname (na, eu, ap, la, etc.)"),
    timespan: str = Query(..., description="Timespan: 30, 60, 90, or all"),
):
    """
    Get player statistics for a region and timespan.

    Region shortnames: na, eu, ap, la, la-s, la-n, oce, kr, mn, gc, br, cn, jp, col
    """
    result = await vlr_stats(region, timespan)
    return _wrap_v2(result)


@router.get("/rankings")
@limiter.limit(RATE_LIMIT)
async def v2_rankings(
    request: Request,
    region: str = Query(..., description="Region shortname (na, eu, ap, la, etc.)"),
):
    """
    Get team rankings for a region.

    Region shortnames: na, eu, ap, la, la-s, la-n, oce, kr, mn, gc, br, cn, jp, col
    """
    result = await vlr_rankings(region)
    return _wrap_v2(result)


@router.get("/match")
@limiter.limit(RATE_LIMIT)
async def v2_match(
    request: Request,
    q: str = Query(..., description="Match type: upcoming, upcoming_extended, live_score, results"),
    num_pages: int = Query(1, description="Number of pages to scrape", ge=1, le=600),
    from_page: int = Query(None, description="Starting page number (1-based)", ge=1, le=600),
    to_page: int = Query(None, description="Ending page number (1-based, inclusive)", ge=1, le=600),
    max_retries: int = Query(3, description="Max retry attempts per page", ge=1, le=5),
    request_delay: float = Query(1.0, description="Delay between requests (seconds)", ge=0.5, le=5.0),
    timeout: int = Query(30, description="Request timeout (seconds)", ge=10, le=120),
):
    """
    Get match data by type.

    - **upcoming**: Upcoming matches from homepage
    - **upcoming_extended**: Upcoming matches from paginated /matches page
    - **live_score**: Live match scores with detail
    - **results**: Completed match results
    """
    validate_match_query(q)

    if q == "upcoming":
        result = await vlr_upcoming_matches(num_pages, from_page, to_page)
    elif q == "upcoming_extended":
        result = await vlr_upcoming_matches_extended(num_pages, from_page, to_page, max_retries, request_delay, timeout)
    elif q == "live_score":
        result = await vlr_live_score(num_pages, from_page, to_page)
    else:  # results
        result = await vlr_match_results(num_pages, from_page, to_page, max_retries, request_delay, timeout)

    return _wrap_v2(result)


@router.get("/events")
@limiter.limit(RATE_LIMIT)
async def v2_events(
    request: Request,
    q: str = Query(None, description="Event type: upcoming or completed"),
    page: int = Query(1, description="Page number (completed events only)", ge=1, le=100),
):
    """
    Get Valorant events.

    - **upcoming**: Currently active or scheduled future events
    - **completed**: Historical events that have finished
    - **omit q**: Both upcoming and completed events
    """
    validate_event_query(q)

    if q == "upcoming":
        result = await vlr_events(upcoming=True, completed=False, page=page)
    elif q == "completed":
        result = await vlr_events(upcoming=False, completed=True, page=page)
    else:
        result = await vlr_events(upcoming=True, completed=True, page=page)

    return _wrap_v2(result)


@router.get("/health")
async def v2_health():
    """Check health of VLR.GG and the API."""
    result = await check_health()
    return {"status": "success", "data": result}
