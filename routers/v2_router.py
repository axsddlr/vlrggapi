"""
V2 API router — standardized responses, validation, Pydantic models.
"""
from fastapi import APIRouter, HTTPException, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from models import V2Response
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
)
from utils.constants import RATE_LIMIT, MAX_MATCH_QUERY_BOUND
from utils.error_handling import (
    validate_event_query,
    validate_match_query,
    validate_match_workload,
    validate_player_timespan,
    validate_id_param,
)

router = APIRouter(prefix="/v2", tags=["v2"])
limiter = Limiter(key_func=get_remote_address)


def _wrap_v2(scraper_result: dict) -> dict:
    """Wrap scraper result into the standardized V2 response shape."""
    if "data" in scraper_result:
        inner = scraper_result["data"]
        status_code = inner.get("status") if isinstance(inner, dict) else None
        if isinstance(status_code, int) and status_code >= 400:
            detail = inner.get("error", "Upstream request failed")
            raise HTTPException(status_code=status_code, detail=detail)
        return {
            "status": "success",
            "data": inner,
        }
    return {"status": "success", "data": scraper_result}


@router.get("/news", response_model=V2Response)
@limiter.limit(RATE_LIMIT)
async def v2_news(request: Request):
    """Get the latest Valorant esports news from VLR.GG."""
    result = await get_news_data()
    return _wrap_v2(result)


@router.get("/stats", response_model=V2Response)
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
    result = await get_stats_data(region, timespan)
    return _wrap_v2(result)


@router.get("/rankings", response_model=V2Response)
@limiter.limit(RATE_LIMIT)
async def v2_rankings(
    request: Request,
    region: str = Query(..., description="Region shortname (na, eu, ap, la, etc.)"),
):
    """
    Get team rankings for a region.

    Region shortnames: na, eu, ap, la, la-s, la-n, oce, kr, mn, gc, br, cn, jp, col
    """
    result = await get_rankings_data(region)
    return _wrap_v2(result)


@router.get("/match", response_model=V2Response)
@limiter.limit(RATE_LIMIT)
async def v2_match(
    request: Request,
    q: str = Query(..., description="Match type: upcoming, upcoming_extended, live_score, results"),
    num_pages: int = Query(1, description="Number of pages to scrape", ge=1, le=MAX_MATCH_QUERY_BOUND),
    from_page: int = Query(None, description="Starting page number (1-based)", ge=1, le=MAX_MATCH_QUERY_BOUND),
    to_page: int = Query(None, description="Ending page number (1-based, inclusive)", ge=1, le=MAX_MATCH_QUERY_BOUND),
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

    if q in {"upcoming_extended", "results"}:
        validate_match_workload(num_pages, from_page, to_page, max_retries, timeout)

    result = await get_match_data(
        q, num_pages, from_page, to_page, max_retries, request_delay, timeout
    )

    return _wrap_v2(result)


@router.get("/events", response_model=V2Response)
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

    result = await get_events_data(q, page)

    return _wrap_v2(result)


@router.get("/match/details", response_model=V2Response)
@limiter.limit(RATE_LIMIT)
async def v2_match_detail(
    request: Request,
    match_id: str = Query(..., description="VLR.GG match ID"),
):
    """
    Get detailed match data.

    Includes per-map stats (player K/D/A, ACS, rating), round-by-round data,
    head-to-head history, performance tab (kill matrix, advanced stats),
    and economy tab data.
    """
    validate_id_param(match_id, "match_id")
    result = await get_match_detail_data(match_id)
    return _wrap_v2(result)


@router.get("/player", response_model=V2Response)
@limiter.limit(RATE_LIMIT)
async def v2_player(
    request: Request,
    id: str = Query(..., description="VLR.GG player ID"),
    timespan: str = Query("90d", description="Stats timespan: 30d, 60d, 90d, or all"),
):
    """
    Get player profile.

    Includes agent stats, current/past teams, event placements, news, and total winnings.
    """
    validate_id_param(id)
    validate_player_timespan(timespan)
    result = await get_player_data(id, timespan)
    return _wrap_v2(result)


@router.get("/player/matches", response_model=V2Response)
@limiter.limit(RATE_LIMIT)
async def v2_player_matches(
    request: Request,
    id: str = Query(..., description="VLR.GG player ID"),
    page: int = Query(1, description="Page number (1-based)", ge=1, le=100),
):
    """Get paginated match history for a player."""
    validate_id_param(id)
    result = await get_player_matches_data(id, page)
    return _wrap_v2(result)


@router.get("/team", response_model=V2Response)
@limiter.limit(RATE_LIMIT)
async def v2_team(
    request: Request,
    id: str = Query(..., description="VLR.GG team ID"),
):
    """
    Get team profile.

    Includes roster, rating/ranking info, event placements, and total winnings.
    """
    validate_id_param(id)
    result = await get_team_data(id)
    return _wrap_v2(result)


@router.get("/team/matches", response_model=V2Response)
@limiter.limit(RATE_LIMIT)
async def v2_team_matches(
    request: Request,
    id: str = Query(..., description="VLR.GG team ID"),
    page: int = Query(1, description="Page number (1-based)", ge=1, le=100),
):
    """Get paginated match history for a team."""
    validate_id_param(id)
    result = await get_team_matches_data(id, page)
    return _wrap_v2(result)


@router.get("/team/transactions", response_model=V2Response)
@limiter.limit(RATE_LIMIT)
async def v2_team_transactions(
    request: Request,
    id: str = Query(..., description="VLR.GG team ID"),
):
    """Get roster transaction history for a team (joins, leaves, benchings)."""
    validate_id_param(id)
    result = await get_team_transactions_data(id)
    return _wrap_v2(result)


@router.get("/events/matches", response_model=V2Response)
@limiter.limit(RATE_LIMIT)
async def v2_event_matches(
    request: Request,
    event_id: str = Query(..., description="VLR.GG event ID"),
):
    """Get match list for a specific event with scores and VOD links."""
    validate_id_param(event_id, "event_id")
    result = await get_event_matches_data(event_id)
    return _wrap_v2(result)


@router.get("/health", response_model=V2Response)
async def v2_health():
    """Check API health and runtime readiness."""
    result = await get_health_data()
    return {"status": "success", "data": result}
