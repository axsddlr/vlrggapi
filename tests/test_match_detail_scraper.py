import asyncio

import pytest

from api.scrapers.match_detail import vlr_match_detail
from utils.cache_manager import cache_manager

PLAYER_ROW = """
<tr>
  <td class="mod-player"><div class="text-of">TenZ</div></td>
  <td class="mod-agents"><img alt="Jett"></td>
  <td>1.20</td>
  <td>250</td>
  <td>20</td>
  <td>15</td>
  <td>5</td>
  <td>+5</td>
  <td>75%</td>
  <td>160</td>
  <td>30%</td>
  <td>3</td>
  <td>2</td>
  <td>+1</td>
</tr>
"""


BASE_MATCH_HTML = f"""
<html>
  <a class="match-header-link wf-link-hover mod-1" href="/team/100/team-one">
    <div class="match-header-link-name mod-1">
      <div class="wf-title-med">Team One</div>
      <div>ONE</div>
    </div>
  </a>
  <a class="match-header-link wf-link-hover mod-2" href="/team/200/team-two">
    <div class="match-header-link-name mod-2">
      <div class="wf-title-med">Team Two</div>
      <div>TWO</div>
    </div>
  </a>
  <div class="vm-stats-gamesnav-item" data-game-id="game-1"></div>
  <div class="vm-stats-gamesnav-item" data-game-id="game-2"></div>

  <div class="vm-stats-game" data-game-id="game-1">
    <div class="vm-stats-game-header">
      <div class="map">Ascent<div class="picked">Team One</div><div class="map-duration">30:00</div></div>
      <div class="team"><div class="score">13</div><div class="mod-ct">7</div><div class="mod-t">6</div></div>
      <div class="team"><div class="score">11</div><div class="mod-ct">5</div><div class="mod-t">6</div></div>
    </div>
    <table class="wf-table-inset mod-overview"><tbody>{PLAYER_ROW}</tbody></table>
    <table class="wf-table-inset mod-overview"><tbody>{PLAYER_ROW}</tbody></table>
  </div>

  <div class="vm-stats-game" data-game-id="game-2">
    <div class="vm-stats-game-header">
      <div class="map">Bind<div class="picked">Team Two</div><div class="map-duration">32:00</div></div>
      <div class="team"><div class="score">10</div><div class="mod-ct">4</div><div class="mod-t">6</div></div>
      <div class="team"><div class="score">13</div><div class="mod-ct">7</div><div class="mod-t">6</div></div>
    </div>
    <table class="wf-table-inset mod-overview"><tbody>{PLAYER_ROW}</tbody></table>
    <table class="wf-table-inset mod-overview"><tbody>{PLAYER_ROW}</tbody></table>
  </div>
</html>
"""


def performance_html(opponent_name: str) -> str:
    return f"""
    <html>
      <table class="wf-table-inset mod-matrix mod-normal">
        <thead><tr><th>Player</th><th>{opponent_name}</th></tr></thead>
        <tbody><tr><td>TenZ</td><td>5</td></tr></tbody>
      </table>
      <table class="wf-table-inset mod-adv-stats">
        <thead><tr><th>Player</th><th>2K</th></tr></thead>
        <tbody><tr><td>TenZ</td><td>3</td></tr></tbody>
      </table>
    </html>
    """


def economy_html(team_name: str) -> str:
    return f"""
    <html>
      <table class="wf-table-inset mod-econ">
        <thead><tr><th>Team</th><th>Pistol</th></tr></thead>
        <tbody><tr><td>{team_name}</td><td>50%</td></tr></tbody>
      </table>
    </html>
    """


class FakeResponse:
    def __init__(self, status_code: int, text: str):
        self.status_code = status_code
        self.text = text
        self.headers: dict = {}


class FakeAsyncClient:
    def __init__(self, responses: dict[str, list[FakeResponse]]):
        self._responses = responses
        self.calls: list[tuple[str, int | None]] = []

    async def get(self, url: str, timeout=None):
        self.calls.append((url, timeout))
        return self._responses[url].pop(0)


