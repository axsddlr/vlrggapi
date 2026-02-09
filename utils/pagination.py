"""
Shared pagination and retry logic for multi-page scrapers.
"""
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Callable, List

from selectolax.parser import HTMLParser

from utils.http_client import get_http_client
from utils.constants import DEFAULT_RETRIES, DEFAULT_REQUEST_DELAY, DEFAULT_TIMEOUT

logger = logging.getLogger(__name__)


@dataclass
class PaginationConfig:
    """Encapsulates pagination parameters and page range calculation."""
    num_pages: int = 1
    from_page: int | None = None
    to_page: int | None = None
    max_retries: int = DEFAULT_RETRIES
    request_delay: float = DEFAULT_REQUEST_DELAY
    timeout: int = DEFAULT_TIMEOUT

    def get_page_range(self) -> tuple[int, int, int]:
        """Calculate (start_page, end_page, total_pages) from the params."""
        if self.from_page is not None and self.to_page is not None:
            start = max(1, self.from_page)
            end = max(start, self.to_page)
            return start, end, end - start + 1

        if self.from_page is not None:
            start = max(1, self.from_page)
            end = start + self.num_pages - 1
            return start, end, self.num_pages

        if self.to_page is not None:
            end = max(1, self.to_page)
            start = max(1, end - self.num_pages + 1)
            return start, end, end - start + 1

        # Default: from page 1
        return 1, self.num_pages, self.num_pages


async def scrape_multiple_pages(
    base_url: str,
    parse_func: Callable[[HTMLParser, int], list[dict]],
    config: PaginationConfig,
    page_url_func: Callable[[str, int], str] | None = None,
) -> dict:
    """
    Generic multi-page scraper with retry and exponential backoff.

    Args:
        base_url: The base URL for page 1 (e.g. "https://www.vlr.gg/matches").
        parse_func: Callable(html: HTMLParser, page: int) -> list[dict].
        config: PaginationConfig with page range and retry settings.
        page_url_func: Optional callable(base_url, page) -> url. Defaults to
                       appending ?page=N for page > 1.

    Returns:
        dict in the standard response shape.
    """
    start_page, end_page, total_pages = config.get_page_range()
    client = get_http_client()
    result: list[dict] = []
    failed_pages: list[int] = []

    if page_url_func is None:
        def page_url_func(base: str, page: int) -> str:
            return base if page == 1 else f"{base}/?page={page}"

    logger.info(
        "Scraping pages %d-%d (%d pages) with %.1fs delay",
        start_page, end_page, total_pages, config.request_delay,
    )

    for page in range(start_page, end_page + 1):
        page_success = False
        retry_count = 0

        while not page_success and retry_count < config.max_retries:
            try:
                url = page_url_func(base_url, page)
                logger.info(
                    "Scraping page %d (%d/%d) attempt %d/%d",
                    page, page - start_page + 1, total_pages,
                    retry_count + 1, config.max_retries,
                )

                resp = await client.get(url, timeout=config.timeout)

                if resp.status_code != 200:
                    logger.warning("Page %d returned status %d", page, resp.status_code)
                    retry_count += 1
                    if retry_count < config.max_retries:
                        await asyncio.sleep(config.request_delay * (2 ** retry_count))
                    continue

                html = HTMLParser(resp.text)
                page_results = parse_func(html, page)
                result.extend(page_results)
                logger.info("Page %d: %d items", page, len(page_results))
                page_success = True

                if page < end_page:
                    await asyncio.sleep(config.request_delay)

            except Exception as e:
                retry_count += 1
                logger.warning(
                    "Error on page %d attempt %d/%d: %s",
                    page, retry_count, config.max_retries, e,
                )
                if retry_count < config.max_retries:
                    await asyncio.sleep(config.request_delay * (2 ** retry_count))

        if not page_success:
            failed_pages.append(page)
            logger.error("Failed page %d after %d attempts", page, config.max_retries)

    successful_pages = total_pages - len(failed_pages)
    logger.info(
        "Scraping done: %d matches, %d/%d pages OK",
        len(result), successful_pages, total_pages,
    )

    return {
        "data": {
            "status": 200,
            "segments": result,
            "meta": {
                "page_range": f"{start_page}-{end_page}",
                "total_pages_requested": total_pages,
                "successful_pages": successful_pages,
                "failed_pages": failed_pages,
                "total_matches": len(result),
            },
        }
    }
