import pytest

from api.scrapers.stats import _parse_stats_row, vlr_stats
from selectolax.parser import HTMLParser
from utils.cache_manager import cache_manager


STATS_HTML = """
<html>
  <table>
    <tbody>
      <tr>
        <td class="mod-player mod-a">
          <a>
            <div class="text-of">TenZ Prime</div>
            <div class="stats-player-country">Team Liquid</div>
          </a>
        </td>
        <td class="mod-agents">
          <img src="/img/vlr/game/agents/jett.png">
          <img src="/img/vlr/game/agents/omen.png">
        </td>
        <td class="mod-rnd">442</td>
        <td class="mod-color-sq">1.36</td>
        <td class="mod-color-sq mod-acs">248.4</td>
        <td class="mod-color-sq">1.58</td>
        <td class="mod-color-sq">79%</td>
        <td class="mod-color-sq">158.5</td>
        <td class="mod-color-sq">0.90</td>
        <td class="mod-color-sq">0.36</td>
        <td class="mod-color-sq">0.07</td>
        <td class="mod-color-sq">0.05</td>
        <td class="mod-color-sq">33%</td>
        <td class="mod-color-sq">16%</td>
        <td class="mod-cl">9/57</td>
      </tr>
    </tbody>
  </table>
</html>
"""


class FakeResponse:
    def __init__(self, status_code: int, text: str):
        self.status_code = status_code
        self.text = text


class FakeAsyncClient:
    def __init__(self, response: FakeResponse):
        self.response = response
        self.calls: list[tuple[str, int | None]] = []

    async def get(self, url: str, timeout=None):
        self.calls.append((url, timeout))
        return self.response


def test_parse_stats_row_uses_structured_player_and_org_selectors():
    row = HTMLParser(STATS_HTML).css_first("tbody tr")

    assert _parse_stats_row(row) == {
        "player": "TenZ Prime",
        "org": "Team Liquid",
        "agents": ["jett", "omen"],
        "rounds_played": "442",
        "rating": "1.36",
        "average_combat_score": "248.4",
        "kill_deaths": "1.58",
        "kill_assists_survived_traded": "79%",
        "average_damage_per_round": "158.5",
        "kills_per_round": "0.90",
        "assists_per_round": "0.36",
        "first_kills_per_round": "0.07",
        "first_deaths_per_round": "0.05",
        "headshot_percentage": "33%",
        "clutch_success_percentage": "16%",
    }


@pytest.mark.anyio
async def test_vlr_stats_preserves_output_shape_with_structured_row_parsing(monkeypatch):
    cache_manager.clear_all()
    client = FakeAsyncClient(FakeResponse(200, STATS_HTML))

    monkeypatch.setattr("api.scrapers.stats.get_http_client", lambda: client)

    data = await vlr_stats("na", "30")

    assert data == {
        "data": {
            "status": 200,
            "segments": [
                {
                    "player": "TenZ Prime",
                    "org": "Team Liquid",
                    "agents": ["jett", "omen"],
                    "rounds_played": "442",
                    "rating": "1.36",
                    "average_combat_score": "248.4",
                    "kill_deaths": "1.58",
                    "kill_assists_survived_traded": "79%",
                    "average_damage_per_round": "158.5",
                    "kills_per_round": "0.90",
                    "assists_per_round": "0.36",
                    "first_kills_per_round": "0.07",
                    "first_deaths_per_round": "0.05",
                    "headshot_percentage": "33%",
                    "clutch_success_percentage": "16%",
                }
            ],
        }
    }
    assert client.calls == [
        (
            "https://www.vlr.gg/stats/?event_group_id=all&event_id=all&region=na&country=all&min_rounds=200&min_rating=1550&agent=all&map_id=all&timespan=30d",
            None,
        )
    ]
    cache_manager.clear_all()
