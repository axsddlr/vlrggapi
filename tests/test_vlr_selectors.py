"""
Validate that CSS selectors used by vlrggapi scrapers still resolve
against live vlr.gg HTML.

Run this standalone or via pytest. Fails fast when vlr.gg changes break
our parsing pipeline *before* the API starts returning errors.

How it works
------------
vlr.gg renders much of its markup **conditionally on data or view**: there is
no stream pane on a match that had no streams, no agent table for a player with
no games in the selected window. A single hardcoded URL therefore cannot prove
a selector still exists — an absent selector there may simply mean the fixture
went quiet, which is how issues like #183 produced false alarms.

So every page type declares:

``anchors``
    Selectors that must be present on **every** fetched page. These prove the
    page really is what we think it is (not a rate-limit wall, a redirect, or
    an empty shell). A missing anchor is a real failure.

``required``
    Selectors that must be **witnessed on at least one** fetched page for that
    page type. Absent from all of them is a real failure; present on any one is
    proof the selector still exists.

``optional``
    Reported only when absent from **every** fetched page, so per-instance
    quirks do not generate noise. Selection of *which* pages to fetch is
    delegated to a per-page-type ``discovery`` function, so "the page type is
    healthy" is established structurally before any selector can fail.

**There is deliberately no static fallback fixture.** A hardcoded witness URL
ages: ``/player/9`` still renders, but stops rendering the agent table once the
player goes quiet, which is indistinguishable from a layout break and is exactly
how #183 reported the same "broken" selector day after day. When discovery turns
up no candidates the page type is reported as *unverifiable* — no evidence, no
verdict — instead of being graded against a stand-in. A genuine break in a
listing page still fails loudly, because each listing has its own page check.

Usage:
    pytest tests/test_vlr_selectors.py -v           # full suite
    pytest tests/test_vlr_selectors.py -v -k homepage  # single page
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import warnings
from collections.abc import Callable
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
class PageCheck:
    """Selectors to validate for a single vlr.gg page *type*.

    A page type may be backed by several witness URLs when its markup is
    data-dependent (see module docstring).
    """

    label: str  # human-readable test name
    urls: list[str]  # witness pages for this page type
    source: str = ""  # scraper file(s) that use these selectors
    anchors: list[str] = field(default_factory=list)  # must hold on every URL
    required: list[str] = field(default_factory=list)  # must hold on >= 1 URL
    optional: list[str] = field(default_factory=list)  # reported if on no URL
    # Optional selectors that only render in a rare data state (e.g. .mod-ot
    # exists only on a match that went to overtime). Absence from the witness
    # set is expected, so these are reported but never fail the build. Add a
    # selector here ONLY after checking that it really does render on some
    # live page — this list is where a false alarm could hide.
    data_conditional: list[str] = field(default_factory=list)
    discovery: str = ""  # witness-discovery key, resolved in default_witnesses()


@dataclass
class PageData:
    """One fetched page, ready to grade."""

    url: str
    tree: SelectolaxParser


# ---------------------------------------------------------------------------
# Witness discovery
# ---------------------------------------------------------------------------
#
# Hand-maintained fixture IDs rot: /player/9 (TenZ) stopped rendering an agent
# table, and a specific match ID stops carrying a stream pane, both of which
# look identical to a real layout break. Discovering candidates from vlr.gg
# listing pages at run time keeps witnesses in the state we want to assert.

_MATCH_ID_RE = re.compile(r"^/(\d+)(?:/|$)")
_PLAYER_ID_RE = re.compile(r"^/player/(\d+)(?:/|$)")

_RESULTS_URL = f"{VLR_BASE_URL}/matches/results"
_ACTIVE_PLAYERS_URL = f"{VLR_BASE_URL}/stats/?region=all&min=1"


def _extract_match_ids(tree: SelectolaxParser) -> list[str]:
    """Match IDs from a listing page (links look like ``/{id}/{slug}``)."""
    ids: list[str] = []
    for anchor in tree.css('a[href^="/"]'):
        match = _MATCH_ID_RE.match(anchor.attributes.get("href", "") or "")
        if match and match.group(1) not in ids:
            ids.append(match.group(1))
    return ids


def _extract_player_ids(tree: SelectolaxParser) -> list[str]:
    """Player IDs from a listing page (links look like ``/player/{id}/{slug}``)."""
    ids: list[str] = []
    for anchor in tree.css('a[href*="/player/"]'):
        match = _PLAYER_ID_RE.match(anchor.attributes.get("href", "") or "")
        if match and match.group(1) not in ids:
            ids.append(match.group(1))
    return ids


async def discover_match_ids(client: httpx.AsyncClient) -> list[str]:
    """Recently completed match IDs, newest first."""
    html = await _fetch_html(client, _RESULTS_URL)
    return _extract_match_ids(html)


async def discover_player_ids(client: httpx.AsyncClient) -> list[str]:
    """IDs of players with recent activity, so agent stats should render."""
    html = await _fetch_html(client, _ACTIVE_PLAYERS_URL)
    return _extract_player_ids(html)


# ---------------------------------------------------------------------------
# Page definitions
# ---------------------------------------------------------------------------

# Result pages carry the full watch module. Every match-backed page type below
# discovers its witnesses at run time, so it deliberately declares NO static
# URL: a fixed match ID eventually stops carrying streams/VODs and then looks
# exactly like a layout break (see the module docstring and #183).
_TEAM_URL = f"{VLR_BASE_URL}/team/2/sentinels"

PAGE_CHECKS: ClassVar[list[PageCheck]] = [
    # --- Homepage ---------------------------------------------------------
    PageCheck(
        label="homepage",
        urls=[VLR_BASE_URL],
        source="api/scrapers/matches.py, api/scrapers/events.py",
        anchors=[
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
    PageCheck(
        label="match_detail",
        urls=[],
        discovery="match_detail",
        source="api/scrapers/match_detail/parsers.py, api/scrapers/match_detail/crawler.py",
        anchors=[
            ".match-header-super",
            ".match-header-date",
            ".match-header-note",
            ".match-header-vs-note",
            ".match-header-link.mod-1",
            ".match-header-link.mod-2",
            ".match-header-link-name.mod-1",
            ".match-header-link-name.mod-2",
            ".match-header-vs",
        ],
        required=[
            # Watch module (streams/VODs). vlr.gg replaced the old
            # .match-streams-btn / .match-vods markup with the sm-* module.
            # Every fetched match page must carry at least one of these
            # containers, so a witness on any single page is proof.
            ".sm-root",
            ".sm-pane-streams",
            ".sm-pane-vods",
            ".sm-btn",
            ".sm-name",
            ".sm-vod",
            ".sm-vod-name",
            ".sm-ext",
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
        # Verified live: .mod-ot renders on overtime matches (e.g. /755377,
        # /743608) and is absent otherwise, so it cannot be witnessed from an
        # arbitrary match sample.
        data_conditional=[
            ".mod-ot",
        ],
    ),
    # --- Match detail performance tab ------------------------------------
    PageCheck(
        label="match_detail_perf",
        urls=[],
        discovery="match_detail_tabs",
        source="api/scrapers/match_detail/parsers.py",
        anchors=[
            ".match-header-super",
        ],
        required=[
            "table.wf-table-inset.mod-matrix.mod-normal",
            "table.wf-table-inset.mod-adv-stats",
        ],
    ),
    # --- Match detail economy tab ----------------------------------------
    PageCheck(
        label="match_detail_econ",
        urls=[],
        discovery="match_detail_tabs",
        source="api/scrapers/match_detail/parsers.py",
        anchors=[
            ".match-header-super",
        ],
        required=[
            "table.wf-table-inset.mod-econ",
        ],
    ),
    # --- Matches listing --------------------------------------------------
    PageCheck(
        label="matches",
        urls=[f"{VLR_BASE_URL}/matches"],
        source="api/scrapers/matches.py",
        anchors=[
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
    PageCheck(
        label="match_results",
        urls=[_RESULTS_URL],
        source="api/scrapers/matches.py",
        anchors=[
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
    PageCheck(
        label="events",
        urls=[f"{VLR_BASE_URL}/events"],
        source="api/scrapers/events.py",
        anchors=[
            "a.event-item",
        ],
        required=[
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
    PageCheck(
        label="event_matches",
        urls=[f"{VLR_BASE_URL}/event/matches/2977"],
        source="api/scrapers/events.py",
        anchors=[
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
    PageCheck(
        label="event_detail",
        urls=[f"{VLR_BASE_URL}/event/2977"],
        source="api/scrapers/event_detail.py",
        anchors=[
            ".event-header",
            ".event-header-main",
        ],
        required=[
            "h1.event-header-main-title",
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
    PageCheck(
        label="player",
        urls=[],
        discovery="player",
        source="api/scrapers/players.py",
        anchors=[
            "h1.wf-title",
            ".player-header",
            ".player-summary-container-1",
        ],
        required=[
            "table.st-table.mod-agent-rows",
        ],
        optional=[
            ".player-real-name",
            ".wf-avatar.mod-player img",
            ".flag",
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
    PageCheck(
        label="team",
        urls=[_TEAM_URL],
        source="api/scrapers/teams/crawlers.py, api/scrapers/teams/parsers.py",
        anchors=[
            ".team-header",
            ".team-header-name",
            ".team-header-country",
            ".team-summary-container-1",
        ],
        required=[
            "h1.wf-title",
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
    PageCheck(
        label="rankings",
        urls=[f"{VLR_BASE_URL}/rankings/north-america"],
        source="api/scrapers/rankings.py",
        anchors=[
            "div.rank-item",
        ],
        required=[
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
    PageCheck(
        label="stats",
        urls=[f"{VLR_BASE_URL}/stats"],
        source="api/scrapers/stats.py",
        anchors=[
            "table",
        ],
        optional=[
            "thead tr",
            "td.mod-player",
            "td.mod-agents img",
            'select[name="region"]',
            "tbody tr",
        ],
    ),
    # --- News -------------------------------------------------------------
    PageCheck(
        label="news",
        urls=[f"{VLR_BASE_URL}/news"],
        source="api/scrapers/news.py",
        anchors=[
            "a.wf-module-item",
        ],
        optional=[
            "div.ge-text-light",
        ],
    ),
    # --- Search -----------------------------------------------------------
    PageCheck(
        label="search",
        urls=[f"{VLR_BASE_URL}/search/?q=sentinels&type=all"],
        source="api/scrapers/search.py",
        anchors=[
            ".wf-card",
        ],
        required=[
            ".search-item",
            ".search-item-title",
        ],
        optional=[
            ".search-item-desc",
            ".search-item-thumb img",
        ],
    ),
    # --- Team sub-pages ---------------------------------------------------
    PageCheck(
        label="team_matches",
        urls=[f"{_TEAM_URL}/matches"],
        source="api/scrapers/teams/crawlers.py, api/scrapers/teams/parsers.py",
        anchors=[
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
    PageCheck(
        label="team_transactions",
        urls=[f"{VLR_BASE_URL}/team/transactions/2/sentinels"],
        source="api/scrapers/teams/crawlers.py, api/scrapers/teams/parsers.py",
        anchors=[
            "h1.wf-title",
        ],
        optional=[
            "tr.txn-item",
            ".txn-item",
            "td.txn-item-action",
            "a[href*='/player/']",
            "img",
            ".flag",
        ],
    ),
    PageCheck(
        label="team_stats",
        urls=[f"{VLR_BASE_URL}/team/stats/2/sentinels"],
        source="api/scrapers/teams/crawlers.py",
        anchors=[
            "h1.wf-title",
        ],
        optional=[
            "table.wf-table.mod-team-maps tbody tr",
            "td",
        ],
    ),
    PageCheck(
        label="player_matches",
        # The scraper reads /player/matches/{id}/, NOT /player/{id}/matches
        # (which vlr.gg serves as the profile page), so the witness has to come
        # from discovery too or this check grades the wrong markup.
        urls=[],
        discovery="player_matches",
        source="api/scrapers/players.py",
        anchors=[
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
# Witness resolution
# ---------------------------------------------------------------------------

# How many pages a discovery-backed check will actually fetch and grade.
_MAX_WITNESSES = 3
_MATCH_DETAIL_WITNESSES = 3
_MATCH_TAB_WITNESSES = 2
_PLAYER_WITNESSES = 2

_DISCOVERY_ERRORS: dict[str, str] = {}


async def _discover(client: httpx.AsyncClient, kind: str) -> list[str]:
    if kind not in ("match", "player"):
        raise ValueError(f"unknown discovery kind: {kind}")
    try:
        ids = (
            await discover_match_ids(client)
            if kind == "match"
            else await discover_player_ids(client)
        )
    except Exception as exc:  # noqa: BLE001 - reported, never fatal
        _DISCOVERY_ERRORS[kind] = f"{type(exc).__name__}: {exc}"
        return []
    # A successful discovery clears an earlier transient failure, so a stale
    # message can never be blamed for a later empty witness list.
    _DISCOVERY_ERRORS.pop(kind, None)
    return ids


def _label_witnesses(label: str, match_ids: list[str]) -> list[str]:
    """Build the witness URL list for one match-backed page type.

    An empty ``match_ids`` yields an empty witness list on purpose — see the
    module docstring: a stand-in fixture is how #183 reported a layout change
    every day for a match that had simply gone quiet.
    """
    if label == "match_detail":
        return [f"{VLR_BASE_URL}/{match_id}/" for match_id in match_ids[:_MATCH_DETAIL_WITNESSES]]
    if label in ("match_detail_perf", "match_detail_econ"):
        tab = "performance" if label.endswith("perf") else "economy"
        return [
            f"{VLR_BASE_URL}/{match_id}/?game=all&tab={tab}"
            for match_id in match_ids[:_MATCH_TAB_WITNESSES]
        ]
    raise ValueError(f"no witness builder for label: {label}")


def _discovery_kind(discovery: str) -> str:
    """Map a page type's discovery key to the discovery error bucket."""
    return "match" if discovery.startswith("match_detail") else "player"


