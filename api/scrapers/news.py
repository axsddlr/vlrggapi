import logging
import re

from selectolax.parser import HTMLParser

from utils.http_client import fetch_with_retries, get_http_client
from utils.constants import VLR_NEWS_URL, CACHE_TTL_NEWS
from utils.cache_manager import cache_manager
from utils.error_handling import handle_scraper_errors

logger = logging.getLogger(__name__)


def _iter_children(node):
    """Yield direct child nodes in document order."""
    child = node.child if node else None
    while child is not None:
        yield child
        child = child.next


def _extract_news_text(item) -> tuple[str, str]:
    """Extract title and description from the item's direct content block."""
    content = next((child for child in _iter_children(item) if child.tag == "div"), None)
    if content is None:
        return "", ""

    blocks = [child for child in _iter_children(content) if child.tag == "div"]
    title = blocks[0].text(strip=True) if blocks else ""
    description = blocks[1].text(strip=True) if len(blocks) > 1 else ""
    return title, description


def _normalize_meta_fragment(text: str) -> str:
    """Normalize legacy and current bullet separators for metadata parsing."""
    text = text.replace("\xa0", " ").replace("â€¢", "•")
    return re.sub(r"\s+", " ", text).strip()


def _extract_news_meta(item) -> tuple[str, str]:
    """Extract date and author from the metadata block."""
    meta = item.css_first("div.ge-text-light")
    if meta is None:
        return "", ""

    date = ""
    author = ""
    text_fragments: list[str] = []

    for child in _iter_children(meta):
        if child.tag != "-text":
            continue
        fragment = _normalize_meta_fragment(child.text())
        if not fragment or fragment == "•":
            continue
        text_fragments.append(fragment)
        if fragment.lower().startswith("by "):
            author = fragment[3:].strip()
        elif not date:
            date = fragment.strip("• ").strip()

    if author or len(text_fragments) > 1:
        return date, author

    meta_text = _normalize_meta_fragment(meta.text())
    before_author, separator, after_author = meta_text.rpartition(" by ")
    if separator:
        author = after_author.strip()
        meta_text = before_author.strip()

    meta_text = re.sub(r"^\s*posted\s*", "", meta_text, flags=re.IGNORECASE)
    parts = [part.strip() for part in re.split(r"\s*[•]\s*", meta_text) if part.strip()]
    date = parts[-1] if parts else meta_text.strip()
    return date, author


@handle_scraper_errors
async def vlr_news():
    cached = cache_manager.get(CACHE_TTL_NEWS, "news")
    if cached is not None:
        return cached

    client = get_http_client()
    resp = await fetch_with_retries(VLR_NEWS_URL, client=client)
    html = HTMLParser(resp.text)
    status = resp.status_code

    result = []
    for item in html.css("a.wf-module-item"):
        title, desc = _extract_news_text(item)
        date, author = _extract_news_meta(item)
        url = item.attributes.get("href", "")

        result.append(
            {
                "title": title,
                "description": desc,
                "date": date,
                "author": author,
                "url_path": f"https://www.vlr.gg{url}",
            }
        )

    data = {"data": {"status": status, "segments": result}}

    if status != 200:
        raise Exception("API response: {}".format(status))

    cache_manager.set(CACHE_TTL_NEWS, data, "news")
    return data
