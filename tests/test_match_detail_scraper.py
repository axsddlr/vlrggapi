import asyncio

import pytest

from api.scrapers.match_detail import vlr_match_detail
from api.scrapers.match_detail.parsers import (
    _parse_economy,
    _parse_maps,
    _parse_rounds,
    _parse_streams_vods,
)
from utils.cache_manager import cache_manager
from utils.html_parsers import parse_html

# vlr.gg markup since the late-2026 "sm-*" streams/VODs redesign (issue #183).
# Streams live in .sm-pane-streams as .sm-btn blocks whose external URL is an
# <a class="sm-ext"> sibling; VODs live in .sm-pane-vods as .sm-vod blocks with
# a .sm-vod-name label. The old .match-streams-btn / .match-vods selectors are
# gone from the page entirely.
STREAMS_VODS_HTML = """
<html>
  <div class="sm-root js-sm-root mod-cols mod-vods">
    <div class="sm-pane sm-pane-streams">
      <div class="sm-group">
        <label class="zx-chk"><input type="checkbox" class="js-sm-sw"><span>Official</span></label>
      </div>
      <div class="match-streams-container js-sm-grid">
        <div class="sm-btn mod-embed" data-type="broadcast" data-site="twitch">
          <div class="sm-body js-stream-embed-btn" data-site-id="valorant_americas" data-embed-site="twitch">
            <i class="flag mod-us"></i><span class="sm-name">VCT Americas</span>
          </div>
          <a class="sm-ext" href="https://www.twitch.tv/valorant_americas" target="_blank" title="Open on Twitch">
            <i class="sm-plat fa fa-twitch"></i>
          </a>
        </div>
        <div class="sm-btn mod-embed" data-type="watchparty" data-site="kick">
          <div class="sm-body js-stream-embed-btn" data-site-id="sliggy" data-embed-site="kick">
            <span class="sm-name">Sliggy</span>
          </div>
          <a class="sm-ext" href="https://kick.com/sliggy" target="_blank" title="Open on Kick">
            <i class="sm-plat fa fa-kick"></i>
          </a>
        </div>
      </div>
    </div>
    <div class="sm-pane sm-pane-vods">
      <div class="sm-vods match-streams-container mod-fill">
        <div class="sm-vod mod-embed" data-site="youtube">
          <div class="sm-body js-stream-embed-btn" data-embed-kind="vod" data-site-id="Jzj8AzjTxMM" data-embed-start="304">
            <span class="sm-vod-num">1</span><span class="sm-vod-name">Summit</span>
          </div>
          <a class="sm-ext" href="https://youtu.be/Jzj8AzjTxMM?t=304" target="_blank" title="Open on Youtube">
            <i class="sm-plat fa fa-youtube-play"></i>
          </a>
        </div>
        <div class="sm-vod mod-embed" data-site="youtube">
          <div class="sm-body js-stream-embed-btn" data-embed-kind="vod" data-site-id="Jzj8AzjTxMM" data-embed-start="3001">
            <span class="sm-vod-num">2</span><span class="sm-vod-name">Haven</span>
          </div>
          <a class="sm-ext" href="https://youtu.be/Jzj8AzjTxMM?t=3001" target="_blank" title="Open on Youtube">
            <i class="sm-plat fa fa-youtube-play"></i>
          </a>
        </div>
      </div>
    </div>
  </div>
</html>
"""

# Pre-redesign markup, kept working as a fallback.
LEGACY_STREAMS_VODS_HTML = """
<html>
  <div class="match-streams">
    <a class="match-streams-btn" href="https://www.twitch.tv/valorant">Valorant</a>
  </div>
  <div class="match-vods">
    <a href="https://youtu.be/abc?t=10">Ascent</a>
  </div>
</html>
"""


def test_parse_streams_vods_reads_sm_panes():
    streams, vods = _parse_streams_vods(parse_html(STREAMS_VODS_HTML))

    assert streams == [
        {"name": "VCT Americas", "url": "https://www.twitch.tv/valorant_americas"},
        {"name": "Sliggy", "url": "https://kick.com/sliggy"},
    ]
    assert vods == [
        {"name": "Summit", "url": "https://youtu.be/Jzj8AzjTxMM?t=304"},
        {"name": "Haven", "url": "https://youtu.be/Jzj8AzjTxMM?t=3001"},
    ]