def _no_witness_reason(pc: PageCheck) -> str:
    """Explain why a page type has nothing to grade.

    Surfacing the discovery error matters: ``_DISCOVERY_ERRORS`` used to be
    written and never read, so a blocked or restructured listing page silently
    turned into a stale-fixture verdict against our own selectors.
    """
    error = _DISCOVERY_ERRORS.get(_discovery_kind(pc.discovery))
    if error:
        return (
            f"witness discovery for {pc.label} could not read the vlr.gg listing "
            f"({error}); no selectors were asserted"
        )
    return (
        f"witness discovery for {pc.label} returned no candidate pages; "
        f"no selectors were asserted"
    )


def _no_witness_result(pc: PageCheck, urls: list[str], reason: str) -> dict:
    """Report a page type as unverifiable because there is nothing to grade.

    Deliberately not a failure. With no witness there is no evidence about our
    selectors, and asserting "broken" from a stand-in is the #183 false alarm.
    """
    return {
        "page": pc.label,
        "urls": list(urls),
        "anchors": pc.anchors,
        "source": pc.source,
        "total_required": len(pc.anchors) + len(pc.required),
        "broken_required": [],
        "broken_anchors": [],
        "unwitnessed_required": [],
        "total_optional": len(pc.optional),
        "broken_optional": [],
        "data_conditional_missing": [],
        "ci_optional_failures": 0,
        "witnessed": {},
        "witnessed_count": 0,
        "pages_fetched": 0,
        "pages_usable": 0,
        "unusable_pages": [],
        "unverifiable": True,
        "unverifiable_reason": reason,
        "fetch_error": None,
        "failed": False,
    }


