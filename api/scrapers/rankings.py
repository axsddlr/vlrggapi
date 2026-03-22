import logging
import re

from selectolax.parser import HTMLParser

from utils.http_client import fetch_with_retries, get_http_client
from utils.constants import VLR_RANKINGS_URL, CACHE_TTL_RANKINGS
from utils.cache_manager import cache_manager
from utils.error_handling import handle_scraper_errors, validate_region

logger = logging.getLogger(__name__)


def _normalize_text(value: str) -> str:
    """Collapse whitespace in scraped text values."""
    return re.sub(r"\s+", " ", value or "").strip()


def _extract_ranked_team_name(item) -> str:
    """Extract the ranked team name from structured DOM nodes."""
    team_link = item.css_first("a.rank-item-team")
    if not team_link:
        return ""

    candidates = [
        team_link.attributes.get("data-sort-value", ""),
    ]

    logo_img = team_link.css_first("img")
    if logo_img:
        candidates.append(logo_img.attributes.get("alt", ""))

    for candidate in candidates:
        normalized = _normalize_text(candidate)
        if normalized:
            return normalized

    team_text_elem = team_link.css_first("div.ge-text")
    if not team_text_elem:
        return _normalize_text(team_link.text())

    raw_text = _normalize_text(team_text_elem.text())
    removable_text = [
        _normalize_text(child.text())
        for child in team_text_elem.css("span.ge-text-light, div.rank-item-team-country")
    ]
    for child_text in removable_text:
        if child_text:
            raw_text = raw_text.replace(child_text, "", 1)

    return _normalize_text(raw_text)


def _extract_last_played_summary(item) -> tuple[str, str, str]:
    """Extract last-played time, opponent label, and opponent logo."""
    last_match = item.css_first("a.rank-item-last")
    if not last_match:
        return "", "", ""

    last_played = ""
    time_block = last_match.css_first("div")
    if time_block:
        last_played = _normalize_text(time_block.text())

    vs_elem = last_match.css_first(".rank-item-last-vs")
    vs_text = _normalize_text(vs_elem.text()) if vs_elem else ""

    opponent_logo = ""
    opponent_name = ""
    opponent_img = last_match.css_first("img")
    if opponent_img:
        opponent_logo = opponent_img.attributes.get("src", "")
        opponent_name = _normalize_text(opponent_img.attributes.get("alt", ""))

    if not opponent_name:
        for span in last_match.css("span"):
            span_text = _normalize_text(span.text())
            span_class = span.attributes.get("class", "")
            if span_text and "rank-item-last-vs" not in span_class:
                opponent_name = span_text
                break

    if not opponent_name:
        blocks = last_match.css("div")
        if len(blocks) > 1:
            trailing_text = _normalize_text(blocks[1].text())
            if trailing_text.startswith(vs_text):
                trailing_text = trailing_text[len(vs_text):]
            opponent_name = _normalize_text(trailing_text)

    if opponent_name and vs_text:
        last_played_team = _normalize_text(f"{vs_text} {opponent_name}")
    elif opponent_name:
        last_played_team = opponent_name
    else:
        last_played_team = ""

    return last_played, last_played_team, opponent_logo


@handle_scraper_errors
async def vlr_rankings(region_key):
    async def build():
        region_name = validate_region(region_key)
        url = f"{VLR_RANKINGS_URL}/{region_name}"

        client = get_http_client()
        resp = await fetch_with_retries(url, client=client)
        html = HTMLParser(resp.text)
        status = resp.status_code

        result = []
        for item in html.css("div.rank-item"):
            rank = _normalize_text(item.css_first("div.rank-item-rank-num").text())
            team = _extract_ranked_team_name(item)
            team_link = item.css_first("a.rank-item-team")
            team_logo = team_link.css_first("img") if team_link else None
            logo = team_logo.attributes.get("src", "") if team_logo else ""
            logo = re.sub(r"/img/vlr/tmp/vlr.png", "", logo)
            country = _normalize_text(item.css_first("div.rank-item-team-country").text())
            last_played, last_played_team, last_played_team_logo = _extract_last_played_summary(item)
            record = _normalize_text(item.css_first("div.rank-item-record").text())
            earnings = _normalize_text(item.css_first("div.rank-item-earnings").text())

            result.append(
                {
                    "rank": rank,
                    "team": team,
                    "country": country,
                    "last_played": last_played,
                    "last_played_team": last_played_team,
                    "last_played_team_logo": last_played_team_logo,
                    "record": record,
                    "earnings": earnings,
                    "logo": logo,
                }
            )

        data = {"data": {"status": status, "segments": result}}

        if status != 200:
            raise Exception("API response: {}".format(status))

        return data

    return await cache_manager.get_or_create_async(
        CACHE_TTL_RANKINGS, build, "rankings", region_key
    )
