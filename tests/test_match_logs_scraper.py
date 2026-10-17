"""Tests for the match logs (2D replay) scraper — vlr.gg 'logs' tab."""
import json

import pytest

from api.scrapers.match_logs import vlr_match_logs
from utils.cache_manager import cache_manager

# Trimmed from https://www.vlr.gg/766311/?game=285688&tab=logs (2026-10).
# Each round embeds its replay as JSON in div.lg-map[data-map]; the DOM adds the
# round strip (end reason), the score band, the per-player economy rows and the
# kill/spike feed whose data-ev index lines up with the JSON event order.
ROUND_ONE = {
    "atk": 1,
    "players": {
        "101": [1, "chamber", "Tastyy"],
        "102": [1, "sage", "Ivy"],
        "103": [2, "brimstone", "mizzy"],
        "104": [2, "yoru", "bstrdd"],
    },
    "events": [
        {
            "t": "0:07", "type": "kill", "by": 101, "vid": 104, "victim": "bstrdd", "team": 2,
            "pos": [562.3, 584.8], "from": [530.7, 707.5],
            "locs": [[103, 967.4, 418.8, 112], [101, 530.7, 707.5, 285], [102, 170.7, 663.5, 255]],
        },
        {
            "t": "0:20", "type": "plant", "by": 102, "pos": [128.6, 341.4], "team": 1,
            "locs": [[102, 128.6, 341.4, 40], [103, 677.0, 338.4, 176]],
        },
        {
            "t": "0:42", "type": "kill", "by": 103, "vid": 102, "victim": "Ivy", "team": 1,
            "pos": [224.2, 339.1], "from": [172.1, 394.4],
            "locs": [[103, 172.1, 394.4, 313], [101, 153.4, 550.3, 263]],
        },
    ],
    "boom": None,
}

ROUND_TWO = {
    "atk": 2,
    "players": {"101": [1, "chamber", "Tastyy"], "104": [2, "yoru", "bstrdd"]},
    "events": [{"t": "1:35", "type": "defuse", "by": 104, "pos": [864.0, 468.8], "team": 2,
                "locs": [[104, 864.0, 468.8, 4]]}],
    "boom": None,
}


def _mir_row(name: str, tag: str, agent: str, left: int, spent: int, armor: str, gun: str) -> str:
    armor_html = (
        '<span class="lg-noarmor" title="No armor"></span>'
        if armor == "none"
        else f'<img class="lg-kit-shield" title="{armor} armor">'
    )
    return f"""
    <div class="lg-mir-row">
      <img class="lg-agent" src="/img/vlr/game/agents/{agent}.png" title="{name} ({agent.title()})">
      <span class="lg-mir-who"><span class="lg-mir-name">{name}</span><span class="lg-mir-tag">{tag}</span></span>
      <span class="lg-mir-creds"><img class="lg-kit-cred" src="/img/vlr/game/misc/creds.png">
        <span class="lg-mir-vals">
          <span class="lg-mir-left" title="Credits left after the buy phase">{left}</span>
          <span class="lg-kit-spent" title="Spent in the buy phase">&minus;{spent}</span>
        </span>
      </span>
      <span class="lg-kit-armor">{armor_html}</span>
      <span class="lg-mir-gun"><img class="lg-kit-gun" title="{gun}"></span>
    </div>"""


