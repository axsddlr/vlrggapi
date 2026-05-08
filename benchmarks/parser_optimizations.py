"""
Benchmark: parsing optimization strategies.
Tests HTML stripping, alternative parsers, and combined approaches.
"""
import time
import statistics
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.http_client import get_http_client, fetch_with_retries
from utils.constants import VLR_BASE_URL, VLR_EVENTS_URL, VLR_NEWS_URL

URLS = {
    "events": VLR_EVENTS_URL,
    "news": VLR_NEWS_URL,
    "homepage": VLR_BASE_URL,
}
ITERATIONS = 15
WARMUP = 5


def strip_html(html: str) -> str:
    """Remove scripts, styles, comments, and excessive whitespace from HTML."""
    s = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    s = re.sub(r'<style[^>]*>.*?</style>', '', s, flags=re.DOTALL | re.IGNORECASE)
    s = re.sub(r'<!--.*?-->', '', s, flags=re.DOTALL)
    s = re.sub(r'>\s+<', '><', s)
    return s


def strip_attrs(html: str) -> str:
    """Remove data-* attributes and minimize other attributes."""
    s = re.sub(r'\s+data-[\w-]+="[^"]*"', '', html)
    return s


async def fetch_pages():
    client = get_http_client()
    pages = {}
    for name, url in URLS.items():
        resp = await fetch_with_retries(url, client=client)
        pages[name] = resp.text
    return pages


def bench(label: str, parse_fn, css_fn, html: str, iterations: int):
    for _ in range(WARMUP):
        root = parse_fn(html)
        css_fn(root)

    times_total = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        root = parse_fn(html)
        css_fn(root)
        t1 = time.perf_counter()
        times_total.append(t1 - t0)

    if times_total:
        avg = statistics.mean(times_total) * 1000
        med = statistics.median(times_total) * 1000
        lo = min(times_total) * 1000
        hi = max(times_total) * 1000
        print(f"  {label:>40s}: avg={avg:7.3f}ms  med={med:7.3f}ms  min={lo:7.3f}ms  max={hi:7.3f}ms")
    return times_total


async def main():
    print("Fetching pages from vlr.gg...")
    pages = await fetch_pages()
    print(f"Fetched {len(pages)} pages\n")

    for pname, html in pages.items():
        size_kb = len(html) / 1024
        stripped = strip_html(html)
        stripped_kb = len(stripped) / 1024
        shrink = (1 - len(stripped) / len(html)) * 100

        from selectolax.parser import HTMLParser
        import lxml.html

        print(f"{'='*65}")
        print(f"Page: {pname}  raw={size_kb:.0f}KB  stripped={stripped_kb:.0f}KB (-{shrink:.0f}%)")
        print(f"{'='*65}")

        # 1. selectolax baseline (current impl)
        bench("selectolax (baseline)",
              lambda h: HTMLParser(h),
              lambda r: (r.css("a.wf-module-item"), r.css_first(".wf-label")),
              html, ITERATIONS)

        # 2. stripped HTML + selectolax
        bench("selectolax + stripped HTML",
              lambda h: HTMLParser(h),
              lambda r: (r.css("a.wf-module-item"), r.css_first(".wf-label")),
              stripped, ITERATIONS)

        # 3. lxml.html
        bench("lxml.html",
              lambda h: lxml.html.fromstring(h),
              lambda r: (r.cssselect("a.wf-module-item"), r.cssselect(".wf-label")[:1]),
              html, ITERATIONS)

        # 4. stripped + lxml.html
        bench("lxml.html + stripped HTML",
              lambda h: lxml.html.fromstring(h),
              lambda r: (r.cssselect("a.wf-module-item"), r.cssselect(".wf-label")[:1]),
              stripped, ITERATIONS)

        # 5. selectolax with lexbor explicit
        try:
            from selectolax.lexbor import LexborHTMLParser
            bench("selectolax(lexbor)",
                  lambda h: LexborHTMLParser(h),
                  lambda r: (r.css("a.wf-module-item"), r.css_first(".wf-label")),
                  html, ITERATIONS)
        except ImportError:
            pass

        # 6. stripped + selectolax(lexbor)
        try:
            from selectolax.lexbor import LexborHTMLParser
            bench("selectolax(lexbor) + stripped",
                  lambda h: LexborHTMLParser(h),
                  lambda r: (r.css("a.wf-module-item"), r.css_first(".wf-label")),
                  stripped, ITERATIONS)
        except ImportError:
            pass

        print()

    print(f"{'='*65}")
    print("HTML size reduction per page:")
    print(f"{'='*65}")
    for pname, html in pages.items():
        stripped = strip_html(html)
        kb_before = len(html) / 1024
        kb_after = len(stripped) / 1024
        pct = (1 - len(stripped) / len(html)) * 100
        print(f"  {pname:>12s}: {kb_before:6.0f}KB -> {kb_after:6.0f}KB  (-{pct:.0f}%)")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
