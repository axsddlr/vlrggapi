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
    get_match_logs_data,
    get_news_data,
    get_player_data,
    get_player_matches_data,
    get_rankings_data,
    get_search_data,
    get_stats_data,
    get_team_data,
    get_team_matches_data,
    get_team_roster_data,
    get_team_schedule_data,
    get_team_stats_data,
    get_team_transactions_data,
)
from utils.constants import MAX_MATCH_QUERY_BOUND
from utils.error_handling import (
    validate_date_param,
    validate_event_query,
    validate_id_param,
    validate_match_query,
    validate_match_workload,
    validate_player_query,
    validate_player_timespan,
    validate_slug_param,
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


def _validate_page(page: int) -> None:
    """Bound a page number at 1-100, raising 400 like the other V2 validators."""
    if page < 1 or page > 100:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid page '{page}'. Must be between 1 and 100.",
        )


@router.get("/news", response_model=V2Response, summary="Latest news", description="Get the latest Valorant esports news headlines from VLR.GG.")
async def v2_news():
    result = await get_news_data()
    return _wrap_v2(result)


@router.get("/stats", response_model=V2Response, summary="Player stats", description="Get player statistics for a region, timespan, and optional event.")
async def v2_stats(
    region: str = Query(..., description="Region: all, americas, emea, pacific, china, intl (deprecated aliases: na/br -> americas, eu -> emea, ap/kr/jp/oce -> pacific, cn -> china)"),
    timespan: str = Query(..., description="Timespan: 30, 60, 90, or all"),
    event_id: str = Query(None, description="Optional numeric event ID to filter stats by event"),
    map_name: str = Query(
        "all",
        alias="map",
        description="Map filter: all, or a map name (ascent, bind, breeze, corrode, fracture, haven, "
        "icebox, lotus, pearl, split, summit, sunset, abyss)",
    ),
    min_rounds: int = Query(
        200, ge=0, description="Minimum rounds played; lower it for event-scoped views"
    ),
    min_rating: float = Query(1.55, ge=0.0, description="Minimum rating on vlr.gg's 0-2 scale"),
):
    if event_id is not None and not event_id.isdigit():
        raise HTTPException(status_code=400, detail="event_id must be a numeric ID")
    result = await get_stats_data(region, timespan, event_id, map_name, min_rounds, min_rating)
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
    light: bool = Query(
        False,
        description="Skip the per-game performance/economy tab fetches (upcoming matches have none)",
    ),
):
    validate_id_param(match_id, "match_id")
    result = await get_match_detail_data(match_id, light=light)
    return _wrap_v2(result)


@router.get("/match/logs", response_model=V2Response, summary="Match 2D replay", description="Per-round replay of one map: round result, each player's buy, and every kill, spike plant and defuse with player positions and health. Omit game_id to use the match's first played map. Takes the `tab=logs` page on vlr.gg.")
async def v2_match_logs(
    match_id: str = Query(..., description="VLR.GG match ID"),
    game_id: str = Query(None, description="Optional game (map) ID; defaults to the first played map"),
):
    validate_id_param(match_id, "match_id")
    if game_id is not None:
        validate_id_param(game_id, "game_id")
    result = await get_match_logs_data(match_id, game_id)
    return _wrap_v2(result)


@router.get("/match/{match_id}/details", response_model=V2Response, summary="Match detail by ID", description="Get full match detail including per-map stats, round data, head-to-head history, performance tab, and economy data. Same data as GET /v2/match/details?match_id=..., which loads vlr.gg's /match/<id> page.")
async def v2_match_detail_path(
    match_id: str,
    light: bool = Query(
        False,
        description="Skip the per-game performance/economy tab fetches (upcoming matches have none)",
    ),
):
    validate_id_param(match_id, "match_id")
    result = await get_match_detail_data(match_id, light=light)
    return _wrap_v2(result)


@router.get("/match/{match_id}/logs", response_model=V2Response, summary="Match 2D replay by ID", description="Per-round replay of one map: round result, each player's buy, and every kill, spike plant and defuse with player positions and health. Same data as GET /v2/match/logs?match_id=...; takes the `tab=logs` page on vlr.gg. Omit game_id to use the match's first played map.")
async def v2_match_logs_path(
    match_id: str,
    game_id: str | None = Query(None, description="Optional game (map) ID; defaults to the first played map"),
):
    validate_id_param(match_id, "match_id")
    if game_id is not None:
        validate_id_param(game_id, "game_id")
    result = await get_match_logs_data(match_id, game_id)
    return _wrap_v2(result)


