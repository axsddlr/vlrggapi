"""
Validate that CSS selectors used by vlrggapi scrapers still resolve
against live vlr.gg HTML.

Run this standalone or via pytest. Fails fast when vlr.gg changes break
our parsing pipeline *before* the API starts returning errors.

Usage:
    pytest tests/test_vlr_selectors.py -v           # full suite
    pytest tests/test_vlr_selectors.py -v -k homepage  # single page
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from dataclasses import dataclass, field
from typing import ClassVar

import httpx
import pytest
from selectolax.parser import HTMLParser as SelectolaxParser

from utils.constants import VLR_BASE_URL

# ---------------------------------------------------------------------------
# Helper: fetch + parse
# ---------------------------------------------------------------------------


async def _fetch_html(client: httpx.AsyncClient, url: str) -> SelectolaxParser:
    resp = await client.get(url, timeout=30)
    resp.raise_for_status()
    return SelectolaxParser(resp.text)


# ---------------------------------------------------------------------------
# Selector definition
# ---------------------------------------------------------------------------


@dataclass
class SelectorSet:
    """Group of selectors to validate on a single vlr.gg page."""

    label: str  # human-readable test name
    url: str
    required: list[str] = field(default_factory=list)  # .css_first() == must exist
    optional: list[str] = field(default_factory=list)  # .css() == at least one
    source: str = ""  # scraper file(s) that use these selectors


# ---------------------------------------------------------------------------
# Page definitions
# ---------------------------------------------------------------------------

_MATCH_DETAIL_URL = f"{VLR_BASE_URL}/706350"
_TEAM_URL = f"{VLR_BASE_URL}/team/2/sentinels"
_PLAYER_URL = f"{VLR_BASE_URL}/player/9"

SELECTOR_SETS: ClassVar[list[SelectorSet]] = [
    # --- Homepage ---------------------------------------------------------
    SelectorSet(
        label="homepage",
        url=VLR_BASE_URL,
        source="api/scrapers/matches.py, api/scrapers/events.py",
        required=[
            ".js-home-matches-upcoming a.wf-module-item",
        ],
        optional=[
            ".h-match-eta",
            ".h-match-team",
            ".h-match-team-name",
            ".h-match-team-score",
            ".h-match-preview-event",
            ".h-match-preview-series",
            ".h-match-eta.mod-upcoming",
            ".flag",
            "div.js-home-events",
            "h1.wf-label.mod-sidebar",
            "div.wf-module.wf-card.mod-sidebar",
            "a.event-item",
            ".event-item-name",
            "img.event-item-icon",
            "div.event-item-tag",
        ],
    ),
    # --- Match detail -----------------------------------------------------
    SelectorSet(
        label="match_detail",
        url=_MATCH_DETAIL_URL,
        source="api/scrapers/match_detail/parsers.py, api/scrapers/match_detail/crawler.py",
        required=[
            ".match-header-super",
            ".match-header-date",
            ".match-header-note",
            ".match-header-vs-note",
            ".match-header-link.mod-1",
            ".match-header-link.mod-2",
            ".match-header-link-name.mod-1",
            ".match-header-link-name.mod-2",
            ".match-header-vs",
            ".match-streams-btn",
            ".match-vods",
        ],
        optional=[
            ".match-header-event img",
            ".match-header-event-series",
            ".match-header-vs-score span",
            "div.vm-stats-game",
            ".vm-stats-game-header .map",
            ".map-duration",
            ".team",
            ".score",
            ".mod-ct",
            ".mod-t",
            ".mod-ot",
            ".ovw-cell",
            ".ovw-player-name",
            ".ovw-agents",
            ".side.mod-both",
            ".vlr-rounds",
            ".vlr-rounds-row",
            ".vlr-rounds-row-col",
            ".rnd-sq",
            ".match-histories-item",
            ".match-histories-item-result",
            ".rf",
            ".ra",
            ".match-histories-item-opponent-name",
            ".match-histories-item-date",
            ".match-h2h-matches",
            ".vm-stats-gamesnav-item",
        ],
    ),
    # --- Match detail performance tab ------------------------------------
    SelectorSet(
        label="match_detail_perf",
        url=f"{_MATCH_DETAIL_URL}/?game=all&tab=performance",
        source="api/scrapers/match_detail/parsers.py",
        required=[],
        optional=[
            "table.wf-table-inset.mod-matrix.mod-normal",
            "table.wf-table-inset.mod-adv-stats",
        ],
    ),
    # --- Match detail economy tab ----------------------------------------
    SelectorSet(
        label="match_detail_econ",
        url=f"{_MATCH_DETAIL_URL}/?game=all&tab=economy",
        source="api/scrapers/match_detail/parsers.py",
        required=[],
        optional=[
            "table.wf-table-inset.mod-econ",
        ],
    ),
    # --- Matches listing --------------------------------------------------
    SelectorSet(
        label="matches",
        url=f"{VLR_BASE_URL}/matches",
        source="api/scrapers/matches.py",
        required=[
            ".wf-label.mod-large",
        ],
        optional=[
            "a.wf-module-item",
            ".ml-eta",
            ".ml-status",
            ".match-item-vs-team",
            ".match-item-vs-team-name",
            ".match-item-vs-team-score",
            ".match-item-event-series",
            ".match-item-event",
            ".match-item-icon img",
            ".match-item-note",
            ".match-item-time",
        ],
    ),
    # --- Match results ----------------------------------------------------
    SelectorSet(
        label="match_results",
        url=f"{VLR_BASE_URL}/matches/results",
        source="api/scrapers/matches.py",
        required=[
            ".wf-label.mod-large",
        ],
        optional=[
            "a.wf-module-item",
            "div.ml-eta",
            "div.match-item-event-series",
            "div.match-item-event",
            "div.match-item-vs",
            ".flag",
        ],
    ),
    # --- Events -----------------------------------------------------------
    SelectorSet(
        label="events",
        url=f"{VLR_BASE_URL}/events",
        source="api/scrapers/events.py",
        required=[
            "a.event-item",
            ".event-item-title",
            ".event-item-desc-item-status",
            ".event-item-desc-item.mod-prize",
            ".event-item-desc-item.mod-dates",
            ".event-item-desc-item.mod-location .flag",
            ".event-item-thumb img",
        ],
        optional=[
            "div.wf-label.mod-large.mod-upcoming",
            "div.wf-label.mod-large.mod-completed",
        ],
    ),
    # --- Event matches ----------------------------------------------------
    SelectorSet(
        label="event_matches",
        url=f"{VLR_BASE_URL}/event/matches/2977",
        source="api/scrapers/events.py",
        required=[
            ".wf-label.mod-large",
        ],
        optional=[
            "a.wf-module-item.match-item",
            ".match-item-vs-team",
            ".match-item-vs-team-name",
            ".match-item-vs-team-score",
            ".match-item-event-series",
            ".ml-status",
            ".ml-eta",
            ".match-item-note",
        ],
    ),
    # --- Event detail -----------------------------------------------------
    SelectorSet(
        label="event_detail",
        url=f"{VLR_BASE_URL}/event/2977",
        source="api/scrapers/event_detail.py",
        required=[
            "h1.event-header-main-title",
            ".event-header",
            ".event-header-main",
        ],
        optional=[
            ".event-header-thumb img",
            ".event-header-main-bc",
            "h2.event-header-main-desc",
            ".event-header-main-meta",
            ".wf-card.mod-dark",
            ".wf-ptable",
            ".wf-card.event-team",
            ".event-team-name",
            ".event-team-players-item",
            ".wf-label",
        ],
    ),
    # --- Player profile ---------------------------------------------------
    SelectorSet(
        label="player",
        url=_PLAYER_URL,
        source="api/scrapers/players.py",
        required=[
            "h1.wf-title",
            ".player-header",
            ".player-summary-container-1",
        ],
        optional=[
            ".player-real-name",
            ".wf-avatar.mod-player img",
            ".flag",
            "table.st-table.mod-agent-rows",
            ".wf-module-item.player-event-item",
            "a.wf-card.m-item",
            "a.wf-card.fc-flex.m-item",
            ".m-item-result",
            ".m-item-team",
            ".m-item-team-name",
            ".m-item-team-tag",
            ".m-item-logo img",
            ".m-item-event",
            ".m-item-date",
        ],
    ),
    # --- Team profile -----------------------------------------------------
    SelectorSet(
        label="team",
        url=_TEAM_URL,
        source="api/scrapers/teams/crawlers.py, api/scrapers/teams/parsers.py",
        required=[
            "h1.wf-title",
            ".team-header",
            ".team-header-name",
            ".team-header-country",
            ".team-summary-container-1",
        ],
        optional=[
            ".team-header-desc",
            ".team-header-links",
            ".team-roster-item",
            ".team-roster-item-name-alias",
            ".team-roster-item-name-real",
            ".team-roster-item-img img",
            ".team-rating-info",
            ".team-rating-info-section.mod-rank",
            ".team-rating-info-section.mod-rating",
            ".team-rating-info-section.mod-streak",
            "a.wf-card.m-item",
            "a.wf-card.fc-flex.m-item",
            ".m-item-result",
            ".m-item-team",
            ".m-item-team-name",
            ".m-item-team-tag",
            ".m-item-logo img",
            ".m-item-event",
            ".m-item-date",
            "a.team-event-item",
            ".team-event-item-series",
        ],
    ),
    # --- Rankings (regional page used by scraper) -----------------------
    SelectorSet(
        label="rankings",
        url=f"{VLR_BASE_URL}/rankings/north-america",
        source="api/scrapers/rankings.py",
        required=[
            "div.rank-item",
            "div.rank-item-rank-num",
            "a.rank-item-team",
            "div.rank-item-record",
            "div.rank-item-rating",
        ],
        optional=[
            "div.rank-item-earnings",
            "div.rank-item-streak",
            "a.rank-item-last",
            ".rank-item-last-vs",
        ],
    ),
    # --- Stats ------------------------------------------------------------
    SelectorSet(
        label="stats",
        url=f"{VLR_BASE_URL}/stats",
        source="api/scrapers/stats.py",
        required=[
            "table",
        ],
        optional=[
            "thead tr",
            "td.mod-player",
            "td.mod-agents img",
            "select[name=\"region\"]",
            "tbody tr",
        ],
    ),
    # --- News -------------------------------------------------------------
    SelectorSet(
        label="news",
        url=f"{VLR_BASE_URL}/news",
        source="api/scrapers/news.py",
        required=[
            "a.wf-module-item",
        ],
        optional=[
            "div.ge-text-light",
        ],
    ),
    # --- Search -----------------------------------------------------------
    SelectorSet(
        label="search",
        url=f"{VLR_BASE_URL}/search/?q=sentinels&type=all",
        source="api/scrapers/search.py",
        required=[
            ".wf-card",
            ".search-item",
            ".search-item-title",
        ],
        optional=[
            ".search-item-desc",
            ".search-item-thumb img",
        ],
    ),
    # --- Team sub-pages ---------------------------------------------------
    SelectorSet(
        label="team_matches",
        url=f"{_TEAM_URL}/matches",
        source="api/scrapers/teams/crawlers.py, api/scrapers/teams/parsers.py",
        required=[
            "h1.wf-title",
        ],
        optional=[
            "a.wf-card.m-item",
            "a.wf-card.fc-flex.m-item",
            "a.m-item",
            ".m-item-result",
            ".m-item-team",
            ".m-item-team-name",
            ".m-item-team-tag",
            ".m-item-logo img",
            ".m-item-event",
            ".m-item-date",
        ],
    ),
    SelectorSet(
        label="team_transactions",
        url=f"{VLR_BASE_URL}/team/transactions/2/sentinels",
        source="api/scrapers/teams/crawlers.py, api/scrapers/teams/parsers.py",
        required=[],
        optional=[
            "tr.txn-item",
            ".txn-item",
            "td.txn-item-action",
            "a[href*='/player/']",
            "img",
            ".flag",
        ],
    ),
    SelectorSet(
        label="team_stats",
        url=f"{VLR_BASE_URL}/team/stats/2/sentinels",
        source="api/scrapers/teams/crawlers.py",
        required=[
            "h1.wf-title",
        ],
        optional=[
            "table.wf-table.mod-team-maps tbody tr",
            "td",
        ],
    ),
    SelectorSet(
        label="player_matches",
        url=f"{_PLAYER_URL}/matches",
        source="api/scrapers/players.py",
        required=[
            "h1.wf-title",
        ],
        optional=[
            "a.wf-card.m-item",
            "a.wf-card.fc-flex.m-item",
            ".m-item-result",
            ".m-item-team",
            ".m-item-team-name",
            ".m-item-team-tag",
            ".m-item-logo img",
            ".m-item-event",
            ".m-item-date",
        ],
    ),
]


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------

_REPORT_PATH = os.environ.get("SELECTOR_REPORT_PATH", "")


def _check_selectors(html: SelectolaxParser, ss: SelectorSet) -> dict:
    """Return dict with detailed broken-selector report."""
    broken_required: list[str] = []
    broken_optional: list[str] = []

    for sel in ss.required:
        if html.css_first(sel) is None:
            broken_required.append(sel)

    for sel in ss.optional:
        if len(html.css(sel)) == 0:
            broken_optional.append(sel)

    return {
        "page": ss.label,
        "url": ss.url,
        "source": ss.source,
        "total_required": len(ss.required),
        "broken_required": broken_required,
        "total_optional": len(ss.optional),
        "broken_optional": broken_optional,
        "failed": bool(broken_required),
    }


_FULL_REPORT: list[dict] = []


@pytest.mark.anyio
@pytest.mark.parametrize(
    "ss",
    SELECTOR_SETS,
    ids=[ss.label for ss in SELECTOR_SETS],
)
async def test_vlr_selectors(ss: SelectorSet):
    """Validate every scraper CSS selector against live vlr.gg HTML."""
    async with httpx.AsyncClient(
        headers={"User-Agent": "vlrggapi-selector-check/1.0"},
        follow_redirects=True,
    ) as client:
        html = await _fetch_html(client, ss.url)
    result = _check_selectors(html, ss)

    # Accumulate for JSON report and always write (last test wins with full data)
    if _REPORT_PATH:
        result["fetch_error"] = None
        _FULL_REPORT.append(result)
        with open(_REPORT_PATH, "w") as f:
            json.dump(_FULL_REPORT, f, indent=2)

    if result["broken_required"]:
        report = json.dumps(result, indent=2)
        pytest.fail(f"Broken required selectors on {ss.label}:\n{report}")

    broken_opt = result["broken_optional"]
    if broken_opt and "CI" in os.environ:
        summary = "\n  - ".join([""] + broken_opt)
        pytest.fail(
            f"{len(broken_opt)} optional selector(s) broken on "
            f"{ss.label} (failing in CI):{summary}"
        )

    if broken_opt:
        summary = "\n  - ".join([""] + broken_opt)
        print(
            f"\n  [{ss.label}] {len(broken_opt)} optional selector(s) "
            f"missing:{summary}"
        )

# ---------------------------------------------------------------------------
# Standalone runner (python tests/test_vlr_selectors.py)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import anyio

    async def _main():
        print("vlr.gg CSS selector validation")
        print("=" * 60)

        all_ok = True
        async with httpx.AsyncClient(
            headers={"User-Agent": "vlrggapi-selector-check/1.0"},
            follow_redirects=True,
        ) as client:
            for ss in SELECTOR_SETS:
                try:
                    html = await _fetch_html(client, ss.url)
                except Exception as exc:
                    print(f"  [{ss.label}] FETCH ERROR: {exc}")
                    all_ok = False
                    continue

                result = _check_selectors(html, ss)
                req = result["broken_required"]
                opt = result["broken_optional"]

                status = "OK" if not req and not opt else "BROKEN"
                print(f"  [{ss.label:20s}] {status}")
                if req:
                    for s in req:
                        print(f"    REQUIRED MISSING: {s}")
                    all_ok = False
                if opt:
                    for s in opt:
                        print(f"    optional missing: {s}")

        if all_ok:
            print("\nAll critical selectors OK.")
        else:
            print("\nSome selectors are broken!")
            sys.exit(1)

    anyio.run(_main)
