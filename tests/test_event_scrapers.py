"""Tests for the event scrapers: /event/matches list and /event detail pages.

Fixtures are trimmed from real vlr.gg markup (Valorant Champions 2026,
event 2766, fetched 2026-09-30 17:44 UTC, rendered in CEST).
"""
from datetime import UTC, datetime

import pytest

import api.scrapers.events as events_module
from api.scrapers.event_detail import _parse_prizes, _parse_standings
from api.scrapers.events import _event_match_utc_offset, vlr_event_matches
from utils.cache_manager import cache_manager
from utils.html_parsers import parse_html


class FakeResponse:
    def __init__(self, status_code: int, text: str = "<html></html>"):
        self.status_code = status_code
        self.text = text
        self.content = text.encode("utf-8")
        self.headers: dict = {}


class FakeAsyncClient:
    def __init__(self, responses: dict[str, FakeResponse]):
        self.responses = responses
        self.calls: list[str] = []

    async def get(self, url: str, timeout=None, headers=None):
        self.calls.append(url)
        return self.responses[url]


def _match_item(href, time, team1, team2, ml_class, status, eta, series, stage):
    return f"""
    <a href="{href}" class="wf-module-item match-item mod-color">
        <div class="match-item-time">
            {time}
        </div>
        <div class="match-item-vs">
            <div class="match-item-vs-team ">
                <div class="match-item-vs-team-name"><div class="text-of"><span class="flag mod-eu"></span>{team1}</div></div>
                <div class="match-item-vs-team-score sp-mask mod-dash">&ndash;</div>
            </div>
            <div class="match-item-vs-team ">
                <div class="match-item-vs-team-name"><div class="text-of"><span class="flag mod-sg"></span>{team2}</div></div>
                <div class="match-item-vs-team-score sp-mask mod-dash">&ndash;</div>
            </div>
        </div>
        <div class="match-item-eta">
            <div class="{ml_class}">
                <div class="ml-status">{status}</div>
                <div class="ml-eta{' mod-completed' if 'mod-completed' in ml_class else ''}">{eta}</div>
            </div>
        </div>
        <div class="match-item-note"></div>
        <div class="match-item-event text-of">
            <div class="match-item-event-series text-of">
                {series}
            </div>
            {stage}
        </div>
    </a>"""


EVENT_MATCHES_HTML = f"""
<html><body>
<div class="wf-label mod-large">
    Wed, September 30, 2026
    <span class="wf-tag" style="vertical-align: -3px; margin-left: 4px;">Today</span>
</div>
<div class="wf-card">
    {_match_item("/753448/team-vitality-vs-loud-valorant-champions-2026-winners-b", "11:00 AM",
                 "Team Vitality", "LOUD", "ml mod-completed", "Completed", "8h 45m", "Winner's (B)", "Group Stage")}
</div>
<div class="wf-label mod-large">
    Thu, October 1, 2026
</div>
<div class="wf-card">
    {_match_item("/753457/tyloo-vs-team-liquid-valorant-champions-2026-elim-c", "11:00 AM",
                 "TYLOO", "Team Liquid", "ml", "Upcoming", "15h 15m", "Elimination (C)", "Group Stage")}
</div>
<div class="wf-label mod-large">
    Sun, October 18, 2026
</div>
<div class="wf-card">
    {_match_item("/753480/tbd-vs-tbd-valorant-champions-2026-gf", "8:00 AM",
                 "TBD", "TBD", "ml", "Upcoming", "2w 3d", "Grand Final", "Playoffs")}
</div>
</body></html>
"""

FETCHED_AT = datetime(2026, 9, 30, 17, 44, 25, tzinfo=UTC)


class _FrozenDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return FETCHED_AT if tz is None else FETCHED_AT.astimezone(tz)


