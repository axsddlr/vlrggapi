"""
Scraper for VLR.GG search results.

Uses vlr.gg's built-in search endpoint to find teams, players, events,
and series by name. Results are categorized by entity type.
"""
import logging
from urllib.parse import quote_plus

from utils.cache_manager import cache_manager
from utils.constants import CACHE_TTL_SEARCH, VLR_BASE_URL
from utils.error_handling import handle_scraper_errors, raise_for_upstream_status
from utils.html_parsers import extract_text_content, normalize_image_url, parse_html
from utils.http_client import fetch_with_retries, get_http_client
from utils.id_mapper import id_mapper

logger = logging.getLogger(__name__)


def _extract_id_from_search_href(href: str) -> str:
    """Extract numeric ID from a search redirect href like /search/r/player/9/idx."""
    if not href:
        return ""
    parts = [p for p in href.strip("/").split("/") if p.isdigit()]
    return parts[0] if parts else ""


def _infer_type_from_href(href: str) -> str:
    """Infer entity type from the search redirect URL path.

    /search/r/player/9/idx  → player
    /search/r/team/16647/idx → team
    /search/r/event/...      → event
    """
    if not href:
        return "unknown"
    parts = href.strip("/").split("/")
    for i, part in enumerate(parts):
        if part == "r" and i + 1 < len(parts):
            return parts[i + 1]  # e.g., "player", "team", "event"
    return "unknown"


@handle_scraper_errors
async def vlr_search(query: str) -> dict:
    """Search VLR.GG for teams, players, events, and series matching a query.

    Args:
        query: Search term (e.g., player name, team name, event keyword).

    Returns:
        Categorized results dict with players, teams, events keys.
    """
    async def build():
        encoded = quote_plus(query.strip())
        url = f"{VLR_BASE_URL}/search/?q={encoded}&type=all"
        client = get_http_client()
        resp = await fetch_with_retries(url, client=client)
        status = resp.status_code
        raise_for_upstream_status(status, f"search for '{query}'")

        html = parse_html(resp.text)

        players: list[dict] = []
        teams: list[dict] = []
        events: list[dict] = []

        # Result cards: all .wf-card elements except the search form (.mod-dark)
        for card in html.css(".wf-card"):
            cls = card.attributes.get("class", "")
            if "mod-dark" in cls:
                continue  # skip search form card

            items = card.css(".search-item")
            for item in items:
                href = item.attributes.get("href", "")
                entity_type = _infer_type_from_href(href)
                entity_id = _extract_id_from_search_href(href)

                name_elem = item.css_first(".search-item-title")
                name = extract_text_content(name_elem) if name_elem else ""

                desc_elem = item.css_first(".search-item-desc")
                desc = extract_text_content(desc_elem) if desc_elem else ""

                img_elem = item.css_first(".search-item-thumb img")
                img = normalize_image_url(img_elem.attributes.get("src", "")) if img_elem else ""

                # Tags (inactive, etc.) are inline spans within the title
                tag = ""
                if name_elem:
                    tag_span = name_elem.css_first("span")
                    if tag_span:
                        tag = extract_text_content(tag_span)

                entry = {
                    "id": entity_id,
                    "name": name,
                    "img": img,
                    "description": desc,
                    "tag": tag,
                }

                if entity_type == "player":
                    players.append(entry)
                elif entity_type == "team":
                    teams.append(entry)
                    id_mapper.register_team(name, entity_id)
                elif entity_type in ("event", "series"):
                    events.append(entry)
                    id_mapper.register_event(name, entity_id)

        data = {
            "data": {
                "status": status,
                "segments": {
                    "query": query.strip(),
                    "results": {
                        "players": players,
                        "teams": teams,
                        "events": events,
                    },
                },
            }
        }
        return data

    return await cache_manager.get_or_create_async(
        CACHE_TTL_SEARCH, build, "search", query.strip()
    )