async def resolve_witnesses(client: httpx.AsyncClient) -> dict[str, list[str]]:
    """Map every page label to its witness URLs, discovering where required."""
    needs_match = [
        pc.label
        for pc in PAGE_CHECKS
        if pc.discovery in ("match_detail", "match_detail_tabs")
    ]
    needs_player = [
        pc.label for pc in PAGE_CHECKS if pc.discovery in ("player", "player_matches")
    ]

    match_ids = await _discover(client, "match") if needs_match else []
    player_ids = await _discover(client, "player") if needs_player else []

    resolved: dict[str, list[str]] = {}
    for pc in PAGE_CHECKS:
        if not pc.discovery:
            resolved[pc.label] = list(pc.urls)
        elif pc.discovery in ("match_detail", "match_detail_tabs"):
            resolved[pc.label] = _label_witnesses(pc.label, match_ids)
        elif pc.discovery == "player":
            resolved[pc.label] = [
                f"{VLR_BASE_URL}/player/{pid}/" for pid in player_ids[:_PLAYER_WITNESSES]
            ]
        elif pc.discovery == "player_matches":
            resolved[pc.label] = [
                f"{VLR_BASE_URL}/player/matches/{pid}/"
                for pid in player_ids[:_PLAYER_WITNESSES]
            ]
    return resolved