LOGS_TAB_HTML = f"""
<html><body>
<div class="vm-stats mod-tab-logs"><div class="vm-stats-container">
  <div class="vm-stats-game mod-active" data-game-id="285688">
    <div class="lg">
      <div class="vlr-rounds-scroll lg-strip"><div class="vlr-rounds-row">
        <div class="vlr-rounds-row-col mod-teams"><div class="vlr-rounds-head"></div></div>
        <div class="vlr-rounds-row-col js-lg-round mod-active mod-won-atk" data-round="1"
             title="Round 1: AKV.GC 1 &ndash; 0 MIBR.GC, Elimination"></div>
        <div class="vlr-rounds-row-col js-lg-round mod-won-def" data-round="2"
             title="Round 2: AKV.GC 2 &ndash; 0 MIBR.GC, Spike defused"></div>
      </div></div>
      <div class="lg-rounds">
        <div class="lg-round mod-active" data-round="1">
          <div class="lg-bar"><div class="lg-band mod-atk mod-win-1">
            <span class="lg-band-team mod-t1 mod-atk"><span class="lg-band-score">1</span><span class="lg-band-name" title="Akave Esports GC">Akave Esports GC</span><span class="lg-band-tag">AKV.GC</span></span>
            <div class="lg-band-mid"><span class="lg-band-round">Round <span class="lg-band-num">1</span><span class="lg-band-of">/2</span></span></div>
            <span class="lg-band-team mod-t2 mod-def"><span class="lg-band-score">0</span><span class="lg-band-name" title="MIBR GC">MIBR GC</span><span class="lg-band-tag">MIBR.GC</span></span>
          </div></div>
          <div class="lg-body">
            <div class="lg-mir">
              <div class="lg-mir-team mod-atk">
                {_mir_row("Tastyy", "AKV.GC", "chamber", 50, 750, "none", "Ghost")}
                {_mir_row("Ivy", "AKV.GC", "sage", 100, 700, "heavy", "Classic")}
              </div>
              <div class="lg-mir-team mod-right mod-def">
                {_mir_row("mizzy", "MIBR.GC", "brimstone", 0, 800, "none", "Ghost")}
                {_mir_row("bstrdd", "MIBR.GC", "yoru", 200, 600, "light", "Sheriff")}
              </div>
            </div>
            <div class="lg-main mod-side">
              <div class="lg-map" data-at="0" data-map='{json.dumps(ROUND_ONE)}'>
                <div class="lg-map-view"><svg class="lg-map-svg" viewBox="0 0 1024 1024">
                  <image class="lg-map-art mod-dark" href="/img/vlr/game/minimap/dark/abyss.png?v=1">
                  <g class="js-lg-map-layer"></g>
                </svg></div>
              </div>
              <div class="lg-feed">
                <div class="lg-row mod-kill" data-ev="0">
                  <span class="lg-clock">0:07</span>
                  <div class="lg-side"><span class="lg-player mod-atk"><span class="lg-player-who"><span class="lg-player-name" title="Tastyy">Tastyy</span></span><img class="lg-agent" title="Chamber"></span></div>
                  <span class="lg-source" title="Headhunter"><img src="/img/vlr/game/weapons/trim/headhunter.png"></span>
                  <div class="lg-side mod-right"><span class="lg-player mod-def mod-victim"><img class="lg-agent" title="Yoru"><span class="lg-player-who"><span class="lg-player-name" title="bstrdd">bstrdd</span></span></span></div>
                </div>
                <div class="lg-row mod-spike" data-ev="1">
                  <span class="lg-clock">0:20</span>
                  <span class="lg-spike-what">Spike planted&nbsp;<span class="lg-site">B</span> by</span>
                  <div class="lg-side"><span class="lg-player mod-atk"><span class="lg-player-who"><span class="lg-player-name" title="Ivy">Ivy</span></span></span></div>
                </div>
                <div class="lg-row mod-kill" data-ev="2">
                  <span class="lg-clock">0:42</span>
                  <div class="lg-side"><span class="lg-player mod-def"><span class="lg-player-who"><span class="lg-player-name" title="mizzy">mizzy</span></span><img class="lg-agent" title="Brimstone"></span></div>
                  <span class="lg-source" title="Vandal"><img src="/img/vlr/game/weapons/trim/vandal.png"></span>
                  <div class="lg-side mod-right"><span class="lg-player mod-def mod-victim"><img class="lg-agent" title="Sage"><span class="lg-player-who"><span class="lg-player-name" title="Ivy">Ivy</span></span></span></div>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div class="lg-round" data-round="2">
          <div class="lg-bar"><div class="lg-band mod-atk mod-win-1">
            <span class="lg-band-team mod-t1 mod-atk"><span class="lg-band-score">2</span><span class="lg-band-name" title="Akave Esports GC">Akave Esports GC</span><span class="lg-band-tag">AKV.GC</span></span>
            <div class="lg-band-mid"><span class="lg-band-round">Round <span class="lg-band-num">2</span><span class="lg-band-of">/2</span></span></div>
            <span class="lg-band-team mod-t2 mod-def"><span class="lg-band-score">0</span><span class="lg-band-name" title="MIBR GC">MIBR GC</span><span class="lg-band-tag">MIBR.GC</span></span>
          </div></div>
          <div class="lg-body">
            <div class="lg-mir"></div>
            <div class="lg-main mod-side">
              <div class="lg-map" data-at="0" data-map='{json.dumps(ROUND_TWO)}'>
                <div class="lg-map-view"><svg class="lg-map-svg" viewBox="0 0 1024 1024">
                  <image class="lg-map-art mod-dark" href="/img/vlr/game/minimap/dark/abyss.png?v=1">
                  <g class="js-lg-map-layer"></g>
                </svg></div>
              </div>
              <div class="lg-feed"></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</div></div>
</body></html>
"""

# No replay markup: a match whose logs tab has no data for the requested game.
LOGS_TAB_EMPTY_HTML = """
<html><body><div class="vm-stats mod-tab-logs"><div class="vm-stats-container">
  <div class="vm-stats-game mod-active" data-game-id="285690"></div>
</div></div></body></html>
"""

BASE_PAGE_HTML = """
<html><body>
<div class="vm-stats-gamesnav">
  <a class="vm-stats-gamesnav-item mod-active mod-all" data-game-id="all">All Maps</a>
  <a class="vm-stats-gamesnav-item" data-game-id="285688" data-disabled="0">1 Abyss</a>
  <a class="vm-stats-gamesnav-item" data-game-id="285689" data-disabled="0">2 Haven</a>
  <a class="vm-stats-gamesnav-item" data-game-id="285690" data-disabled="1">3 Ascent</a>
</div>
</body></html>
"""


