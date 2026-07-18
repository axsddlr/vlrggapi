import logging
import re

import pytest
from fastapi import HTTPException
from selectolax.parser import HTMLParser

import api.scrapers.stats as stats_mod
from api.scrapers.stats import (
    _build_column_map,
    _parse_stats_row,
    _selected_region,
    vlr_stats,
)
from utils.cache_manager import cache_manager
from utils.error_handling import validate_region

# ---------------------------------------------------------------------------
# Legacy (pre-revamp) 21-ish column markup: NO data-col attributes, org lives in
# .stats-player-country. Cells are laid out at the historical positional indices
# (player td[0], agents td[1], then rnd td[2], rating td[3], acs td[4] ...).
# ---------------------------------------------------------------------------
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

# The full ordered list of data-col attributes vlr.gg now emits (after the player
# column, which is unlabelled). 22 keyed columns == 23 <th> including player.
NEW_DATA_COLS = [
    "agents", "maps", "rnd", "rating2", "acs", "kd", "kast", "adr", "kpr", "apr",
    "fkfd", "fbpr", "fdpr", "hsp", "clp", "cl", "kmax", "k", "d", "a", "fk", "fd",
]

# Realistic per-column cell text for one row.
NEW_ROW_VALUES = {
    "maps": "11", "rnd": "228", "rating2": "1.37", "acs": "247", "kd": "1.15",
    "kast": "73%", "adr": "155.0", "kpr": "0.82", "apr": "0.30", "fkfd": "+5",
    "fbpr": "0.14", "fdpr": "0.10", "hsp": "28%", "clp": "20%", "cl": "7/35",
    "kmax": "30", "k": "180", "d": "150", "a": "60", "fk": "25", "fd": "20",
}

STATS_REGION_OPTIONS = ["all", "americas", "emea", "pacific", "china", "intl"]


def _thead(data_cols=NEW_DATA_COLS, drop=()):
    """Build a <thead> with a data-col on each column except those in ``drop``."""
    ths = ['<th class="mod-player">Player</th>']
    for col in data_cols:
        if col in drop:
            ths.append(f"<th>{col}</th>")  # present but unkeyed
        else:
            ths.append(f'<th data-col="{col}">{col}</th>')
    return "<thead><tr>" + "".join(ths) + "</tr></thead>"


def _new_row(values=None, org="NRG", player="brawk", org_class="st-pl-country"):
    """Build a <tr> whose <td> order matches NEW_DATA_COLS (player first)."""
    values = values if values is not None else NEW_ROW_VALUES
    tds = [
        f'<td class="mod-player"><a><div class="text-of">{player}</div>'
        f'<div class="{org_class}">{org}</div></a></td>'
    ]
    for col in NEW_DATA_COLS:
        if col == "agents":
            tds.append('<td class="mod-agents"><img src="/img/vlr/game/agents/jett.png"></td>')
        else:
            tds.append(f"<td>{values.get(col, '')}</td>")
    return "<tr>" + "".join(tds) + "</tr>"


def _region_select(selected="americas"):
    opts = []
    for r in STATS_REGION_OPTIONS:
        sel = " selected" if r == selected else ""
        opts.append(f'<option value="{r}"{sel}>{r}</option>')
    return '<select name="region">' + "".join(opts) + "</select>"


def make_stats_page(selected="americas", rows=None, thead=None, include_select=True):
    """Assemble a full new-markup /stats page for the vlr_stats flow tests."""
    if thead is None:
        thead = _thead()
    if rows is None:
        rows = _new_row()
    select_html = _region_select(selected) if include_select else ""
    return (
        f"<html><body>{select_html}"
        f"<table>{thead}<tbody>{rows}</tbody></table></body></html>"
    )


class FakeResponse:
    def __init__(self, status_code: int, text: str):
        self.status_code = status_code
        self.text = text
        self.content = text.encode("utf-8")
        self.headers: dict = {}


def _region_of(url: str) -> str | None:
    """Extract the region= query value from a /stats URL. None => a prime GET."""
    match = re.search(r"[?&]region=([^&]+)", url)
    return match.group(1) if match else None