@router.get("/player", response_model=V2Response, summary="Player data", description="Get player profile or match history via q parameter.")
async def v2_player(
    id: str = Query(..., description="VLR.GG player ID"),
    q: str = Query("profile", description="Data type: profile, matches (deprecated: use the path-based routes below)", deprecated=True),
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


@router.get("/player/{player_id}", response_model=V2Response, summary="Player profile by ID", description="Get a player's profile and stats. Same data as GET /v2/player?id=...&q=profile, which loads vlr.gg's /player/<id> page.")
async def v2_player_profile(
    player_id: str,
    timespan: str = Query("90d", description="Stats timespan (30d, 60d, 90d, all)"),
):
    validate_id_param(player_id, "player_id")
    validate_player_timespan(timespan)
    result = await get_player_data(player_id, timespan)
    return _wrap_v2(result)


@router.get("/player/{player_id}/matches", response_model=V2Response, summary="Player match history by ID", description="Get a player's completed matches, newest first. Same data as GET /v2/player?id=...&q=matches, which loads the match-history tab on vlr.gg's /player/<id> page.")
async def v2_player_matches(
    player_id: str,
    page: int = Query(1, description="Page number (1-based), 1-100"),
):
    validate_id_param(player_id, "player_id")
    _validate_page(page)
    result = await get_player_matches_data(player_id, page)
    return _wrap_v2(result)


@router.get("/team", response_model=V2Response, summary="Team data", description="Get team profile, match history, roster transactions, map stats, grouped roster, or upcoming schedule via q parameter.")
async def v2_team(
    id: str = Query(..., description="VLR.GG team ID"),
    q: str = Query("profile", description="Data type: profile, matches, transactions, stats, roster, schedule (deprecated: use the path-based routes below)", deprecated=True),
    page: int = Query(1, description="Page number for matches (1-based)", ge=1, le=100),
    date_start: str = Query(
        "",
        description="Start date (YYYY-MM-DD) for q=stats: only matches from that day on",
    ),
):
    validate_id_param(id)
    validate_team_query(q)
    if date_start:
        validate_date_param(date_start)

    if q == "matches":
        result = await get_team_matches_data(id, page)
    elif q == "transactions":
        result = await get_team_transactions_data(id)
    elif q == "stats":
        result = await get_team_stats_data(id, date_start)
    elif q == "roster":
        result = await get_team_roster_data(id)
    elif q == "schedule":
        result = await get_team_schedule_data(id)
    else:
        result = await get_team_data(id)

    return _wrap_v2(result)


@router.get("/team/{team_id}", response_model=V2Response, summary="Team profile by ID", description="Get a team's profile: name, logo, country, socials, and current roster. Same data as GET /v2/team?id=...&q=profile, which loads vlr.gg's /team/<id> page.")
async def v2_team_profile(team_id: str):
    validate_id_param(team_id, "team_id")
    result = await get_team_data(team_id)
    return _wrap_v2(result)


@router.get("/team/{team_id}/matches", response_model=V2Response, summary="Team match history by ID", description="Get a team's completed matches, newest first. Same data as GET /v2/team?id=...&q=matches, which loads vlr.gg's /team/matches/<id> page.")
async def v2_team_matches(
    team_id: str,
    page: int = Query(1, description="Page number (1-based), 1-100"),
):
    validate_id_param(team_id, "team_id")
    _validate_page(page)
    result = await get_team_matches_data(team_id, page)
    return _wrap_v2(result)


@router.get("/team/{team_id}/transactions", response_model=V2Response, summary="Team transactions by ID", description="Get a team's roster transaction history — joins, leaves, and bench moves. Same data as GET /v2/team?id=...&q=transactions, which loads vlr.gg's /team/transactions/<id> page.")
async def v2_team_transactions(team_id: str):
    validate_id_param(team_id, "team_id")
    result = await get_team_transactions_data(team_id)
    return _wrap_v2(result)


@router.get("/team/{team_id}/stats", response_model=V2Response, summary="Team map stats by ID", description="Get a team's per-map win/loss and round stats, optionally from a start date on. Same data as GET /v2/team?id=...&q=stats, which loads vlr.gg's /team/stats/<id> page.")
async def v2_team_stats(
    team_id: str,
    date_start: str = Query(
        "",
        description="Start date (YYYY-MM-DD): only matches from that day on",
    ),
):
    validate_id_param(team_id, "team_id")
    if date_start:
        validate_date_param(date_start)
    result = await get_team_stats_data(team_id, date_start)
    return _wrap_v2(result)


@router.get("/team/{team_id}/roster", response_model=V2Response, summary="Team roster by ID", description="Get a team's roster grouped by period, including stand-ins and coaches. Same data as GET /v2/team?id=...&q=roster, which loads vlr.gg's /team/roster/<id> page.")
async def v2_team_roster(team_id: str):
    validate_id_param(team_id, "team_id")
    result = await get_team_roster_data(team_id)
    return _wrap_v2(result)


@router.get("/team/{team_id}/schedule", response_model=V2Response, summary="Team schedule by ID", description="Get a team's upcoming matches. Same data as GET /v2/team?id=...&q=schedule, which loads the upcoming section of vlr.gg's /team/matches/<id> page.")
async def v2_team_schedule(team_id: str):
    validate_id_param(team_id, "team_id")
    result = await get_team_schedule_data(team_id)
    return _wrap_v2(result)


@router.get("/events/matches", response_model=V2Response, summary="Event matches", description="List all matches for an event — scores, teams, dates. Use event IDs from GET /v2/events.")
async def v2_event_matches(
    event_id: str = Query(..., description="VLR.GG event ID"),
):
    validate_id_param(event_id, "event_id")
    result = await get_event_matches_data(event_id)
    return _wrap_v2(result)


@router.get("/event/{event_id}", response_model=V2Response, summary="Event detail", description="Get full event detail — stages, prizes, teams, standings, dates, and prize pool. Prizes and standings are those of one stage: the default (usually current) one, or the one named by stage.")
async def v2_event_detail(
    event_id: str,
    stage: str = Query(None, description="Optional stage slug from the response's stages list (e.g. playoffs)"),
):
    validate_id_param(event_id, "event_id")
    if stage is not None:
        validate_slug_param(stage, "stage")
    result = await get_event_detail_data(event_id, stage)
    return _wrap_v2(result)


@router.get("/search", response_model=V2Response, summary="Search", description="Search VLR.GG for teams, players, events, and series. Returns categorized results.")
async def v2_search(
    q: str = Query(..., description="Search query (player name, team name, event keyword)"),
):
    result = await get_search_data(q)
    return _wrap_v2(result)


@router.get("/health", response_model=V2Response, summary="Health check", description="Report local service readiness (in-process checks only; no upstream call).")
async def v2_health():
    result = await get_health_data()
    return {"status": "success", "data": result}
