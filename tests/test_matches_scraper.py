import pytest
import httpx

from api.scrapers.matches import vlr_live_score, vlr_upcoming_matches
from utils.cache_manager import cache_manager


UPCOMING_HTML = """
<html>
  <div class="js-home-matches-upcoming">
    <a class="wf-module-item">
      <div class="h-match-eta mod-upcoming">51m</div>
      <div class="h-match-team">
        <div class="h-match-team-name">Alpha</div>
      </div>
      <div class="h-match-team">
        <div class="h-match-team-name">Beta</div>
      </div>
    </a>
  </div>
</html>
"""


LIVE_HTML = """
<html>
  <div class="js-home-matches-upcoming">
    <a class="wf-module-item" href="/123">
      <div class="h-match-eta mod-live">LIVE</div>
      <div class="h-match-team">
        <div class="h-match-team-name">Team One</div>
        <div class="h-match-team-score">12</div>
        <div class="h-match-team-rounds">
          <span class="mod-ct">6</span>
        </div>
      </div>
      <div class="h-match-team"></div>
    </a>
  </div>
</html>
"""


MATCH_DETAIL_HTML = "<html></html>"

MULTI_LIVE_HTML = """
<html>
  <div class="js-home-matches-upcoming">
    <a class="wf-module-item" href="/101">
      <div class="h-match-eta mod-live">LIVE</div>
      <div class="h-match-team"><div class="h-match-team-name">One</div><div class="h-match-team-score">1</div></div>
      <div class="h-match-team"><div class="h-match-team-name">Two</div><div class="h-match-team-score">2</div></div>
    </a>
    <a class="wf-module-item" href="/102">
      <div class="h-match-eta mod-live">LIVE</div>
      <div class="h-match-team"><div class="h-match-team-name">Three</div><div class="h-match-team-score">3</div></div>
      <div class="h-match-team"><div class="h-match-team-name">Four</div><div class="h-match-team-score">4</div></div>
    </a>
    <a class="wf-module-item" href="/103">
      <div class="h-match-eta mod-live">LIVE</div>
      <div class="h-match-team"><div class="h-match-team-name">Five</div><div class="h-match-team-score">5</div></div>
      <div class="h-match-team"><div class="h-match-team-name">Six</div><div class="h-match-team-score">6</div></div>
    </a>
  </div>
</html>
"""


class FakeResponse:
    def __init__(self, status_code: int, text: str):
        self.status_code = status_code
        self.text = text


class FakeAsyncClient:
    def __init__(self, responses: dict[str, list[FakeResponse]]):
        self._responses = responses
        self.calls: list[tuple[str, int | None]] = []

    async def get(self, url: str, timeout=None):
        self.calls.append((url, timeout))
        return self._responses[url].pop(0)


@pytest.mark.anyio
async def test_vlr_upcoming_matches_handles_missing_homepage_fields(monkeypatch):
    cache_manager.clear_all()
    client = FakeAsyncClient(
        {
            "https://www.vlr.gg": [FakeResponse(200, UPCOMING_HTML)],
        }
    )

    monkeypatch.setattr("api.scrapers.matches.get_http_client", lambda: client)

    data = await vlr_upcoming_matches()

    assert data == {
        "data": {
            "status": 200,
            "segments": [
                {
                    "team1": "Alpha",
                    "team2": "Beta",
                    "flag1": "",
                    "flag2": "",
                    "time_until_match": "51m from now",
                    "match_series": "",
                    "match_event": "",
                    "unix_timestamp": "",
                    "match_page": "",
                }
            ],
        }
    }
    cache_manager.clear_all()


@pytest.mark.anyio
async def test_vlr_live_score_handles_missing_homepage_fields(monkeypatch):
    cache_manager.clear_all()
    client = FakeAsyncClient(
        {
            "https://www.vlr.gg": [FakeResponse(200, LIVE_HTML)],
            "https://www.vlr.gg/123": [FakeResponse(200, MATCH_DETAIL_HTML)],
        }
    )

    monkeypatch.setattr("api.scrapers.matches.get_http_client", lambda: client)

    data = await vlr_live_score()

    assert data == {
        "data": {
            "status": 200,
            "segments": [
                {
                    "team1": "Team One",
                    "team2": "TBD",
                    "flag1": "",
                    "flag2": "",
                    "team1_logo": "",
                    "team2_logo": "",
                    "score1": "12",
                    "score2": "",
                    "team1_round_ct": "6",
                    "team1_round_t": "N/A",
                    "team2_round_ct": "N/A",
                    "team2_round_t": "N/A",
                    "map_number": "Unknown",
                    "current_map": "Unknown",
                    "time_until_match": "LIVE",
                    "match_event": "",
                    "match_series": "",
                    "unix_timestamp": "",
                    "match_page": "https://www.vlr.gg/123",
                }
            ],
        }
    }
    cache_manager.clear_all()


@pytest.mark.anyio
async def test_vlr_live_score_limits_concurrent_detail_fetches_and_falls_back_on_timeout(monkeypatch):
    cache_manager.clear_all()
    client = FakeAsyncClient(
        {
            "https://www.vlr.gg": [FakeResponse(200, MULTI_LIVE_HTML)],
        }
    )

    active_fetches = 0
    max_active_fetches = 0

    async def fake_fetch_with_retries(url, *, client=None, timeout=None, max_retries=3, request_delay=1.0):
        nonlocal active_fetches, max_active_fetches
        if url == "https://www.vlr.gg":
            return await client.get(url, timeout=timeout)

        active_fetches += 1
        max_active_fetches = max(max_active_fetches, active_fetches)
        try:
            if url.endswith("/102"):
                raise httpx.ReadTimeout("timed out")
            return FakeResponse(200, MATCH_DETAIL_HTML)
        finally:
            active_fetches -= 1

    monkeypatch.setattr("api.scrapers.matches.get_http_client", lambda: client)
    monkeypatch.setattr("api.scrapers.matches.fetch_with_retries", fake_fetch_with_retries)
    monkeypatch.setattr("api.scrapers.matches.LIVE_DETAIL_FETCH_CONCURRENCY", 2)
    monkeypatch.setattr("api.scrapers.matches.LIVE_DETAIL_FETCH_TIMEOUT", 7)

    data = await vlr_live_score()

    assert max_active_fetches <= 2
    assert [segment["match_page"] for segment in data["data"]["segments"]] == [
        "https://www.vlr.gg/101",
        "https://www.vlr.gg/102",
        "https://www.vlr.gg/103",
    ]
    timed_out_segment = data["data"]["segments"][1]
    assert timed_out_segment["team1_logo"] == ""
    assert timed_out_segment["team2_logo"] == ""
    assert timed_out_segment["current_map"] == "Unknown"
    assert timed_out_segment["map_number"] == "Unknown"
    cache_manager.clear_all()