class FakeFetch:
    """Stand-in for fetch_with_retries: routes prime vs data requests by URL.

    A URL with no ``region=`` is the priming GET. Data URLs get a page whose
    selected region echoes the requested one, unless ``selected_override`` forces a
    different (mismatched) region to simulate D4 poisoning.
    """

    def __init__(self):
        self.calls: list[str] = []
        self.prime_status = 200
        self.selected_override: str | None = None
        self.page_for_region = None  # optional callable(region) -> html

    async def __call__(self, url, *, client=None, **kwargs):
        self.calls.append(url)
        region = _region_of(url)
        if region is None:
            return FakeResponse(self.prime_status, "<html><body>primed</body></html>")
        if self.page_for_region is not None:
            return FakeResponse(200, self.page_for_region(region))
        selected = self.selected_override or region
        return FakeResponse(200, make_stats_page(selected=selected))


@pytest.fixture(autouse=True)
def _reset_stats_state():
    """Each test starts cold: empty cache and an unprimed session."""
    cache_manager.clear_all()
    stats_mod._primed = False
    yield
    cache_manager.clear_all()
    stats_mod._primed = False


def _install_fake_fetch(monkeypatch) -> FakeFetch:
    fetch = FakeFetch()
    monkeypatch.setattr("api.scrapers.stats.fetch_with_retries", fetch)
    monkeypatch.setattr("api.scrapers.stats.get_http_client", lambda: object())
    return fetch


# ---------------------------------------------------------------------------
# Row / column-map parsing
# ---------------------------------------------------------------------------

def test_parse_stats_row_legacy_positional_fallback():
    """Old 21-column markup (no data-col, .stats-player-country) still parses."""
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
        "clutch_attempts": "9/57",
    }


def test_parse_stats_row_new_markup_header_keyed():
    """23-column markup: cells read by data-col key, immune to inserted columns."""
    tree = HTMLParser(make_stats_page(include_select=False))
    col_map = _build_column_map(tree)
    row = tree.css_first("tbody tr")

    parsed = _parse_stats_row(row, col_map)

    assert parsed["rounds_played"] == "228"
    assert parsed["rating"] == "1.37"
    assert parsed["average_combat_score"] == "247"
    assert parsed["org"] == "NRG"
    # clutch_attempts must come from the ``cl`` key, not a positional index.
    assert parsed["clutch_attempts"] == "7/35"
    # the inserted ``maps`` column must NOT leak into rounds_played.
    assert parsed["rounds_played"] != "11"


def test_build_column_map_keys_align_with_td_positions():
    tree = HTMLParser(make_stats_page(include_select=False))
    col_map = _build_column_map(tree)

    # player is td[0] (unkeyed), agents td[1], maps td[2], rnd td[3] ...
    assert col_map["agents"] == 1
    assert col_map["maps"] == 2
    assert col_map["rnd"] == 3
    assert col_map["rating2"] == 4
    assert col_map["acs"] == 5
    assert col_map["cl"] == 16


def test_build_column_map_none_for_legacy_markup():
    tree = HTMLParser(STATS_HTML)
    assert _build_column_map(tree) is None


# ---------------------------------------------------------------------------
# Org selector fallback (D2)
# ---------------------------------------------------------------------------

def test_org_selector_prefers_new_class():
    html = (
        '<table><tbody><tr><td class="mod-player"><a>'
        '<div class="text-of">p</div>'
        '<div class="st-pl-country">NRG</div>'
        '<div class="stats-player-country">OLD</div>'
        '</a></td></tr></tbody></table>'
    )
    row = HTMLParser(html).css_first("tbody tr")
    assert _parse_stats_row(row)["org"] == "NRG"


def test_org_selector_falls_back_to_old_class():
    html = (
        '<table><tbody><tr><td class="mod-player"><a>'
        '<div class="text-of">p</div>'
        '<div class="stats-player-country">VIT</div>'
        '</a></td></tr></tbody></table>'
    )
    row = HTMLParser(html).css_first("tbody tr")
    assert _parse_stats_row(row)["org"] == "VIT"


def test_org_selector_missing_defaults_na():
    html = (
        '<table><tbody><tr><td class="mod-player"><a>'
        '<div class="text-of">p</div></a></td></tr></tbody></table>'
    )
    row = HTMLParser(html).css_first("tbody tr")
    assert _parse_stats_row(row)["org"] == "N/A"


