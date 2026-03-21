import pytest

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