def test_parse_streams_vods_falls_back_to_legacy_markup():
    streams, vods = _parse_streams_vods(parse_html(LEGACY_STREAMS_VODS_HTML))

    assert streams == [{"name": "Valorant", "url": "https://www.twitch.tv/valorant"}]
    assert vods == [{"name": "Ascent", "url": "https://youtu.be/abc?t=10"}]


def test_parse_streams_vods_empty_when_match_has_no_watch_module():
    streams, vods = _parse_streams_vods(parse_html("<html><body></body></html>"))

    assert streams == []
    assert vods == []

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


LIVE_PICKED_HTML = """
<html>
  <div class="vm-stats-game" data-game-id="g1">
    <div class="vm-stats-game-header">
      <div class="team"><div class="team-name">Alpha</div></div>
      <div class="team"><div class="team-name">Bravo</div></div>
      <div class="map">
        <div class="map-name">
          <span>Haven<span class="picked mod-2 ge-text-light">PICK</span></span>
        </div>
        <div class="map-duration">44:30</div>
      </div>
    </div>
  </div>
</html>
"""


def test_parse_maps_resolves_live_picked_badge_to_the_picking_team():
    maps = _parse_maps(parse_html(LIVE_PICKED_HTML))

    assert maps[0]["picked_by"] == "Bravo"
    assert maps[0]["map_name"] == "Haven"


def test_parse_maps_reads_legacy_picked_badge_team_name():
    maps = _parse_maps(parse_html(BASE_MATCH_HTML))

    assert [entry["picked_by"] for entry in maps] == ["Team One", "Team Two"]
    assert [entry["map_name"] for entry in maps] == ["Ascent", "Bind"]


def test_parse_maps_leaves_picked_by_empty_without_a_badge():
    maps = _parse_maps(parse_html('<div class="vm-stats-game" data-game-id="g1"></div>'))

    assert maps[0]["picked_by"] == ""


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


