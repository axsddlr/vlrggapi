from fastapi import APIRouter, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from api.scrape import Vlr

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
vlr = Vlr()


@router.get("/news")
@limiter.limit("600/minute")
async def VLR_news(request: Request):
    return vlr.vlr_news()


@router.get("/stats")
@limiter.limit("600/minute")
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
    return vlr.vlr_stats(region, timespan)


@router.get("/rankings")
@limiter.limit("600/minute")
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
    return vlr.vlr_rankings(region)


@router.get("/match")
@limiter.limit("600/minute")
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
        "upcoming": upcoming matches,\n
        "live_score": live match scores,\n
        "results": match results,\n
    
    Page Range Options:
    - num_pages: Number of pages from page 1 (ignored if from_page/to_page specified)
    - from_page: Starting page number (1-based, optional)
    - to_page: Ending page number (1-based, inclusive, optional)
    
    Additional parameters for robust scraping:
    - max_retries: Maximum retry attempts per failed page (1-5, default: 3)
    - request_delay: Delay between requests in seconds (0.5-5.0, default: 1.0)
    - timeout: Request timeout in seconds (10-120, default: 30)
    
    Examples:
    - /match?q=results&num_pages=5 (scrapes pages 1-5)
    - /match?q=results&from_page=10&to_page=15 (scrapes pages 10-15)
    - /match?q=results&from_page=5&num_pages=3 (scrapes pages 5-7)
    """
    if q == "upcoming":
        return vlr.vlr_upcoming_matches(num_pages, from_page, to_page)
    elif q == "live_score":
        return vlr.vlr_live_score(num_pages, from_page, to_page)
    elif q == "results":
        return vlr.vlr_match_results(num_pages, from_page, to_page, max_retries, request_delay, timeout)

    else:
        return {"error": "Invalid query parameter"}


@router.get("/events")
@limiter.limit("600/minute")
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
    
    ## Event Types:
    - **upcoming**: Currently active or scheduled future events
    - **completed**: Historical events that have finished
    - **default**: Both upcoming and completed events (when q parameter is omitted)
    
    ## Pagination:
    - Only applies to **completed events**
    - Upcoming events are always from the first page
    - Page numbers range from 1 to 100
    - Each page contains approximately 25-30 events
    
    ## Usage Examples:
    - `GET /events` - All events (upcoming + completed page 1)
    - `GET /events?q=upcoming` - Only upcoming events
    - `GET /events?q=completed` - Only completed events (page 1)
    - `GET /events?q=completed&page=3` - Completed events from page 3
    - `GET /events?page=2` - All events (upcoming + completed page 2)
    
    ## Response Format:
    Returns event details including title, status, prize pool, dates, region, thumbnail, and event URL.
    """
    if q == "upcoming":
        return vlr.vlr_events(upcoming=True, completed=False, page=page)
    elif q == "completed":
        return vlr.vlr_events(upcoming=False, completed=True, page=page)
    else:
        return vlr.vlr_events(upcoming=True, completed=True, page=page)


@router.get("/health")
def health():
    return vlr.check_health()