@pytest.mark.anyio
async def test_vlr_match_detail_fetches_performance_and_economy_for_all_games(monkeypatch):
    cache_manager.clear_all()
    client = FakeAsyncClient(
        {
            "https://www.vlr.gg/555": [FakeResponse(200, BASE_MATCH_HTML)],
            "https://www.vlr.gg/555/?game=game-1&tab=performance": [FakeResponse(200, performance_html("Opponent A"))],
            "https://www.vlr.gg/555/?game=game-1&tab=economy": [FakeResponse(200, economy_html("Team One"))],
            "https://www.vlr.gg/555/?game=game-2&tab=performance": [FakeResponse(200, performance_html("Opponent B"))],
            "https://www.vlr.gg/555/?game=game-2&tab=economy": [FakeResponse(200, economy_html("Team Two"))],
        }
    )

    monkeypatch.setattr("api.scrapers.match_detail.get_http_client", lambda: client)

    data = await vlr_match_detail("555")
    segment = data["data"]["segments"][0]

    assert data["data"]["status"] == 200
    assert segment["teams"] == [
        {
            "id": "100",
            "name": "Team One",
            "tag": "ONE",
            "logo": "",
            "score": "",
            "is_winner": False,
        },
        {
            "id": "200",
            "name": "Team Two",
            "tag": "TWO",
            "logo": "",
            "score": "",
            "is_winner": False,
        },
    ]
    assert segment["performance"]["kill_matrix"] == [{"player": "TenZ", "kills_vs": {"Opponent A": "5"}}]
    assert segment["performance"]["advanced_stats"] == [{"player": "TenZ", "2K": "3"}]
    assert segment["economy"] == [{"Team": "Team One", "Pistol": "50%"}]
    assert segment["performance"]["by_map"] == [
        {
            "game_id": "game-1",
            "kill_matrix": [{"player": "TenZ", "kills_vs": {"Opponent A": "5"}}],
            "advanced_stats": [{"player": "TenZ", "2K": "3"}],
        },
        {
            "game_id": "game-2",
            "kill_matrix": [{"player": "TenZ", "kills_vs": {"Opponent B": "5"}}],
            "advanced_stats": [{"player": "TenZ", "2K": "3"}],
        },
    ]
    assert segment["economy_by_map"] == [
        {"game_id": "game-1", "rows": [{"Team": "Team One", "Pistol": "50%"}]},
        {"game_id": "game-2", "rows": [{"Team": "Team Two", "Pistol": "50%"}]},
    ]
    assert segment["maps"][0]["performance"] == {
        "kill_matrix": [{"player": "TenZ", "kills_vs": {"Opponent A": "5"}}],
        "advanced_stats": [{"player": "TenZ", "2K": "3"}],
    }
    assert segment["maps"][0]["economy"] == [{"Team": "Team One", "Pistol": "50%"}]
    assert segment["maps"][1]["performance"] == {
        "kill_matrix": [{"player": "TenZ", "kills_vs": {"Opponent B": "5"}}],
        "advanced_stats": [{"player": "TenZ", "2K": "3"}],
    }
    assert segment["maps"][1]["economy"] == [{"Team": "Team Two", "Pistol": "50%"}]
    assert len(client.calls) == 5
    cache_manager.clear_all()


@pytest.mark.anyio
async def test_vlr_match_detail_limits_tab_fetches_and_falls_back_on_tab_error(monkeypatch):
    cache_manager.clear_all()
    active_fetches = 0
    max_active_fetches = 0
    tab_timeouts: list[int | None] = []

    async def fake_fetch_with_retries(
        url,
        *,
        client=None,
        timeout=None,
        max_retries=3,
        request_delay=1.0,
    ):
        nonlocal active_fetches, max_active_fetches
        if url == "https://www.vlr.gg/888":
            return FakeResponse(200, BASE_MATCH_HTML)

        tab_timeouts.append(timeout)
        active_fetches += 1
        max_active_fetches = max(max_active_fetches, active_fetches)
        try:
            await asyncio.sleep(0)
            if url.endswith("game=game-2&tab=economy"):
                return FakeResponse(503, "<html></html>")
            if "tab=performance" in url:
                return FakeResponse(200, performance_html("Opponent"))
            return FakeResponse(200, economy_html("Team"))
        finally:
            active_fetches -= 1

    monkeypatch.setattr("api.scrapers.match_detail.get_http_client", lambda: object())
    monkeypatch.setattr(
        "api.scrapers.match_detail.fetch_with_retries", fake_fetch_with_retries
    )
    monkeypatch.setattr("api.scrapers.match_detail.MATCH_DETAIL_TAB_FETCH_CONCURRENCY", 2)
    monkeypatch.setattr("api.scrapers.match_detail.MATCH_DETAIL_TAB_FETCH_TIMEOUT", 11)

    data = await vlr_match_detail("888")
    segment = data["data"]["segments"][0]

    assert max_active_fetches <= 2
    assert tab_timeouts == [11] * 4
    assert segment["economy_by_map"][1] == {"game_id": "game-2", "rows": []}
    assert segment["maps"][1]["economy"] == []
    cache_manager.clear_all()


@pytest.mark.anyio
async def test_vlr_match_detail_uses_empty_team_id_when_header_link_is_missing(monkeypatch):
    cache_manager.clear_all()
    client = FakeAsyncClient(
        {
            "https://www.vlr.gg/777": [
                FakeResponse(
                    200,
                    BASE_MATCH_HTML.replace(
                        '<a class="match-header-link wf-link-hover mod-2" href="/team/200/team-two">\n'
                        '    <div class="match-header-link-name mod-2">\n'
                        '      <div class="wf-title-med">Team Two</div>\n'
                        '      <div>TWO</div>\n'
                        '    </div>\n'
                        '  </a>\n',
                        '<div class="match-header-link-name mod-2">\n'
                        '  <div class="wf-title-med">Team Two</div>\n'
                        '  <div>TWO</div>\n'
                        '</div>\n',
                    ),
                )
            ],
            "https://www.vlr.gg/777/?game=game-1&tab=performance": [FakeResponse(200, performance_html("Opponent A"))],
            "https://www.vlr.gg/777/?game=game-1&tab=economy": [FakeResponse(200, economy_html("Team One"))],
            "https://www.vlr.gg/777/?game=game-2&tab=performance": [FakeResponse(200, performance_html("Opponent B"))],
            "https://www.vlr.gg/777/?game=game-2&tab=economy": [FakeResponse(200, economy_html("Team Two"))],
        }
    )

    monkeypatch.setattr("api.scrapers.match_detail.get_http_client", lambda: client)

    data = await vlr_match_detail("777")
    teams = data["data"]["segments"][0]["teams"]

    assert teams[0]["id"] == "100"
    assert teams[1]["id"] == ""
    cache_manager.clear_all()