@pytest.mark.anyio
async def test_vlr_event_matches_emits_stage_time_and_utc_timestamp(monkeypatch):
    cache_manager.clear_all()
    client = FakeAsyncClient({"https://www.vlr.gg/event/matches/2766": FakeResponse(200, EVENT_MATCHES_HTML)})
    monkeypatch.setattr("api.scrapers.events.get_http_client", lambda: client)
    monkeypatch.setattr(events_module, "datetime", _FrozenDatetime)

    result = await vlr_event_matches("2766")
    rows = result["data"]["segments"]

    assert [r["date"] for r in rows] == [
        "Wed, September 30, 2026",
        "Thu, October 1, 2026",
        "Sun, October 18, 2026",
    ]
    assert [r["stage"] for r in rows] == ["Group Stage", "Group Stage", "Playoffs"]
    assert [r["event_series"] for r in rows] == ["Winner's (B)", "Elimination (C)", "Grand Final"]
    assert [r["time"] for r in rows] == ["11:00 AM", "11:00 AM", "8:00 AM"]
    # Page rendered in CEST (UTC+2): the countdowns pin the offset, which then
    # applies to every row, including the one with a day-precision countdown
    assert [r["unix_timestamp"] for r in rows] == [
        "2026-09-30 09:00:00",
        "2026-10-01 09:00:00",
        "2026-10-18 06:00:00",
    ]
    cache_manager.clear_all()


@pytest.mark.anyio
async def test_vlr_event_matches_leaves_timestamp_empty_without_a_minute_countdown(monkeypatch):
    cache_manager.clear_all()
    html = EVENT_MATCHES_HTML.replace("8h 45m", "1w 2d").replace("15h 15m", "1d 3h")
    client = FakeAsyncClient({"https://www.vlr.gg/event/matches/2766": FakeResponse(200, html)})
    monkeypatch.setattr("api.scrapers.events.get_http_client", lambda: client)
    monkeypatch.setattr(events_module, "datetime", _FrozenDatetime)

    result = await vlr_event_matches("2766")
    rows = result["data"]["segments"]

    assert [r["unix_timestamp"] for r in rows] == ["", "", ""]
    assert [r["time"] for r in rows] == ["11:00 AM", "11:00 AM", "8:00 AM"]
    cache_manager.clear_all()


def test_event_match_utc_offset_handles_negative_offsets():
    # A page rendered in US Pacific (UTC-7): 2:00 AM local, starting in 1h 30m
    now = datetime(2026, 9, 30, 7, 30, tzinfo=UTC)
    local = datetime(2026, 9, 30, 2, 0)
    offset = _event_match_utc_offset([(local, "1h 30m", 1)], now)
    assert offset is not None
    assert offset.total_seconds() == -7 * 3600


def test_event_match_utc_offset_skips_live_and_unparsed_rows():
    now = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
    rows = [
        (datetime(2026, 9, 30, 14, 0), "LIVE", 0),
        (None, "2h 0m", 1),
        (datetime(2026, 9, 30, 14, 0), "3d 2h", 1),
    ]
    assert _event_match_utc_offset(rows, now) is None


# --- /event/{id}: standings ---

def _group_row(href, name, region, w, lo, t, maps, rounds, diff):
    return f"""
    <tr class=" mod-adv ">
        <td style="border-right: 0; padding-right: 8px;">
            <img src="/img/vlr/tmp/vlr.png" class="event-group-team-logo">
        </td>
        <td style="height: 53px;">
            <a class="event-group-team" href="{href}">
                <div class="event-group-team-name text-of">
                    {name}
                    <div class="ge-text-light event-group-team-region">
                        {region}
                    </div>
                </div>
            </a>
            <div class="event-group-spoiler-placeholder"><div>Spoiler hidden</div><div>&nbsp;</div></div>
        </td>
        <td class="mod-center mod-record" style="font-weight: 700;">{w}</td>
        <td class="mod-center mod-record" style="font-weight: 700;">{lo}</td>
        <td class="mod-center mod-record">{t}</td>
        <td class="mod-center mod-stat">{maps[0]}<span class="record-div">/</span>{maps[1]}</td>
        <td class="mod-center mod-stat">{rounds[0]}<span class="record-div">/</span>{rounds[1]}</td>
        <td class="mod-center mod-stat"><span class="diff mod-positive">{diff}</span></td>
    </tr>"""