# ---------------------------------------------------------------------------
# Full vlr_stats flow
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_vlr_stats_new_markup_end_to_end(monkeypatch):
    fetch = _install_fake_fetch(monkeypatch)

    data = await vlr_stats("americas", "60")

    seg = data["data"]["segments"]
    assert len(seg) == 1
    assert seg[0]["rounds_played"] == "228"
    assert seg[0]["rating"] == "1.37"
    assert seg[0]["average_combat_score"] == "247"
    assert seg[0]["org"] == "NRG"
    assert seg[0]["clutch_attempts"] == "7/35"
    # output key set is unchanged from upstream's contract
    assert set(seg[0].keys()) == {
        "player", "org", "agents", "rounds_played", "rating",
        "average_combat_score", "kill_deaths", "kill_assists_survived_traded",
        "average_damage_per_round", "kills_per_round", "assists_per_round",
        "first_kills_per_round", "first_deaths_per_round", "headshot_percentage",
        "clutch_success_percentage", "clutch_attempts",
    }
    # prime fired first, exactly once, before the data fetch
    assert _region_of(fetch.calls[0]) is None
    assert "region=americas" in fetch.calls[1]


@pytest.mark.anyio
async def test_vlr_stats_legacy_markup_logs_warning(monkeypatch, caplog):
    fetch = _install_fake_fetch(monkeypatch)
    # legacy page: positional cells, no data-col, no region select (skip validation)
    legacy_thead = "<thead><tr><th>Player</th><th>Agents</th><th>Rnd</th></tr></thead>"
    legacy_tbody = HTMLParser(STATS_HTML).css_first("tbody").html
    legacy_page = f"<html><body><table>{legacy_thead}{legacy_tbody}</table></body></html>"
    fetch.page_for_region = lambda region: legacy_page

    with caplog.at_level(logging.WARNING, logger="api.scrapers.stats"):
        data = await vlr_stats("americas", "60")

    seg = data["data"]["segments"]
    assert seg[0]["rounds_played"] == "442"
    assert seg[0]["rating"] == "1.36"
    assert seg[0]["org"] == "Team Liquid"
    assert any("no data-col" in rec.message for rec in caplog.records)


@pytest.mark.anyio
async def test_vlr_stats_missing_required_key_raises(monkeypatch):
    fetch = _install_fake_fetch(monkeypatch)
    # data-col present on most columns, but rating2 is unkeyed -> must fail closed
    page = make_stats_page(thead=_thead(drop=("rating2",)))
    fetch.page_for_region = lambda region: page

    with pytest.raises(HTTPException) as exc:
        await vlr_stats("americas", "60")
    assert exc.value.status_code == 502
    # nothing partial-parsed reached the cache
    assert cache_manager.get(stats_mod.CACHE_TTL_STATS, "stats", "americas", "60") is None


@pytest.mark.anyio
async def test_priming_fires_once_across_two_region_calls(monkeypatch):
    fetch = _install_fake_fetch(monkeypatch)

    await vlr_stats("americas", "60")
    await vlr_stats("emea", "60")

    prime_calls = [c for c in fetch.calls if _region_of(c) is None]
    assert len(prime_calls) == 1
    # order: prime, then the two data fetches
    assert _region_of(fetch.calls[0]) is None
    assert "region=americas" in fetch.calls[1]
    assert "region=emea" in fetch.calls[2]


@pytest.mark.anyio
async def test_failing_prime_raises_and_caches_nothing(monkeypatch):
    fetch = _install_fake_fetch(monkeypatch)
    fetch.prime_status = 503

    with pytest.raises(HTTPException) as exc:
        await vlr_stats("americas", "60")
    assert exc.value.status_code == 503
    # only the prime was attempted; no data fetch, nothing cached
    assert all(_region_of(c) is None for c in fetch.calls)
    assert cache_manager.get(stats_mod.CACHE_TTL_STATS, "stats", "americas", "60") is None
    assert stats_mod._primed is False


@pytest.mark.anyio
async def test_region_mismatch_retries_then_raises(monkeypatch):
    fetch = _install_fake_fetch(monkeypatch)
    fetch.selected_override = "all"  # page always claims the global list

    with pytest.raises(HTTPException) as exc:
        await vlr_stats("americas", "60")
    assert exc.value.status_code == 502

    # one prime, one data fetch, one FORCED re-prime, one refetch
    prime_calls = [c for c in fetch.calls if _region_of(c) is None]
    data_calls = [c for c in fetch.calls if _region_of(c) is not None]
    assert len(prime_calls) == 2
    assert len(data_calls) == 2
    # the mismatched response was never cached
    assert cache_manager.get(stats_mod.CACHE_TTL_STATS, "stats", "americas", "60") is None


