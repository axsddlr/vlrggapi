import logging
import re

from selectolax.parser import HTMLParser

from utils.http_client import get_http_client
from utils.constants import VLR_RANKINGS_URL, CACHE_TTL_RANKINGS
from utils.cache_manager import cache_manager
from utils.error_handling import handle_scraper_errors, validate_region

logger = logging.getLogger(__name__)


@handle_scraper_errors
async def vlr_rankings(region_key):
    cached = cache_manager.get(CACHE_TTL_RANKINGS, "rankings", region_key)
    if cached is not None:
        return cached

    region_name = validate_region(region_key)
    url = f"{VLR_RANKINGS_URL}/{region_name}"

    client = get_http_client()
    resp = await client.get(url)
    html = HTMLParser(resp.text)
    status = resp.status_code

    result = []
    for item in html.css("div.rank-item"):
        rank = item.css_first("div.rank-item-rank-num").text().strip()
        team = item.css_first("div.ge-text").text().split("#")[0]
        logo = item.css_first("a.rank-item-team").css_first("img").attributes["src"]
        logo = re.sub(r"\/img\/vlr\/tmp\/vlr.png", "", logo)
        country = item.css_first("div.rank-item-team-country").text()
        last_played = (
            item.css_first("a.rank-item-last")
            .text()
            .replace("\n", "")
            .replace("\t", "")
            .split("v")[0]
        )
        last_played_team = (
            item.css_first("a.rank-item-last")
            .text()
            .replace("\t", "")
            .replace("\n", "")
            .split("o")[1]
            .replace(".", ". ")
        )
        last_played_team_logo = (
            item.css_first("a.rank-item-last").css_first("img").attributes["src"]
        )
        record = (
            item.css_first("div.rank-item-record")
            .text()
            .replace("\t", "")
            .replace("\n", "")
        )
        earnings = (
            item.css_first("div.rank-item-earnings")
            .text()
            .replace("\t", "")
            .replace("\n", "")
        )

        result.append(
            {
                "rank": rank,
                "team": team.strip(),
                "country": country,
                "last_played": last_played.strip(),
                "last_played_team": last_played_team.strip(),
                "last_played_team_logo": last_played_team_logo,
                "record": record,
                "earnings": earnings,
                "logo": logo,
            }
        )

    # Consistent response shape (v2). V1 router reshapes for backwards compat.
    data = {"data": {"status": status, "segments": result}}

    if status != 200:
        raise Exception("API response: {}".format(status))

    cache_manager.set(CACHE_TTL_RANKINGS, data, "rankings", region_key)
    return data
