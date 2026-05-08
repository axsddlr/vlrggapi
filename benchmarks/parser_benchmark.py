"""
Benchmark: selectolax vs BeautifulSoup vs Scrapling HTML parser performance.
Tests parsing + CSS selector extraction on real vlr.gg pages.
"""
import time
import statistics
import sys
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.http_client import get_http_client, fetch_with_retries
from utils.constants import VLR_BASE_URL, VLR_EVENTS_URL, VLR_NEWS_URL

URLS = {
    "events": VLR_EVENTS_URL,
    "news": VLR_NEWS_URL,
    "homepage": VLR_BASE_URL,
}

ITERATIONS = 10
WARMUP = 3


async def fetch_pages():
    client = get_http_client()
    pages = {}
    for name, url in URLS.items():
        resp = await fetch_with_retries(url, client=client)
        pages[name] = resp.text
    return pages


def bench_selectolax(html: str, iterations: int):
    from selectolax.parser import HTMLParser
    # warmup
    for _ in range(WARMUP):
        parser = HTMLParser(html)
        _ = parser.css("a")
        _ = parser.css_first(".wf-module-item")

    times_parse = []
    times_css = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        parser = HTMLParser(html)
        t1 = time.perf_counter()
        _ = parser.css("a.wf-module-item")
        _ = parser.css_first(".wf-label")
        t2 = time.perf_counter()
        times_parse.append(t1 - t0)
        times_css.append(t2 - t1)
    return times_parse, times_css


def bench_beautifulsoup(html: str, iterations: int, backend: str = "lxml"):
    from bs4 import BeautifulSoup
    for _ in range(WARMUP):
        soup = BeautifulSoup(html, backend)
        _ = soup.select("a")
        _ = soup.select_one(".wf-module-item")

    times_parse = []
    times_css = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        soup = BeautifulSoup(html, backend)
        t1 = time.perf_counter()
        _ = soup.select("a.wf-module-item")
        _ = soup.select_one(".wf-label")
        t2 = time.perf_counter()
        times_parse.append(t1 - t0)
        times_css.append(t2 - t1)
    return times_parse, times_css


def bench_scrapling(html: str, iterations: int):
    from scrapling.parser import Selector
    for _ in range(WARMUP):
        page = Selector(html)
        _ = page.css("a")
        _ = page.css(".wf-module-item")[0]

    times_parse = []
    times_css = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        page = Selector(html)
        t1 = time.perf_counter()
        _ = page.css("a.wf-module-item")
        _ = page.css(".wf-label")[0]
        t2 = time.perf_counter()
        times_parse.append(t1 - t0)
        times_css.append(t2 - t1)
    return times_parse, times_css


def fmt_stats(label: str, data: list[float]):
    avg = statistics.mean(data) * 1000
    med = statistics.median(data) * 1000
    lo = min(data) * 1000
    hi = max(data) * 1000
    return f"  {label:>20s}: avg={avg:7.3f}ms  med={med:7.3f}ms  min={lo:7.3f}ms  max={hi:7.3f}ms"


async def main():
    import httpx
    print("Fetching pages from vlr.gg...")
    pages = await fetch_pages()
    print(f"Fetched {len(pages)} pages\n")

    for pname, html in pages.items():
        size_kb = len(html) / 1024
        print(f"{'='*60}")
        print(f"Page: {pname} ({size_kb:.0f} KB)")
        print(f"{'='*60}")

        # selectolax
        try:
            tp, tc = bench_selectolax(html, ITERATIONS)
            print("selectolax:")
            print(fmt_stats("parse", tp))
            print(fmt_stats("css selectors", tc))
        except Exception as e:
            print(f"selectolax FAILED: {e}")

        # BeautifulSoup + lxml
        try:
            tp, tc = bench_beautifulsoup(html, ITERATIONS, "lxml")
            print("BeautifulSoup(lxml):")
            print(fmt_stats("parse", tp))
            print(fmt_stats("css selectors", tc))
        except Exception as e:
            print(f"BeautifulSoup(lxml) FAILED: {e}")

        # BeautifulSoup + html.parser
        try:
            tp, tc = bench_beautifulsoup(html, ITERATIONS, "html.parser")
            print("BeautifulSoup(html.parser):")
            print(fmt_stats("parse", tp))
            print(fmt_stats("css selectors", tc))
        except Exception as e:
            print(f"BeautifulSoup(html.parser) FAILED: {e}")

        # Scrapling
        try:
            tp, tc = bench_scrapling(html, ITERATIONS)
            print("Scrapling Selector:")
            print(fmt_stats("parse", tp))
            print(fmt_stats("css selectors", tc))
        except Exception as e:
            print(f"Scrapling FAILED: {e}")

        print()

    # size check on all packages
    print(f"{'='*60}")
    print("Package sizes (installed):")
    print(f"{'='*60}")
    for mod_name, import_name in [("selectolax", "selectolax"), ("beautifulsoup4", "bs4"),
                                   ("lxml", "lxml"), ("scrapling[all]", "scrapling")]:
        try:
            mod = __import__(import_name)
            mod_dir = Path(mod.__file__).resolve().parent
            total = sum(f.stat().st_size for f in mod_dir.rglob("*") if f.is_file()) / 1024 / 1024
            print(f"  {mod_name:>25s}: {total:.1f} MB")
        except Exception as e:
            print(f"  {mod_name:>25s}: not installed ({e})")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
