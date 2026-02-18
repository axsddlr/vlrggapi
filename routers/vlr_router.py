"""
Original unversioned API router — preserved for backwards compatibility.
"""
from fastapi import APIRouter, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from routers.shared_handlers import (
    get_event_matches_data,
    get_events_data,
    get_health_data,
    get_match_data,
    get_match_detail_data,
    get_news_data,
    get_player_data,
    get_player_matches_data,
    get_rankings_data,
    get_stats_data,
    get_team_data,
    get_team_matches_data,
    get_team_transactions_data,
    to_legacy_rankings_shape,
)
from utils.constants import RATE_LIMIT, MAX_MATCH_QUERY_BOUND
from utils.error_handling import validate_match_workload

router = APIRouter(tags=["Default"])
limiter = Limiter(key_func=get_remote_address)


@router.get("/news")
@limiter.limit(RATE_LIMIT)
async def VLR_news(request: Request):
    return await get_news_data()


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
    return await get_stats_data(region, timespan)


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
    return to_legacy_rankings_shape(await get_rankings_data(region))


@router.get("/match")
@limiter.limit(RATE_LIMIT)
async def VLR_match(
    request: Request,
    q: str,
    num_pages: int = Query(1, description="Number of pages to scrape (default: 1)", ge=1, le=MAX_MATCH_QUERY_BOUND),
    from_page: int = Query(None, description="Starting page number (1-based, optional)", ge=1, le=MAX_MATCH_QUERY_BOUND),
    to_page: int = Query(None, description="Ending page number (1-based, inclusive, optional)", ge=1, le=MAX_MATCH_QUERY_BOUND),
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
    if q not in {"upcoming", "upcoming_extended", "live_score", "results"}:
        return {"error": "Invalid query parameter"}

    if q in {"upcoming_extended", "results"}:
        validate_match_workload(num_pages, from_page, to_page, max_retries, timeout)

    return await get_match_data(
        q, num_pages, from_page, to_page, max_retries, request_delay, timeout
    )


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
    return await get_events_data(q, page)


@router.get("/match/details")
@limiter.limit(RATE_LIMIT)
async def VLR_match_detail(
    request: Request,
    match_id: str = Query(..., description="VLR.GG match ID"),
):
    """Get detailed match data including per-map stats, rounds, and head-to-head."""
    return await get_match_detail_data(match_id)


@router.get("/player")
@limiter.limit(RATE_LIMIT)
async def VLR_player(
    request: Request,
    id: str = Query(..., description="VLR.GG player ID"),
    timespan: str = Query("90d", description="Stats timespan: 30d, 60d, 90d, or all"),
):
    """Get player profile with agent stats, event placements, and team history."""
    return await get_player_data(id, timespan)


@router.get("/player/matches")
@limiter.limit(RATE_LIMIT)
async def VLR_player_matches(
    request: Request,
    id: str = Query(..., description="VLR.GG player ID"),
    page: int = Query(1, description="Page number", ge=1, le=100),
):
    """Get paginated match history for a player."""
    return await get_player_matches_data(id, page)


@router.get("/team")
@limiter.limit(RATE_LIMIT)
async def VLR_team(
    request: Request,
    id: str = Query(..., description="VLR.GG team ID"),
):
    """Get team profile with roster, rating, and event placements."""
    return await get_team_data(id)


@router.get("/team/matches")
@limiter.limit(RATE_LIMIT)
async def VLR_team_matches(
    request: Request,
    id: str = Query(..., description="VLR.GG team ID"),
    page: int = Query(1, description="Page number", ge=1, le=100),
):
    """Get paginated match history for a team."""
    return await get_team_matches_data(id, page)


@router.get("/team/transactions")
@limiter.limit(RATE_LIMIT)
async def VLR_team_transactions(
    request: Request,
    id: str = Query(..., description="VLR.GG team ID"),
):
    """Get roster transaction history for a team."""
    return await get_team_transactions_data(id)


@router.get("/events/matches")
@limiter.limit(RATE_LIMIT)
async def VLR_event_matches(
    request: Request,
    event_id: str = Query(..., description="VLR.GG event ID"),
):
    """Get match list for a specific event."""
    return await get_event_matches_data(event_id)


@router.get("/health")
async def health():
    return await get_health_data()