async def fetch_pages(client: httpx.AsyncClient, urls: list[str]) -> tuple[list[PageData], str | None]:
    """Fetch witness pages concurrently; return (pages, fetch_error)."""
    async def one(url: str) -> object:
        try:
            return PageData(url=url, tree=await _fetch_html(client, url))
        except Exception as exc:  # noqa: BLE001 - reported, never fatal
            return exc

    results = await asyncio.gather(*(one(url) for url in urls))
    pages = [r for r in results if isinstance(r, PageData)]
    failures = [
        f"{page} ({type(r).__name__}: {r})"
        for page, r in zip(urls, results)
        if isinstance(r, Exception)
    ]
    return pages, ("; ".join(failures) if failures else None)


# ---------------------------------------------------------------------------
# Grading
# ---------------------------------------------------------------------------


def _first_present(tree: SelectolaxParser, selectors: list[str]) -> str | None:
    for selector in selectors:
        if tree.css_first(selector) is not None:
            return selector
    return None


def grade_page(pc: PageCheck, pages: list[PageData]) -> dict:
    """Grade every selector in ``pc`` across the witness pages.

    The "page still fetches at all" verdict is a *structural* question: is any
    subset of the declared anchors present? A page that renders *only* our
    optional/conditional markup but none of its structural anchors is a
    suspicious partial render, so it is discarded rather than allowed to
    generate selector noise.
    """
    good: list[PageData] = []
    structurally_bad: list[str] = []

    for page in pages:
        if _first_present(page.tree, pc.anchors) is not None:
            good.append(page)
        else:
            structurally_bad.append(page.url)

    def witness(selector: str) -> str | None:
        for page in good:
            if page.tree.css_first(selector) is not None:
                return page.url
        return None

    anchors_missing = [s for s in pc.anchors if witness(s) is None]

    required_missing: list[str] = []
    witnessed: dict[str, str] = {}
    if good:
        for selector in pc.required:
            found = witness(selector)
            if found:
                witnessed[selector] = found
            else:
                required_missing.append(selector)

    optional_missing = [s for s in pc.optional if witness(s) is None]

    # With no structurally valid page there is no evidence, so asserting either
    # way would be a guess. Report it as unverifiable rather than a layout break.
    unverifiable = not good
    broken_required = [] if unverifiable else anchors_missing + required_missing
    broken_optional = [] if unverifiable else optional_missing
    data_conditional_missing = [
        s for s in broken_optional if s in pc.data_conditional
    ]
    # Only ordinary optional markup raises the alarm in CI; a selector whose
    # absence is explained by the data state is reported, not escalated.
    ci_optional_failures = len(broken_optional) - len(data_conditional_missing)

    return {
        "page": pc.label,
        "urls": [page.url for page in pages],
        "anchors": pc.anchors,
        "source": pc.source,
        "total_required": len(pc.anchors) + len(pc.required),
        "broken_required": broken_required,
        "broken_anchors": [] if unverifiable else anchors_missing,
        "unwitnessed_required": [] if unverifiable else required_missing,
        "total_optional": len(pc.optional),
        "broken_optional": broken_optional,
        "data_conditional_missing": data_conditional_missing,
        "ci_optional_failures": ci_optional_failures,
        "witnessed": witnessed,
        "witnessed_count": len(witnessed),
        "pages_fetched": len(pages),
        "pages_usable": len(good),
        "unusable_pages": structurally_bad,
        "unverifiable": unverifiable,
        "unverifiable_reason": (
            "no witness page rendered the page's structural anchors"
            if unverifiable
            else None
        ),
        "fetch_error": None,
        "failed": bool(broken_required),
    }


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------

