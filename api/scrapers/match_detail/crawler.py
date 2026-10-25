"""
Main match detail scraper orchestrator.

Fetches the base match page, extracts game IDs, and concurrently
fetches performance and economy tabs for enriched per-map data.
"""
import asyncio
import logging

from utils.cache_manager import cache_manager
from utils.constants import (
    CACHE_TTL_MATCH_DETAIL,
    CACHE_TTL_MATCH_DETAIL_LIVE,
    MATCH_DETAIL_TAB_FETCH_CONCURRENCY,
    MATCH_DETAIL_TAB_FETCH_TIMEOUT,
    VLR_BASE_URL,
)
from utils.error_handling import handle_scraper_errors, upstream_error_payload
from utils.html_parsers import HTMLParser, parse_html
from utils.http_client import fetch_with_retries, get_http_client

from .parsers import (
    _is_live,
    _parse_advanced_stats,
    _parse_economy,
    _parse_event_info,
    _parse_head_to_head,
    _parse_kill_matrix,
    _parse_maps,
    _parse_match_header,
    _parse_streams_vods,
    _parse_teams,
)

logger = logging.getLogger(__name__)


def _extract_game_ids(html: HTMLParser) -> list[str]:
    """Return all data-game-id values from the stats nav, excluding 'all'."""
    game_ids: list[str] = []
    for item in html.css(".vm-stats-gamesnav-item"):
        gid = item.attributes.get("data-game-id", "")
        if gid and gid != "all":
            game_ids.append(gid)
    return game_ids


async def _fetch_game_tab_html(
    client,
    base_url: str,
    game_id: str,
    tab: str,
    timeout: int = MATCH_DETAIL_TAB_FETCH_TIMEOUT,
) -> tuple[str, str, "HTMLParser | None"]:
    """Fetch one game-tab page and return parsed HTML when available."""
    url = f"{base_url}/?game={game_id}&tab={tab}"
    try:
        resp = await fetch_with_retries(url, client=client, timeout=timeout)
        if resp.status_code >= 400:
            logger.warning(
                "Failed to fetch %s tab for game %s: upstream status %d",
                tab, game_id, resp.status_code,
            )
            return game_id, tab, None
        return game_id, tab, parse_html(resp.text)
    except Exception as exc:
        logger.warning("Failed to fetch %s tab for game %s: %s", tab, game_id, exc)
        return game_id, tab, None


@handle_scraper_errors
async def vlr_match_detail(match_id: str) -> dict:
    """
    Scrape a single VLR.GG match page and return structured match data.

    Fetches the base page, then concurrently fetches the performance and
    economy tabs for every game. Cache TTL is 30 s for live matches and
    300 s for completed matches.
    """
    base_url = f"{VLR_BASE_URL}/{match_id}"

    cached = cache_manager.get(CACHE_TTL_MATCH_DETAIL_LIVE, "match_detail", match_id)
    if cached is not None:
        return cached
    cached = cache_manager.get(CACHE_TTL_MATCH_DETAIL, "match_detail", match_id)
    if cached is not None:
        return cached

    async def build():
        cached_live = cache_manager.get(
            CACHE_TTL_MATCH_DETAIL_LIVE, "match_detail", match_id
        )
        if cached_live is not None:
            return cached_live

        cached_complete = cache_manager.get(
            CACHE_TTL_MATCH_DETAIL, "match_detail", match_id
        )
        if cached_complete is not None:
            return cached_complete

        client = get_http_client()

        base_resp = await fetch_with_retries(base_url, client=client)
        http_status = base_resp.status_code
        if http_status >= 400:
            return upstream_error_payload(http_status, f"match detail {match_id}")

        base_html = parse_html(base_resp.text)

        game_ids = _extract_game_ids(base_html)
        first_game_id = game_ids[0] if game_ids else None

        performance_by_game: dict[str, dict] = {}
        economy_by_game: dict[str, list[dict]] = {}

        if game_ids:
            tab_fetch_semaphore = asyncio.Semaphore(MATCH_DETAIL_TAB_FETCH_CONCURRENCY)

            async def fetch_tab(game_id: str, tab: str):
                async with tab_fetch_semaphore:
                    return await _fetch_game_tab_html(
                        client,
                        base_url,
                        game_id,
                        tab,
                        timeout=MATCH_DETAIL_TAB_FETCH_TIMEOUT,
                    )

            tab_results = await asyncio.gather(
                *[
                    fetch_tab(game_id, tab)
                    for game_id in game_ids
                    for tab in ("performance", "economy")
                ]
            )

            for game_id, tab, tab_html in tab_results:
                if tab_html is None:
                    continue
                if tab == "performance":
                    performance_by_game[game_id] = {
                        "kill_matrix": _parse_kill_matrix(tab_html),
                        "advanced_stats": _parse_advanced_stats(tab_html),
                    }
                elif tab == "economy":
                    economy_by_game[game_id] = _parse_economy(tab_html)

        event_info = _parse_event_info(base_html)
        header_info = _parse_match_header(base_html)
        teams = _parse_teams(base_html)
        streams, vods = _parse_streams_vods(base_html)
        maps = _parse_maps(base_html)
        h2h = _parse_head_to_head(base_html)

        for index, map_data in enumerate(maps):
            game_id = game_ids[index] if index < len(game_ids) else ""
            map_data["performance"] = performance_by_game.get(
                game_id, {"kill_matrix": [], "advanced_stats": []}
            )
            map_data["economy"] = economy_by_game.get(game_id, [])

        first_game_performance = performance_by_game.get(
            first_game_id or "", {"kill_matrix": [], "advanced_stats": []}
        )
        first_game_economy = economy_by_game.get(first_game_id or "", [])

        segment = {
            "match_id": match_id,
            "event": event_info,
            "date": header_info["date"],
            "map_vetos": header_info["map_vetos"],
            "status": header_info["status"],
            "teams": teams,
            "streams": streams,
            "vods": vods,
            "maps": maps,
            "head_to_head": h2h,
            "performance": {
                "kill_matrix": first_game_performance["kill_matrix"],
                "advanced_stats": first_game_performance["advanced_stats"],
                "by_map": [
                    {"game_id": game_id, **performance_by_game.get(game_id, {"kill_matrix": [], "advanced_stats": []})}
                    for game_id in game_ids
                ],
            },
            "economy": first_game_economy,
            "economy_by_map": [
                {"game_id": game_id, "rows": economy_by_game.get(game_id, [])}
                for game_id in game_ids
            ],
        }

        data = {"data": {"status": http_status, "segments": [segment]}}

        live = _is_live(base_html)
        ttl = CACHE_TTL_MATCH_DETAIL_LIVE if live else CACHE_TTL_MATCH_DETAIL
        cache_manager.set_if_cacheable(ttl, data, "match_detail", match_id)

        return data

    return await cache_manager.coalesce_async(f"match_detail:{match_id}", build)