# Economy tab markup as vlr.gg serves it since the 2026-10 redesign (issue #194),
# captured live from /766311/?game=285688&tab=economy. One .ecm-groups block per
# map holds four table.ecm blocks: the first carries the team names plus
# Pistol/Conv./Bonus, then "On Eco", "On Half buy" and "On Full buy" tables whose
# team rows either repeat the name (th.ecm-team-th.ecm-xt) or omit it and rely on
# row order. The first .vm-stats-game block is a decoy: every map's block is on
# the page and only .mod-active belongs to the requested game.
NEW_ECONOMY_HTML = """
<html><body>
  <div class="vm-stats-game">
    <div class="ecs-top">
      <div class="ecm-groups">
        <table class="ecm ecm-open"><tbody>
          <tr><th></th><th class="ecm-step">Pistol</th></tr>
          <tr><th class="ecm-team-th" title="Decoy FC"><span class="ecm-team mod-1"><span>Decoy FC</span></span></th><td class="mod-hit"><div class="ecm-score">9<span class="ecm-of">/9</span></div></td></tr>
        </tbody></table>
      </div>
    </div>
  </div>
  <div class="vm-stats-game mod-active">
    <div class="ecs-top">
      <div class="ecm-groups"><table class="ecm ecm-open"><tbody>
        <tr><th></th><th class="ecm-step">Pistol</th><th class="ecm-step" title="Converted">Conv.</th><th>Bonus</th></tr>
        <tr><th class="ecm-team-th" title="AKV.GC"><span class="ecm-team mod-1"><img src="//owcdn.net/img/61da5f0488060.png"><span>AKV.GC</span></span></th><td class="mod-hit"><div class="ecm-score">1<span class="ecm-of">/2</span></div></td><td class="mod-hit"><div class="ecm-score">1<span class="ecm-of">/1</span></div></td><td class="mod-hit"><div class="ecm-score">0<span class="ecm-of">/1</span></div></td></tr>
        <tr><th class="ecm-team-th" title="MIBR.GC"><span class="ecm-team mod-2"><img src="//owcdn.net/img/632be7626d6d9.png"><span>MIBR.GC</span></span></th><td class="mod-hit"><div class="ecm-score">1<span class="ecm-of">/2</span></div></td><td class="mod-hit"><div class="ecm-score">1<span class="ecm-of">/1</span></div></td><td class="mod-hit"><div class="ecm-score">1<span class="ecm-of">/1</span></div></td></tr>
      </tbody></table>
      <table class="ecm"><tbody>
        <tr><th colspan="3" class="ecm-gt"><span class="ecm-gt-in"><span class="ecc-sq mod-b1"><span class="ecc-q mod-q1"></span></span><span class="ecm-gt-t"><span>On Eco</span><span class="ecm-gt-r">&lt;10k</span></span></span></th></tr>
        <tr><td class="mod-empty"><span class="ecm-dash">&ndash;</span></td><td class="mod-empty"><span class="ecm-dash">&ndash;</span></td><td class="mod-hit"><div class="ecm-score">0<span class="ecm-of">/2</span></div></td></tr>
        <tr><td class="mod-empty"><span class="ecm-dash">&ndash;</span></td><td class="mod-empty"><span class="ecm-dash">&ndash;</span></td><td class="mod-hit"><div class="ecm-score">0<span class="ecm-of">/2</span></div></td></tr>
        <tr><th class="ecm-foot"><span class="ecm-vs">vs.</span> Eco</th><th class="ecm-foot"><span class="ecm-vs">vs.</span> Half</th><th class="ecm-foot"><span class="ecm-vs">vs.</span> Full</th></tr>
      </tbody></table>
      <table class="ecm"><tbody>
        <tr><th class="ecm-xt"></th><th colspan="3" class="ecm-gt"><span class="ecm-gt-in"><span class="ecc-sq mod-b2"><span class="ecc-q mod-q2"></span></span><span class="ecm-gt-t"><span>On Half buy</span><span class="ecm-gt-r">10&ndash;18k</span></span></span></th></tr>
        <tr><th class="ecm-team-th ecm-xt" title="AKV.GC"><span class="ecm-team mod-1"><img src="//owcdn.net/img/61da5f0488060.png"><span>AKV.GC</span></span></th><td class="mod-empty"><span class="ecm-dash">&ndash;</span></td><td class="mod-empty"><span class="ecm-dash">&ndash;</span></td><td class="mod-hit"><div class="ecm-score">0<span class="ecm-of">/3</span></div></td></tr>
        <tr><th class="ecm-team-th ecm-xt" title="MIBR.GC"><span class="ecm-team mod-2"><img src="//owcdn.net/img/632be7626d6d9.png"><span>MIBR.GC</span></span></th><td class="mod-empty"><span class="ecm-dash">&ndash;</span></td><td class="mod-empty"><span class="ecm-dash">&ndash;</span></td><td class="mod-hit"><div class="ecm-score">0<span class="ecm-of">/1</span></div></td></tr>
        <tr><th class="ecm-xt"></th><th class="ecm-foot"><span class="ecm-vs">vs.</span> Eco</th><th class="ecm-foot"><span class="ecm-vs">vs.</span> Half</th><th class="ecm-foot"><span class="ecm-vs">vs.</span> Full</th></tr>
      </tbody></table>
      <table class="ecm"><tbody>
        <tr><th colspan="3" class="ecm-gt"><span class="ecm-gt-in"><span class="ecc-sq mod-b3"><span class="ecc-q mod-q3"></span></span><span class="ecm-gt-t"><span>On Full buy</span><span class="ecm-gt-r">18k+</span></span></span></th></tr>
        <tr><td class="mod-hit"><div class="ecm-score">2<span class="ecm-of">/2</span></div></td><td class="mod-hit"><div class="ecm-score">1<span class="ecm-of">/1</span></div></td><td class="mod-hit"><div class="ecm-score">4<span class="ecm-of">/8</span></div></td></tr>
        <tr><td class="mod-hit"><div class="ecm-score">2<span class="ecm-of">/2</span></div></td><td class="mod-hit"><div class="ecm-score">3<span class="ecm-of">/3</span></div></td><td class="mod-hit"><div class="ecm-score">4<span class="ecm-of">/8</span></div></td></tr>
        <tr><th class="ecm-foot"><span class="ecm-vs">vs.</span> Eco</th><th class="ecm-foot"><span class="ecm-vs">vs.</span> Half</th><th class="ecm-foot"><span class="ecm-vs">vs.</span> Full</th></tr>
      </tbody></table>
      </div>
    </div>
  </div>
</body></html>
"""