_REPORT_PATH = os.environ.get("SELECTOR_REPORT_PATH", "")

_FULL_REPORT: list[dict] = []

# Graded results keyed by page label, fetched once per pytest session.
_RESULTS: dict[str, dict] = {}
_RESULTS_LOCK = asyncio.Lock()
# Witness discovery is also once per session: re-discovering per page type would
# re-fetch the listing pages 19 times.
_WITNESSES: dict[str, list[str]] = {}
_WITNESSES_LOCK = asyncio.Lock()


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        headers={"User-Agent": "vlrggapi-selector-check/1.0"},
        follow_redirects=True,
    )


async def _witnesses_for(client: httpx.AsyncClient) -> dict[str, list[str]]:
    async with _WITNESSES_LOCK:
        if not _WITNESSES:
            _WITNESSES.update(await resolve_witnesses(client))
        return dict(_WITNESSES)


async def _grade_page_check(pc: PageCheck) -> dict:
    """Fetch and grade one page type, retrying transient failures."""
    async with _client() as client:
        witnesses = await _witnesses_for(client)
        urls = witnesses[pc.label]

        # Discovery-backed page types ship no stand-in fixture, so an empty
        # witness list means "nothing to grade". Saying "broken" here would be
        # blaming our selectors for a listing we could not read (#183).
        if not urls:
            return _no_witness_result(pc, urls, _no_witness_reason(pc))

        result: dict | None = None
        last_error: str | None = None
        for attempt in range(3):
            pages, fetch_error = await fetch_pages(client, urls)
            if pages:
                result = grade_page(pc, pages)
                result["fetch_error"] = fetch_error
                if not result["failed"]:
                    break
            else:
                last_error = fetch_error or "no pages fetched"
            if attempt < 2:
                await asyncio.sleep(5 * (attempt + 1))

    if result is None:
        return {
            "page": pc.label,
            "urls": urls,
            "anchors": pc.anchors,
            "source": pc.source,
            "total_required": len(pc.anchors) + len(pc.required),
            "broken_required": list(pc.anchors) + list(pc.required),
            "broken_anchors": list(pc.anchors),
            "unwitnessed_required": list(pc.required),
            "total_optional": len(pc.optional),
            "broken_optional": [],
            "data_conditional_missing": [],
            "ci_optional_failures": 0,
            "witnessed": {},
            "witnessed_count": 0,
            "pages_fetched": 0,
            "pages_usable": 0,
            "unusable_pages": [],
            "unverifiable": False,
            "unverifiable_reason": None,
            "fetch_error": last_error,
            "failed": True,
        }
    return result