@pytest.mark.anyio
async def test_region_mismatch_recovers_on_reprime(monkeypatch):
    """A mismatch on the first fetch that clears after a re-prime succeeds."""
    fetch = _install_fake_fetch(monkeypatch)
    state = {"first": True}

    def builder(region):
        if state["first"]:
            state["first"] = False
            return make_stats_page(selected="all")  # cold/global on first data fetch
        return make_stats_page(selected=region)

    fetch.page_for_region = builder

    data = await vlr_stats("americas", "60")
    assert data["data"]["segments"][0]["org"] == "NRG"


@pytest.mark.anyio
async def test_alias_normalizes_before_cache_key(monkeypatch):
    fetch = _install_fake_fetch(monkeypatch)

    await vlr_stats("na", "60")

    # cache entry is keyed on the canonical region, not the alias
    assert cache_manager.get(stats_mod.CACHE_TTL_STATS, "stats", "americas", "60", "all") is not None
    assert cache_manager.get(stats_mod.CACHE_TTL_STATS, "stats", "na", "60", "all") is None
    # the fetched URL carries the canonical region
    data_calls = [c for c in fetch.calls if _region_of(c) is not None]
    assert "region=americas" in data_calls[0]

    # a follow-up canonical request is served from the same cache entry (no refetch)
    before = len(fetch.calls)
    await vlr_stats("americas", "60")
    assert len(fetch.calls) == before


@pytest.mark.anyio
async def test_empty_region_returns_no_error_no_retry(monkeypatch):
    fetch = _install_fake_fetch(monkeypatch)
    # correct selected region, zero rows
    fetch.page_for_region = lambda region: make_stats_page(selected=region, rows="")

    data = await vlr_stats("pacific", "60")

    assert data["data"]["segments"] == []
    assert data["data"]["status"] == 200
    # exactly one prime + one data fetch, no retry
    assert len(fetch.calls) == 2


@pytest.mark.anyio
async def test_tableless_empty_page_returns_empty_without_fallback_warning(monkeypatch, caplog):
    """vlr.gg renders NO table at all for a zero-row result (e.g. sparse tier/span
    windows). That is an empty result set, not legacy markup — no fallback warning."""
    fetch = _install_fake_fetch(monkeypatch)
    fetch.page_for_region = lambda region: (
        f"<html><body>{_region_select(selected=region)}</body></html>"
    )

    with caplog.at_level(logging.WARNING, logger="api.scrapers.stats"):
        data = await vlr_stats("americas", "60")

    assert data["data"]["segments"] == []
    assert not any("no data-col" in rec.message for rec in caplog.records)


# ---------------------------------------------------------------------------
# Region vocabulary
# ---------------------------------------------------------------------------

def test_selected_region_reads_selected_option():
    tree = HTMLParser(make_stats_page(selected="emea"))
    assert _selected_region(tree) == "emea"


def test_selected_region_none_when_absent():
    tree = HTMLParser("<html><body><table></table></body></html>")
    assert _selected_region(tree) is None


@pytest.mark.parametrize("value", ["americas", "all", "intl"])
def test_validate_stats_region_accepts_canonical(value):
    from utils.error_handling import validate_stats_region
    assert validate_stats_region(value) == value


@pytest.mark.parametrize(
    "alias,canonical",
    [("na", "americas"), ("br", "americas"), ("eu", "emea"),
     ("ap", "pacific"), ("kr", "pacific"), ("jp", "pacific"),
     ("oce", "pacific"), ("cn", "china")],
)
def test_validate_stats_region_normalizes_aliases(alias, canonical):
    from utils.error_handling import validate_stats_region
    assert validate_stats_region(alias) == canonical


@pytest.mark.parametrize("value", ["la", "la-s", "la-n", "mn", "gc", "col", "xyz"])
def test_validate_stats_region_rejects_unknown(value):
    from utils.error_handling import validate_stats_region
    with pytest.raises(HTTPException) as exc:
        validate_stats_region(value)
    assert exc.value.status_code == 400


def test_rankings_region_americas_still_400():
    """The shared /rankings region dict is untouched: 'americas' must still 400."""
    with pytest.raises(HTTPException) as exc:
        validate_region("americas")
    assert exc.value.status_code == 400
