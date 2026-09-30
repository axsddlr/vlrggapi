"""Tests for the event scrapers: /event/matches list and /event detail pages.

Fixtures are trimmed from real vlr.gg markup (Valorant Champions 2026,
event 2766, fetched 2026-09-30 17:44 UTC, rendered in CEST).
"""
from datetime import UTC, datetime

import pytest

import api.scrapers.events as events_module
from api.scrapers.events import _event_match_utc_offset, vlr_event_matches
from utils.cache_manager import cache_manager


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