def _unverifiable_skip_message(result: dict) -> str:
    """Warn and build the skip reason for a page type we could not grade.

    A skip is not a pass: with no witness the check is blind. pytest swallows
    stdout for skipped tests, so the warning *is* the visibility mechanism — it
    lands in the run's warnings summary, and in CI that reaches the Actions log
    without failing the run and without filing a false "layout change" issue.
    """
    warn = f"{result['page']}: {result['unverifiable_reason']}"
    warnings.warn(warn, stacklevel=2)
    return f"{warn}; fetched {result['pages_fetched']} page(s)"


async def _result_for(pc: PageCheck) -> dict:
    async with _RESULTS_LOCK:
        if pc.label not in _RESULTS:
            _RESULTS[pc.label] = await _grade_page_check(pc)
        return _RESULTS[pc.label]


def _write_report() -> None:
    if not _REPORT_PATH:
        return
    ordered = [_RESULTS[pc.label] for pc in PAGE_CHECKS if pc.label in _RESULTS]
    with open(_REPORT_PATH, "w") as handle:
        json.dump(ordered, handle, indent=2)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "pc",
    PAGE_CHECKS,
    ids=[pc.label for pc in PAGE_CHECKS],
)
async def test_vlr_selectors(pc: PageCheck):
    """Validate one vlr.gg page type's CSS selectors against live HTML."""
    result = await _result_for(pc)
    _write_report()

    if result["unverifiable"]:
        pytest.skip(_unverifiable_skip_message(result))

    if result["broken_required"]:
        report = json.dumps(result, indent=2)
        pytest.fail(f"Broken required selectors on {pc.label}:\n{report}")

    broken_opt = result["broken_optional"]
    if result["ci_optional_failures"] and "CI" in os.environ:
        summary = "\n  - ".join([""] + broken_opt)
        pytest.fail(
            f"{result['ci_optional_failures']} optional selector(s) missing on "
            f"every witness page for {pc.label} (failing in CI):{summary}"
        )

    if broken_opt:
        note = ""
        if result["data_conditional_missing"]:
            note = (
                " (data-conditional, not failing: "
                + ", ".join(result["data_conditional_missing"])
                + ")"
            )
        summary = "\n  - ".join([""] + broken_opt)
        print(
            f"\n  [{pc.label}] {len(broken_opt)} optional selector(s) "
            f"missing{note}:{summary}"
        )


