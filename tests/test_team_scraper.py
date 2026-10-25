import pytest
from fastapi import HTTPException

from api.scrapers.teams import (
    vlr_team,
    vlr_team_matches,
    vlr_team_stats,
    vlr_team_transactions,
)
from api.scrapers.teams.parsers import _extract_prize_from_text, _parse_single_roster_item
from utils.cache_manager import cache_manager
from utils.html_parsers import parse_html

ROSTER_ITEM_HTML = """
<div class="team-roster-item">
  <a href="/player/1234/thuy">
    <div class="team-roster-item-img"><img src="/img/player.png"></div>
    <div class="team-roster-item-name">
      <div class="team-roster-item-name-alias">Thuy</div>
      <div class="team-roster-item-name-real">Ngoc-Thuy Duong</div>
      Coach
    </div>
  </a>
</div>
"""


def test_roster_role_survives_an_alias_embedded_in_the_real_name():
    """Stripping every occurrence of the alias leaves fragments that look like a role."""
    item = parse_html(ROSTER_ITEM_HTML).css_first(".team-roster-item")

    player = _parse_single_roster_item(item, is_staff=True)

    assert player["alias"] == "Thuy"
    assert player["real_name"] == "Ngoc-Thuy Duong"
    assert player["role"] == "Coach"


class FakeResponse:
    def __init__(self, status_code: int, text: str = "<html></html>"):
        self.status_code = status_code
        self.text = text
        self.content = text.encode("utf-8")
        self.headers: dict = {}


class FakeAsyncClient:
    def __init__(self, response: FakeResponse):
        self.response = response
        self.calls: list[tuple[str, int | None]] = []

    async def get(self, url: str, timeout=None, headers=None):
        self.calls.append((url, timeout))
        return self.response


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1st $50,0002024", "$50,000"),
        ("2nd $2,024", "$2,024"),
        ("special prize $2024", "$2024"),
        ("winner $100K 2024", "$100K"),
        ("no prize here", ""),
        ("", ""),
    ],
)
def test_extract_prize_from_text_handles_concatenated_years(text, expected):
    assert _extract_prize_from_text(text) == expected


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("scraper", "args", "expected_status", "expected_detail"),
    [
        (vlr_team, ("77",), 404, "VLR.GG returned status 404 for team 77"),
        (
            vlr_team_matches,
            ("77", 3),
            503,
            "VLR.GG returned status 503 for team matches 77 page 3",
        ),
        (
            vlr_team_transactions,
            ("77",),
            429,
            "VLR.GG returned status 429 for team transactions 77",
        ),
    ],
)
async def test_team_scrapers_raise_http_errors_for_upstream_failures(
    monkeypatch, scraper, args, expected_status, expected_detail
):
    client = FakeAsyncClient(FakeResponse(expected_status))

    monkeypatch.setattr("api.scrapers.teams.crawlers.get_http_client", lambda: client)

    with pytest.raises(HTTPException) as exc_info:
        await scraper(*args)

    assert exc_info.value.status_code == expected_status
    assert exc_info.value.detail == expected_detail


@pytest.mark.anyio
async def test_team_stats_sends_the_date_window_and_caches_per_window(monkeypatch):
    cache_manager.clear_all()
    stats_page = (
        "<html><body><table class='wf-table mod-team-maps'><tbody></tbody></table>"
        "<div class='team-summary-container'></div></body></html>"
    )
    client = FakeAsyncClient(FakeResponse(200, stats_page))

    monkeypatch.setattr("api.scrapers.teams.crawlers.get_http_client", lambda: client)

    await vlr_team_stats("77", "2026-01-01")
    await vlr_team_stats("77", "2026-01-01")  # cached: no new fetch
    await vlr_team_stats("77", "2026-02-01")  # different window: separate entry

    urls = [url for url, _timeout in client.calls]
    assert urls == [
        "https://www.vlr.gg/team/stats/77/?date_start=2026-01-01",
        "https://www.vlr.gg/team/stats/77/?date_start=2026-02-01",
    ]