class FakeResponse:
    def __init__(self, status_code: int, text: str):
        self.status_code = status_code
        self.text = text
        self.content = text.encode("utf-8")
        self.headers: dict = {}


def _patch_fetch(monkeypatch, responses: dict[str, FakeResponse]):
    calls: list[str] = []

    async def fake_fetch(url, *, client=None, timeout=None, **kwargs):
        calls.append(url)
        if url not in responses:
            raise AssertionError(f"unexpected fetch: {url}")
        return responses[url]

    monkeypatch.setattr("api.scrapers.match_logs.fetch_with_retries", fake_fetch)
    return calls


@pytest.mark.anyio
async def test_vlr_match_logs_parses_rounds(monkeypatch):
    cache_manager.clear_all()
    _patch_fetch(
        monkeypatch,
        {"https://www.vlr.gg/766311/?game=285688&tab=logs": FakeResponse(200, LOGS_TAB_HTML)},
    )

    data = await vlr_match_logs("766311", "285688")
    segment = data["data"]["segments"][0]

    assert data["data"]["status"] == 200
    assert segment["match_id"] == "766311"
    assert segment["game_id"] == "285688"
    assert segment["map"] == "abyss"
    assert segment["teams"] == {
        "team1": {"name": "Akave Esports GC", "tag": "AKV.GC"},
        "team2": {"name": "MIBR GC", "tag": "MIBR.GC"},
    }
    assert [r["round"] for r in segment["rounds"]] == [1, 2]

    first = segment["rounds"][0]
    assert first["score"] == {"team1": 1, "team2": 0}
    assert first["winner"] == "team1"
    assert first["attacking_side"] == "team1"
    assert first["end_reason"] == "Elimination"

    assert first["economy"][0] == {
        "player": "Tastyy", "team": 1, "agent": "chamber",
        "credits": 50, "spent": 750, "weapon": "Ghost", "armor": "none",
    }
    assert first["economy"][1]["armor"] == "heavy"
    assert first["economy"][3] == {
        "player": "bstrdd", "team": 2, "agent": "yoru",
        "credits": 200, "spent": 600, "weapon": "Sheriff", "armor": "light",
    }

    kill, plant, second_kill = first["events"]
    assert kill == {
        "t": "0:07", "type": "kill", "player": "Tastyy", "team": 1,
        "victim": "bstrdd", "victim_team": 2, "source": "Headhunter",
        "pos": {"x": 562.3, "y": 584.8}, "from": {"x": 530.7, "y": 707.5},
        "positions": [
            {"player": "mizzy", "team": 2, "x": 967.4, "y": 418.8, "hp": 112},
            {"player": "Tastyy", "team": 1, "x": 530.7, "y": 707.5, "hp": 285},
            {"player": "Ivy", "team": 1, "x": 170.7, "y": 663.5, "hp": 255},
        ],
    }
    assert plant["type"] == "plant"
    assert plant["player"] == "Ivy"
    assert plant["team"] == 1
    assert plant["site"] == "B"
    assert "source" not in plant
    assert second_kill["source"] == "Vandal"
    assert second_kill["victim_team"] == 1

    second = segment["rounds"][1]
    assert second["end_reason"] == "Spike defused"
    assert second["attacking_side"] == "team1"
    assert second["economy"] == []
    assert second["events"][0]["type"] == "defuse"
    assert second["events"][0]["player"] == "bstrdd"
    cache_manager.clear_all()


@pytest.mark.anyio
async def test_vlr_match_logs_defaults_to_first_played_game(monkeypatch):
    cache_manager.clear_all()
    calls = _patch_fetch(
        monkeypatch,
        {
            "https://www.vlr.gg/766311/": FakeResponse(200, BASE_PAGE_HTML),
            "https://www.vlr.gg/766311/?game=285688&tab=logs": FakeResponse(200, LOGS_TAB_HTML),
        },
    )

    data = await vlr_match_logs("766311")

    assert data["data"]["segments"][0]["game_id"] == "285688"
    assert calls == [
        "https://www.vlr.gg/766311/",
        "https://www.vlr.gg/766311/?game=285688&tab=logs",
    ]
    cache_manager.clear_all()


@pytest.mark.anyio
async def test_vlr_match_logs_returns_no_rounds_when_game_has_no_replay(monkeypatch):
    cache_manager.clear_all()
    _patch_fetch(
        monkeypatch,
        {"https://www.vlr.gg/766311/?game=285690&tab=logs": FakeResponse(200, LOGS_TAB_EMPTY_HTML)},
    )

    data = await vlr_match_logs("766311", "285690")

    segment = data["data"]["segments"][0]
    assert segment["rounds"] == []
    assert segment["game_id"] == "285690"
    cache_manager.clear_all()