def _group_table(title, rows):
    return f"""
    <div class="event-group-block wf-card mod-dark">
        <table class="wf-table mod-simple mod-group">
            <thead>
                <tr>
                    <th class="mod-title" colspan="2">{title}</th>
                    <th class="mod-w mod-center" title="Wins">W</th>
                    <th class="mod-l mod-center" title="Losses">L</th>
                    <th class="mod-t mod-center" title="Ties">T</th>
                    <th class="mod-center mod-maps mod-wide" title="Maps Won/Maps Lost">MAP</th>
                    <th class="mod-center mod-rfra mod-wide" title="Rounds Won/Rounds Lost">RND</th>
                    <th class="mod-center mod-dt mod-wide" title="Round Differential">&Delta;</th>
                </tr>
            </thead>
            <tbody>{"".join(rows)}</tbody>
        </table>
    </div>"""


# Trimmed from vlr.gg/event/3123 (Komplettligaen 2026: Autumn Division 1, group-stage view)
ROUND_ROBIN_HTML = f"""
<div class="event-content"><div style="display: flex; flex-direction: column;">
<div style=" margin-bottom: 22px;">
    <div class="wf-label mod-large">
        Round Robin
    </div>
    <div class="event-group mod-fullwidth">
        {_group_table("", [
            _group_row("/team/23405/monark", "Monark", "Norway", 5, 0, 0, (6, 1), (87, 56), "+31"),
            _group_row("/team/17599/uia-kraken", "UiA Kraken", "International", 4, 1, 0, (8, 3), (135, 102), "+33"),
        ])}
    </div>
</div>
</div></div>
"""

MULTI_GROUP_HTML = f"""
<div class="wf-label mod-large">Group Stage</div>
<div class="event-group">
    {_group_table("Group A", [_group_row("/team/1/a", "Alpha", "Europe", 3, 0, 0, (6, 0), (78, 30), "+48")])}
    {_group_table("Group B", [_group_row("/team/2/b", "Bravo", "Brazil", 2, 1, 0, (4, 3), (80, 70), "+10")])}
</div>
"""


def test_parse_standings_reads_round_robin_group_tables():
    standings = _parse_standings(parse_html(ROUND_ROBIN_HTML))

    assert standings == [{
        "stage": "Round Robin",
        "group": "",
        "columns": ["Team", "W", "L", "T", "MAP", "RND", "\u0394"],
        "rows": [
            {"Team": "Monark", "W": "5", "L": "0", "T": "0", "MAP": "6/1", "RND": "87/56", "\u0394": "+31"},
            {"Team": "UiA Kraken", "W": "4", "L": "1", "T": "0", "MAP": "8/3", "RND": "135/102", "\u0394": "+33"},
        ],
    }]


def test_parse_standings_names_each_group_of_a_multi_group_stage():
    standings = _parse_standings(parse_html(MULTI_GROUP_HTML))

    assert [(s["stage"], s["group"], s["rows"][0]["Team"]) for s in standings] == [
        ("Group Stage", "Group A", "Alpha"),
        ("Group Stage", "Group B", "Bravo"),
    ]


# --- /event/{id}: prizes ---

PRIZE_TABLE_HTML = """
<div class="wf-label mod-large">Prize Distribution</div>
<div class="wf-card mod-dark" style="margin-bottom: 30px; ">
    <div class="wf-ptable wf-ptable--standings" role="table">
        <div class="row" role="row">
            <div class="cell" role="cell">Place</div>
            <div class="cell" role="cell">Prize</div>
            <div class="cell" role="cell">Team</div>
        </div>
        <div class="row " role="row">
            <div class="cell" role="cell">1<sup>st</sup></div>
            <div class="cell" role="cell">$1,000,000</div>
            <div class="cell mod-team" role="cell">
                <div class="ge-text-light">
                    <img src="/img/vlr/tmp/vlr.png">
                    TBD
                </div>
            </div>
        </div>
    </div>
</div>
"""


def test_parse_prizes_finds_the_prize_table_after_group_cards():
    # Group tables and group match cards are .wf-card.mod-dark as well and
    # precede the prize table on a group-stage view
    group_match_card = '<a class="wf-card event-group-series-match mod-dark" href="/755587/x">R1</a>'
    html = parse_html(ROUND_ROBIN_HTML + group_match_card + PRIZE_TABLE_HTML)

    prizes = _parse_prizes(html)

    assert [(p["placement"], p["amount"], p["team"]["name"]) for p in prizes] == [("1st", "$1,000,000", "")]
