"""
Shared endpoint handler logic used by both legacy and V2 routers.
"""
from api.scrapers import (
    check_health,
    vlr_event_matches,
    vlr_events,
    vlr_live_score,
    vlr_match_detail,
    vlr_match_results,
    vlr_news,
    vlr_player,
    vlr_player_matches,
    vlr_rankings,
    vlr_stats,
    vlr_team,
    vlr_team_matches,
    vlr_team_transactions,
    vlr_upcoming_matches,
    vlr_upcoming_matches_extended,
)


async def get_news_data() -> dict:
    return await vlr_news()


async def get_stats_data(region: str, timespan: str) -> dict:
    return await vlr_stats(region, timespan)


async def get_rankings_data(region: str) -> dict:
    return await vlr_rankings(region)


def to_legacy_rankings_shape(data: dict) -> dict:
    """Return the historical rankings response shape used by the legacy route."""
    if "data" in data and "segments" in data["data"]:
        return {
            "status": data["data"]["status"],
            "data": data["data"]["segments"],
        }
    return data


async def get_match_data(
    q: str,
    num_pages: int,
    from_page: int | None,
    to_page: int | None,
    max_retries: int,
    request_delay: float,
    timeout: int,
) -> dict:
    if q == "upcoming":
        return await vlr_upcoming_matches(num_pages, from_page, to_page)
    if q == "upcoming_extended":
        return await vlr_upcoming_matches_extended(
            num_pages, from_page, to_page, max_retries, request_delay, timeout
        )
    if q == "live_score":
        return await vlr_live_score(num_pages, from_page, to_page)
    if q == "results":
        return await vlr_match_results(
            num_pages, from_page, to_page, max_retries, request_delay, timeout
        )
    raise ValueError("Invalid query parameter")


async def get_events_data(q: str | None, page: int) -> dict:
    if q == "upcoming":
        return await vlr_events(upcoming=True, completed=False, page=page)
    if q == "completed":
        return await vlr_events(upcoming=False, completed=True, page=page)
    return await vlr_events(upcoming=True, completed=True, page=page)


async def get_match_detail_data(match_id: str) -> dict:
    return await vlr_match_detail(match_id)


async def get_player_data(player_id: str, timespan: str) -> dict:
    return await vlr_player(player_id, timespan)


async def get_player_matches_data(player_id: str, page: int) -> dict:
    return await vlr_player_matches(player_id, page)


async def get_team_data(team_id: str) -> dict:
    return await vlr_team(team_id)


async def get_team_matches_data(team_id: str, page: int) -> dict:
    return await vlr_team_matches(team_id, page)


async def get_team_transactions_data(team_id: str) -> dict:
    return await vlr_team_transactions(team_id)


async def get_event_matches_data(event_id: str) -> dict:
    return await vlr_event_matches(event_id)


async def get_health_data() -> dict:
    return await check_health()
