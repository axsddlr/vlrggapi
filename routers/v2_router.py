"""
V2 API router — standardized responses, validation, Pydantic models.
"""
from fastapi import APIRouter, HTTPException, Query

from models import V2Response
from routers.shared_handlers import (
    get_event_detail_data,
    get_event_matches_data,
    get_events_data,
    get_health_data,
    get_match_data,
    get_match_detail_data,
    get_news_data,
    get_player_data,
    get_player_matches_data,
    get_rankings_data,
    get_search_data,
    get_stats_data,
    get_team_data,
    get_team_matches_data,
    get_team_stats_data,
    get_team_transactions_data,
)
from utils.constants import MAX_MATCH_QUERY_BOUND
from utils.error_handling import (
    validate_event_query,
    validate_id_param,
    validate_match_query,
    validate_match_workload,
    validate_player_query,
    validate_player_timespan,
    validate_team_query,
)

router = APIRouter(prefix="/v2", tags=["v2"])


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


@router.get("/news", response_model=V2Response, summary="Latest news", description="Get the latest Valorant esports news headlines from VLR.GG.")
async def v2_news():
    result = await get_news_data()
    return _wrap_v2(result)


@router.get("/stats", response_model=V2Response, summary="Player stats", description="Get player statistics for a region and timespan.")
async def v2_stats(
    region: str = Query(..., description="Region shortname (na, eu, ap, la, la-s, la-n, oce, kr, mn, gc, br, cn, jp, col)"),
    timespan: str = Query(..., description="Timespan: 30, 60, 90, or all"),
):
    result = await get_stats_data(region, timespan)
    return _wrap_v2(result)


@router.get("/rankings", response_model=V2Response, summary="Team rankings", description="Get team rankings for a region.")
async def v2_rankings(
    region: str = Query(..., description="Region shortname (na, eu, ap, la, la-s, la-n, oce, kr, mn, gc, br, cn, jp, col)"),
):
    result = await get_rankings_data(region)
    return _wrap_v2(result)


@router.get("/match", response_model=V2Response, summary="Matches by type", description="Get upcoming, live, or completed match data. Supports pagination for results and upcoming_extended.")
async def v2_match(
    q: str = Query(..., description="Match type: upcoming, upcoming_extended, live_score, results"),
    num_pages: int = Query(1, description="Number of pages to scrape", ge=1, le=MAX_MATCH_QUERY_BOUND),
    from_page: int = Query(None, description="Starting page number (1-based)", ge=1, le=MAX_MATCH_QUERY_BOUND),
    to_page: int = Query(None, description="Ending page number (1-based, inclusive)", ge=1, le=MAX_MATCH_QUERY_BOUND),
    max_retries: int = Query(3, description="Max retry attempts per page", ge=1, le=5),
    request_delay: float = Query(1.0, description="Delay between requests (seconds)", ge=0.5, le=5.0),
    timeout: int = Query(30, description="Request timeout (seconds)", ge=10, le=120),
):
    validate_match_query(q)

    if q in {"upcoming_extended", "results"}:
        validate_match_workload(num_pages, from_page, to_page, max_retries, timeout)

    result = await get_match_data(
        q, num_pages, from_page, to_page, max_retries, request_delay, timeout
    )

    return _wrap_v2(result)


@router.get("/events", response_model=V2Response, summary="Browse events", description="Browse Valorant events — names, dates, status, and prize pools. Use q=upcoming, completed, or live to filter.")
async def v2_events(
    q: str = Query(None, description="Event type: upcoming, completed, or live"),
    page: int = Query(1, description="Page number (completed events only)", ge=1, le=100),
):
    validate_event_query(q)

    result = await get_events_data(q, page)

    return _wrap_v2(result)


@router.get("/match/details", response_model=V2Response, summary="Match detail", description="Get full match detail including per-map stats, round data, head-to-head history, performance tab, and economy data.")
async def v2_match_detail(
    match_id: str = Query(..., description="VLR.GG match ID"),
):
    validate_id_param(match_id, "match_id")
    result = await get_match_detail_data(match_id)
    return _wrap_v2(result)


@router.get("/player", response_model=V2Response, summary="Player data", description="Get player profile or match history via q parameter.")
async def v2_player(
    id: str = Query(..., description="VLR.GG player ID"),
    q: str = Query("profile", description="Data type: profile, matches"),
    timespan: str = Query("90d", description="Stats timespan for profile (30d, 60d, 90d, all)"),
    page: int = Query(1, description="Page number for matches (1-based)", ge=1, le=100),
):
    validate_id_param(id)
    validate_player_query(q)

    if q == "matches":
        result = await get_player_matches_data(id, page)
    else:
        validate_player_timespan(timespan)
        result = await get_player_data(id, timespan)

    return _wrap_v2(result)


@router.get("/team", response_model=V2Response, summary="Team data", description="Get team profile, match history, roster transactions, or map stats via q parameter.")
async def v2_team(
    id: str = Query(..., description="VLR.GG team ID"),
    q: str = Query("profile", description="Data type: profile, matches, transactions, stats"),
    page: int = Query(1, description="Page number for matches (1-based)", ge=1, le=100),
):
    validate_id_param(id)
    validate_team_query(q)

    if q == "matches":
        result = await get_team_matches_data(id, page)
    elif q == "transactions":
        result = await get_team_transactions_data(id)
    elif q == "stats":
        result = await get_team_stats_data(id)
    else:
        result = await get_team_data(id)

    return _wrap_v2(result)


@router.get("/events/matches", response_model=V2Response, summary="Event matches", description="List all matches for an event — scores, teams, dates. Use event IDs from GET /v2/events.")
async def v2_event_matches(
    event_id: str = Query(..., description="VLR.GG event ID"),
):
    validate_id_param(event_id, "event_id")
    result = await get_event_matches_data(event_id)
    return _wrap_v2(result)


@router.get("/event/{event_id}", response_model=V2Response, summary="Event detail", description="Get full event detail — prizes, teams, standings, dates, and prize pool.")
async def v2_event_detail(
    event_id: str,
):
    validate_id_param(event_id, "event_id")
    result = await get_event_detail_data(event_id)
    return _wrap_v2(result)


@router.get("/search", response_model=V2Response, summary="Search", description="Search VLR.GG for teams, players, events, and series. Returns categorized results.")
async def v2_search(
    q: str = Query(..., description="Search query (player name, team name, event keyword)"),
):
    result = await get_search_data(q)
    return _wrap_v2(result)


@router.get("/health", response_model=V2Response, summary="Health check", description="Check API health and upstream VLR.GG reachability.")
async def v2_health():
    result = await get_health_data()
    return {"status": "success", "data": result}