def economy_html(team_name: str) -> str:
    """Economy tab in the post-redesign .ecm markup, as the crawler sees it."""
    return f"""
    <html>
      <div class="vm-stats-game mod-active">
        <div class="ecs-top">
          <div class="ecm-groups">
            <table class="ecm ecm-open">
              <tbody>
                <tr><th></th><th class="ecm-step">Pistol</th><th class="ecm-step" title="Converted">Conv.</th><th>Bonus</th></tr>
                <tr>
                  <th class="ecm-team-th" title="{team_name}"><span class="ecm-team mod-1"><span>{team_name}</span></span></th>
                  <td class="mod-hit"><div class="ecm-score">1<span class="ecm-of">/2</span></div></td>
                  <td class="mod-hit"><div class="ecm-score">2<span class="ecm-of">/2</span></div></td>
                  <td class="mod-hit"><div class="ecm-score">1<span class="ecm-of">/3</span></div></td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </html>
    """


def economy_legacy_html(team_name: str) -> str:
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
        self.content = text.encode("utf-8")
        self.headers: dict = {}


class FakeAsyncClient:
    def __init__(self, responses: dict[str, list[FakeResponse]]):
        self._responses = responses
        self.calls: list[tuple[str, int | None]] = []

    async def get(self, url: str, timeout=None, headers=None):
        self.calls.append((url, timeout))
        return self._responses[url].pop(0)


@pytest.mark.anyio
async def test_vlr_match_detail_light_skips_the_per_game_tabs(monkeypatch):
    cache_manager.clear_all()
    client = FakeAsyncClient({"https://www.vlr.gg/556": [FakeResponse(200, BASE_MATCH_HTML)]})

    monkeypatch.setattr("api.scrapers.match_detail.crawler.get_http_client", lambda: client)

    data = await vlr_match_detail("556", light=True)
    segment = data["data"]["segments"][0]

    assert [url for url, _timeout in client.calls] == ["https://www.vlr.gg/556"]
    assert segment["economy"] == []
    assert all(entry["rows"] == [] for entry in segment["economy_by_map"])
    assert all(
        entry["kill_matrix"] == [] and entry["advanced_stats"] == []
        for entry in segment["performance"]["by_map"]
    )


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

    monkeypatch.setattr("api.scrapers.match_detail.crawler.get_http_client", lambda: client)

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
    assert segment["economy"] == [{"Team": "Team One", "Pistol": "1/2", "Conv.": "2/2", "Bonus": "1/3"}]
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
        {"game_id": "game-1", "rows": [{"Team": "Team One", "Pistol": "1/2", "Conv.": "2/2", "Bonus": "1/3"}]},
        {"game_id": "game-2", "rows": [{"Team": "Team Two", "Pistol": "1/2", "Conv.": "2/2", "Bonus": "1/3"}]},
    ]
    assert segment["maps"][0]["performance"] == {
        "kill_matrix": [{"player": "TenZ", "kills_vs": {"Opponent A": "5"}}],
        "advanced_stats": [{"player": "TenZ", "2K": "3"}],
    }
    assert segment["maps"][0]["economy"] == [{"Team": "Team One", "Pistol": "1/2", "Conv.": "2/2", "Bonus": "1/3"}]
    assert segment["maps"][1]["performance"] == {
        "kill_matrix": [{"player": "TenZ", "kills_vs": {"Opponent B": "5"}}],
        "advanced_stats": [{"player": "TenZ", "2K": "3"}],
    }
    assert segment["maps"][1]["economy"] == [{"Team": "Team Two", "Pistol": "1/2", "Conv.": "2/2", "Bonus": "1/3"}]
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

    monkeypatch.setattr("api.scrapers.match_detail.crawler.get_http_client", lambda: object())
    monkeypatch.setattr(
        "api.scrapers.match_detail.crawler.fetch_with_retries", fake_fetch_with_retries
    )
    monkeypatch.setattr("api.scrapers.match_detail.crawler.MATCH_DETAIL_TAB_FETCH_CONCURRENCY", 2)
    monkeypatch.setattr("api.scrapers.match_detail.crawler.MATCH_DETAIL_TAB_FETCH_TIMEOUT", 11)

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

    monkeypatch.setattr("api.scrapers.match_detail.crawler.get_http_client", lambda: client)

    data = await vlr_match_detail("777")
    teams = data["data"]["segments"][0]["teams"]

    assert teams[0]["id"] == "100"
    assert teams[1]["id"] == ""
    cache_manager.clear_all()


