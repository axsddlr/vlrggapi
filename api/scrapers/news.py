import logging

from selectolax.parser import HTMLParser

from utils.http_client import get_http_client
from utils.constants import VLR_NEWS_URL, CACHE_TTL_NEWS
from utils.cache_manager import cache_manager
from utils.error_handling import handle_scraper_errors

logger = logging.getLogger(__name__)


@handle_scraper_errors
async def vlr_news():
    cached = cache_manager.get(CACHE_TTL_NEWS, "news")
    if cached is not None:
        return cached

    client = get_http_client()
    resp = await client.get(VLR_NEWS_URL)
    html = HTMLParser(resp.text)
    status = resp.status_code

    result = []
    for item in html.css("a.wf-module-item"):
        date_author = item.css_first("div.ge-text-light").text()
        date, author = date_author.split("by")

        desc = item.css_first("div").css_first("div:nth-child(2)").text().strip()

        title = item.css_first("div:nth-child(1)").text().strip().split("\n")[0]
        title = title.replace("\t", "")

        url = item.css_first("a.wf-module-item").attributes["href"]

        result.append(
            {
                "title": title,
                "description": desc,
                "date": date.split("\u2022")[1].strip(),
                "author": author.strip(),
                "url_path": f"https://www.vlr.gg{url}",
            }
        )

    data = {"data": {"status": status, "segments": result}}

    if status != 200:
        raise Exception("API response: {}".format(status))

    cache_manager.set(CACHE_TTL_NEWS, data, "news")
    return data
