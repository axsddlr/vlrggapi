import logging

from selectolax.parser import HTMLParser

from utils.http_client import fetch_with_retries, get_http_client
from utils.constants import VLR_STATS_URL, CACHE_TTL_STATS
from utils.cache_manager import cache_manager
from utils.error_handling import handle_scraper_errors, validate_region, validate_timespan

logger = logging.getLogger(__name__)


def _safe_text(node) -> str:
    """Safely extract stripped text from an HTML node."""
    if not node:
        return ""
    return node.text().strip()


def _cell_text(cells: list, index: int) -> str:
    """Read a table cell by index without raising on sparse rows."""
    if index >= len(cells):
        return ""
    return _safe_text(cells[index])


def _parse_stats_row(item) -> dict:
    """Parse one stats table row using table-cell structure, not flattened text."""
    cells = item.css("td")
    player_cell = item.css_first("td.mod-player")

    player_name = _safe_text(player_cell.css_first(".text-of")) if player_cell else ""
    org = _safe_text(player_cell.css_first(".stats-player-country")) if player_cell else ""
    if not org:
        org = "N/A"

    agents = []
    for agent_img in item.css("td.mod-agents img"):
        src = agent_img.attributes.get("src", "")
        if not src:
            continue
        agents.append(src.split("/")[-1].split(".")[0])

    return {
        "player": player_name,
        "org": org,
        "agents": agents,
        "rounds_played": _cell_text(cells, 2),
        "rating": _cell_text(cells, 3),
        "average_combat_score": _cell_text(cells, 4),
        "kill_deaths": _cell_text(cells, 5),
        "kill_assists_survived_traded": _cell_text(cells, 6),
        "average_damage_per_round": _cell_text(cells, 7),
        "kills_per_round": _cell_text(cells, 8),
        "assists_per_round": _cell_text(cells, 9),
        "first_kills_per_round": _cell_text(cells, 10),
        "first_deaths_per_round": _cell_text(cells, 11),
        "headshot_percentage": _cell_text(cells, 12),
        "clutch_success_percentage": _cell_text(cells, 13),
    }


@handle_scraper_errors
async def vlr_stats(region_key: str, timespan: str):
    async def build():
        validate_region(region_key)
        validate_timespan(timespan)

        base_url = (
            f"{VLR_STATS_URL}/?event_group_id=all&event_id=all"
            f"&region={region_key}&country=all&min_rounds=200"
            f"&min_rating=1550&agent=all&map_id=all"
        )
        url = (
            f"{base_url}&timespan=all"
            if timespan.lower() == "all"
            else f"{base_url}&timespan={timespan}d"
        )

        client = get_http_client()
        resp = await fetch_with_retries(url, client=client)
        html = HTMLParser(resp.text)
        status = resp.status_code

        result = []
        for item in html.css("tbody tr"):
            parsed = _parse_stats_row(item)
            if parsed["player"]:
                result.append(parsed)

        data = {"data": {"status": status, "segments": result}}

        if status != 200:
            raise Exception("API response: {}".format(status))

        return data

    return await cache_manager.get_or_create_async(
        CACHE_TTL_STATS, build, "stats", region_key, timespan
    )