def test_parse_economy_reads_new_ecm_markup():
    """Issue #194: the economy tab moved from table.wf-table-inset.mod-econ to table.ecm."""
    rows = _parse_economy(parse_html(NEW_ECONOMY_HTML))

    assert [row["Team"] for row in rows] == ["AKV.GC", "MIBR.GC"]

    assert rows[0]["Pistol"] == "1/2"
    assert rows[0]["Conv."] == "1/1"
    assert rows[0]["Bonus"] == "0/1"
    assert rows[0]["On Half buy 10\u201318k: vs. Full"] == "0/3"
    assert rows[0]["On Full buy 18k+: vs. Eco"] == "2/2"
    assert rows[0]["On Full buy 18k+: vs. Half"] == "1/1"
    assert rows[0]["On Full buy 18k+: vs. Full"] == "4/8"
    # .mod-empty cells render a dash; "no data" is an empty string, not a glyph.
    assert rows[0]["On Eco <10k: vs. Eco"] == ""
    assert rows[0]["On Eco <10k: vs. Half"] == ""
    assert rows[0]["On Eco <10k: vs. Full"] == "0/2"
    # The "On Eco" table has no name column, so its rows follow the previous table's order.
    assert rows[1]["Team"] == "MIBR.GC"
    assert rows[1]["Bonus"] == "1/1"
    assert rows[1]["On Half buy 10\u201318k: vs. Full"] == "0/1"
    assert rows[1]["On Full buy 18k+: vs. Half"] == "3/3"
    # Only .vm-stats-game.mod-active belongs to the requested game; other map
    # blocks are on the same page and must not leak in.
    assert "Decoy FC" not in [row["Team"] for row in rows]
    assert all("9/9" not in value for row in rows for value in row.values())


def test_parse_economy_keeps_legacy_table_fallback():
    """Markup served before the redesign still parses through the old selector."""
    rows = _parse_economy(parse_html(economy_legacy_html("Team One")))

    assert rows == [{"Team": "Team One", "Pistol": "50%"}]


ROUNDS_HTML = """
<div class="vm-stats-game">
  <div class="vlr-rounds">
    <div class="vlr-rounds-row">
      <div class="vlr-rounds-row-col mod-teams"></div>
      <div class="vlr-rounds-row-col">
        <div class="rnd-sq mod-win mod-t"><img src="/img/vlr/game/round/elim.webp" alt=""></div>
        <div class="rnd-sq"></div>
      </div>
      <div class="vlr-rounds-row-col">
        <div class="rnd-sq"></div>
        <div class="rnd-sq mod-win mod-ct"><img src="/img/vlr/game/round/defuse.webp" alt=""></div>
      </div>
      <div class="vlr-rounds-row-col">
        <div class="rnd-sq"></div>
        <div class="rnd-sq"></div>
      </div>
    </div>
  </div>
</div>
"""


def test_parse_rounds_skips_unplayed_slots_and_names_the_win_type():
    game = parse_html(ROUNDS_HTML).css_first(".vm-stats-game")

    rounds = _parse_rounds(game)

    # the third column is an unplayed slot: no winner marker, no round icon
    assert rounds == [
        {"round_num": 1, "winner": "team1", "side": "t", "win_type": "elim"},
        {"round_num": 2, "winner": "team2", "side": "ct", "win_type": "defuse"},
    ]