# ---------------------------------------------------------------------------
# Standalone runner (python -m pytest tests/test_vlr_selectors.py)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import anyio

    async def _main():
        print("vlr.gg CSS selector validation")
        print("=" * 60)

        all_ok = True
        async with _client() as client:
            witnesses = await _witnesses_for(client)
            for pc in PAGE_CHECKS:
                urls = witnesses[pc.label]
                if not urls:
                    # No witness is not a break — see _no_witness_result.
                    print(f"  [{pc.label:20s}] UNVERIFIABLE: {_no_witness_reason(pc)}")
                    continue

                pages, fetch_error = await fetch_pages(client, urls)
                if not pages:
                    print(f"  [{pc.label:20s}] FETCH ERROR: {fetch_error}")
                    all_ok = False
                    continue

                result = grade_page(pc, pages)
                req = result["broken_required"]
                opt = result["broken_optional"]
                print(
                    f"  [{pc.label:20s}] witnessed={result['witnessed_count']}"
                    f"/{result['total_required']} pages={result['pages_usable']}"
                )
                if result["unverifiable"]:
                    print(f"    UNVERIFIABLE: {result['unverifiable_reason']}")
                    for url in result["unusable_pages"]:
                        print(f"      unusable: {url}")
                    continue
                for selector in req:
                    print(f"    REQUIRED MISSING: {selector}")
                    all_ok = False
                for selector in opt:
                    print(f"    optional missing: {selector}")

        print("\nAll critical selectors OK." if all_ok else "\nSome selectors are broken!")
        if not all_ok:
            sys.exit(1)

    anyio.run(_main)
