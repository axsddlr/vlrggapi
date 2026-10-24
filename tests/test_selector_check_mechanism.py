"""Unit tests for the witnessed-selector grading mechanism.

These are deliberately offline: the mechanism must be correct *before* it is
pointed at live vlr.gg, otherwise a bug in the grader looks like a layout break.
The live assertions live in ``test_vlr_selectors.py``.
"""

from __future__ import annotations

from dataclasses import replace

import httpx
import pytest
from selectolax.parser import HTMLParser as SelectolaxParser

import tests.test_vlr_selectors as selector_module
from tests.test_vlr_selectors import (
    PAGE_CHECKS,
    PageCheck,
    PageData,
    _extract_match_ids,
    _extract_player_ids,
    _label_witnesses,
    _no_witness_reason,
    _no_witness_result,
    _probe_indices,
    _readiness_for,
    _settled_witnesses,
    _stats_are_published,
    _unverifiable_skip_message,
    _vods_are_published,
    grade_page,
    resolve_witnesses,
)
from utils.constants import VLR_BASE_URL

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def page(url: str, html: str) -> PageData:
    return PageData(url=url, tree=SelectolaxParser(html))


# A healthy match page: anchors present, watch module present.
MATCH_WITH_WATCH = """
<html>
  <div class="match-header-super"></div>
  <div class="match-header-vs"></div>
  <div class="sm-root">
    <div class="sm-pane-streams"><div class="sm-btn"><span class="sm-name">VCT</span>
      <a class="sm-ext" href="https://twitch.tv/vct"></a></div></div>
    <div class="sm-pane-vods"><div class="sm-vod"><span class="sm-vod-name">Ascent</span>
      <a class="sm-ext" href="https://youtu.be/x"></a></div></div>
  </div>
</html>
"""

# A match with no streams/VODs at all: anchors hold, watch module absent.
MATCH_WITHOUT_WATCH = """
<html>
  <div class="match-header-super"></div>
  <div class="match-header-vs"></div>
</html>
"""

# A partial render: our conditional markup is present but the page's own
# structural anchors are not, so the page is not trustworthy as evidence.
PARTIAL_RENDER = """
<html>
  <div class="sm-root"><div class="sm-pane-streams"></div></div>
</html>
"""


def watch_check(**overrides) -> PageCheck:
    base = dict(
        label="match_detail",
        urls=[],
        anchors=[".match-header-super", ".match-header-vs"],
        required=[".sm-root", ".sm-btn", ".sm-name", ".sm-vod-name"],
        optional=[".match-header-event img"],
    )
    base.update(overrides)
    return PageCheck(**base)


# ---------------------------------------------------------------------------
# Grading: the core "absence is only evidence where presence was expected"
# ---------------------------------------------------------------------------


def test_selector_witnessed_on_one_of_several_pages_is_not_broken():
    """The #183 caveat: a conditional selector present on any witness is fine."""
    pages = [
        page("https://vlr.gg/a", MATCH_WITHOUT_WATCH),
        page("https://vlr.gg/b", MATCH_WITH_WATCH),
    ]

    result = grade_page(watch_check(), pages)

    assert result["broken_required"] == []
    assert result["failed"] is False
    assert result["witnessed"][".sm-root"] == "https://vlr.gg/b"
    assert result["witnessed_count"] == 4
    assert result["pages_usable"] == 2


def test_selector_witnessed_on_no_page_is_broken():
    """A selector that renders nowhere is still a loud, actionable failure."""
    pages = [
        page("https://vlr.gg/a", MATCH_WITHOUT_WATCH),
        page("https://vlr.gg/b", MATCH_WITHOUT_WATCH),
    ]

    result = grade_page(watch_check(), pages)

    assert result["broken_required"] == [".sm-root", ".sm-btn", ".sm-name", ".sm-vod-name"]
    assert result["unwitnessed_required"] == result["broken_required"]
    assert result["witnessed"] == {}
    assert result["failed"] is True


def test_anchor_missing_on_every_page_is_unverifiable_not_broken():
    """No structural anchor means we cannot tell "page changed" from "page is
    not this page type at all", so we refuse to assert either way.

    A wholly unreachable or restructured page type still surfaces: every
    selector ends up unwitnessed, so the check reports zero evidence rather
    than passing quietly (see the live runner, which prints it explicitly).
    """
    pages = [page("https://vlr.gg/a", "<html><div>nope</div></html>")]

    result = grade_page(watch_check(), pages)

    assert result["unverifiable"] is True
    assert result["failed"] is False
    assert result["broken_required"] == []
    assert result["witnessed"] == {}


def test_missing_anchor_on_one_page_only_does_not_fail():
    """One pruned/odd witness must not fail a page type."""
    pages = [
        page("https://vlr.gg/a", "<html><div>nope</div></html>"),
        page("https://vlr.gg/b", MATCH_WITH_WATCH),
    ]

    result = grade_page(watch_check(), pages)

    assert result["broken_required"] == []
    assert result["pages_usable"] == 1
    assert result["unusable_pages"] == ["https://vlr.gg/a"]


def test_partial_render_is_discarded_not_trusted():
    """Conditional markup alone is not evidence the page type is healthy."""
    pages = [page("https://vlr.gg/a", PARTIAL_RENDER)]

    result = grade_page(watch_check(), pages)

    assert result["unverifiable"] is True
    assert result["failed"] is False
    assert result["pages_usable"] == 0
    assert result["witnessed"] == {}


def test_no_pages_at_all_is_unverifiable_not_broken():
    result = grade_page(watch_check(), [])

    assert result["unverifiable"] is True
    assert result["broken_required"] == []
    assert result["failed"] is False


def test_optional_reported_only_when_absent_from_every_page():
    """Per-instance quirks stop generating noise."""
    pages = [
        page("https://vlr.gg/a", MATCH_WITH_WATCH),
        page("https://vlr.gg/b", MATCH_WITH_WATCH),
    ]

    # .match-header-event img is absent everywhere -> reported.
    assert grade_page(watch_check(), pages)["broken_optional"] == [".match-header-event img"]

    # Present on one witness -> not reported at all.
    with_event = MATCH_WITH_WATCH.replace(
        '<div class="match-header-super"></div>',
        '<div class="match-header-super"></div>'
        '<div class="match-header-event"><img src="logo.png"></div>',
    )
    pages_with_event = [
        page("https://vlr.gg/a", MATCH_WITH_WATCH),
        page("https://vlr.gg/b", with_event),
    ]
    assert grade_page(watch_check(), pages_with_event)["broken_optional"] == []


def test_anchor_present_on_only_some_pages_is_not_broken():
    """Anchors are a structural smell test, so one healthy page suffices."""
    check = watch_check(anchors=[".match-header-super"])
    pages = [
        page("https://vlr.gg/a", "<html><div class='match-header-vs'></div></html>"),
        page("https://vlr.gg/b", MATCH_WITH_WATCH),
    ]

    assert grade_page(check, pages)["broken_anchors"] == []


# ---------------------------------------------------------------------------
# Data-conditional selectors
# ---------------------------------------------------------------------------


def test_data_conditional_selector_never_fails_build_but_is_reported():
    """.mod-ot only exists on a match that went to overtime.

    Asserting "the selector is missing" is meaningless when the witness simply
    is not that kind of match, so it must not raise the alarm — but it is still
    reported so a human can see we have no evidence.
    """
    check = replace(
        watch_check(optional=[".mod-ot"]), data_conditional=[".mod-ot"]
    )
    pages = [
        page("https://vlr.gg/a", MATCH_WITHOUT_WATCH),
        page("https://vlr.gg/b", MATCH_WITHOUT_WATCH),
    ]

    result = grade_page(check, pages)

    assert result["broken_optional"] == [".mod-ot"]
    assert result["data_conditional_missing"] == [".mod-ot"]
    assert result["ci_optional_failures"] == 0


def test_ordinary_optional_selector_still_fails_build_when_absent():
    """The escape hatch must stay narrow: real optional markup still alerts."""
    check = watch_check(optional=[".match-header-event img"])
    pages = [page("https://vlr.gg/a", MATCH_WITHOUT_WATCH)]

    result = grade_page(check, pages)

    assert result["broken_optional"] == [".match-header-event img"]
    assert result["data_conditional_missing"] == []
    assert result["ci_optional_failures"] == 1


def test_data_conditional_selector_present_is_clean():
    """An overtime witness clears .mod-ot entirely."""
    overtime = MATCH_WITH_WATCH.replace(
        '<div class="match-header-vs"></div>',
        '<div class="match-header-vs"></div><div class="mod-ot">2</div>',
    )
    check = replace(watch_check(optional=[".mod-ot"]), data_conditional=[".mod-ot"])

    result = grade_page(check, [page("https://vlr.gg/a", overtime)])

    assert result["broken_optional"] == []
    assert result["data_conditional_missing"] == []
    assert result["ci_optional_failures"] == 0


def test_ordinary_and_data_conditional_are_separated():
    check = replace(
        watch_check(optional=[".match-header-event img", ".mod-ot"]),
        data_conditional=[".mod-ot"],
    )
    pages = [page("https://vlr.gg/a", MATCH_WITHOUT_WATCH)]

    result = grade_page(check, pages)

    assert result["broken_optional"] == [".match-header-event img", ".mod-ot"]
    assert result["data_conditional_missing"] == [".mod-ot"]
    assert result["ci_optional_failures"] == 1


# ---------------------------------------------------------------------------
# Discovery helpers
# ---------------------------------------------------------------------------


def test_extract_match_ids_reads_id_slug_links():
    tree = SelectolaxParser(
        """
        <html>
          <a href="/753450/team-a-vs-team-b">m1</a>
          <a href="/753449/other">m2</a>
          <a href="/753450/team-a-vs-team-b">dup</a>
          <a href="/matches/results">listing</a>
          <a href="https://www.vlr.gg/753448/x">absolute</a>
        </html>
        """
    )

    assert _extract_match_ids(tree) == ["753450", "753449"]


def test_extract_player_ids_reads_player_links():
    tree = SelectolaxParser(
        """
        <html>
          <a href="/player/36245/name">p1</a>
          <a href="/player/4774/">p2</a>
          <a href="/player/36245/name">dup</a>
          <a href="/player/matches/9/tenz">sibling page, not an id</a>
        </html>
        """
    )

    assert _extract_player_ids(tree) == ["36245", "4774"]


def test_label_witnesses_uses_discovered_ids():
    ids = ["753450", "753449", "753459", "753460"]

    detail = _label_witnesses("match_detail", ids)
    assert detail == [
        "https://www.vlr.gg/753450/",
        "https://www.vlr.gg/753449/",
        "https://www.vlr.gg/753459/",
    ]

    perf = _label_witnesses("match_detail_perf", ids)
    assert perf == [
        "https://www.vlr.gg/753450/?game=all&tab=performance",
        "https://www.vlr.gg/753449/?game=all&tab=performance",
    ]

    econ = _label_witnesses("match_detail_econ", ids)
    assert econ[0] == "https://www.vlr.gg/753450/?game=all&tab=economy"

    logs = _label_witnesses("match_detail_logs", ids)
    assert logs == [
        "https://www.vlr.gg/753450/?game=all&tab=logs",
        "https://www.vlr.gg/753449/?game=all&tab=logs",
    ]


def test_label_witnesses_has_no_static_fallback_when_discovery_is_empty():
    """A hardcoded stand-in is what produced #183's false alarm every day.

    ``/player/9`` still renders, but no longer renders the agent table (the data
    window is empty for an inactive player), so grading a required selector
    against it manufactures a "layout change" out of a quiet fixture. With no
    discovered candidates the honest answer is "no witnesses", not a stale URL.
    """
    assert _label_witnesses("match_detail", []) == []
    assert _label_witnesses("match_detail_perf", []) == []
    assert _label_witnesses("match_detail_econ", []) == []


def test_discovery_backed_page_types_declare_no_static_witness():
    """Guard the root cause: discovery-backed checks must not ship a fixture."""
    discovery_backed = [
        pc for pc in PAGE_CHECKS if pc.discovery
    ]
    assert {pc.label for pc in discovery_backed} == {
        "match_detail",
        "match_detail_perf",
        "match_detail_econ",
        "match_detail_logs",
        "player",
        "player_matches",
    }
    for pc in discovery_backed:
        assert pc.urls == [], f"{pc.label} still ships a hardcoded witness: {pc.urls}"


class _UnreachableClient:
    """Stands in for vlr.gg being blocked/unreachable during discovery."""

    async def get(self, url, **kwargs):  # noqa: ANN001, ANN003
        raise httpx.ConnectError("simulated discovery failure")


@pytest.mark.anyio
async def test_resolve_witnesses_yields_nothing_when_discovery_fails():
    try:
        resolved = await resolve_witnesses(_UnreachableClient())
    finally:
        selector_module._DISCOVERY_ERRORS.clear()

    for label in ("match_detail", "match_detail_perf", "player", "player_matches"):
        assert resolved[label] == [], label
    # Static page types keep their declared URLs; only discovery is affected.
    assert resolved["homepage"] == [VLR_BASE_URL]


def test_player_match_history_witnesses_the_page_the_scraper_parses():
    """``vlr_player_matches`` reads ``/player/matches/{id}/``.

    The check previously fetched ``/player/9/matches``, which vlr.gg serves as
    the *profile* page, so the match-history markup was never actually graded.
    """
    pc = next(p for p in PAGE_CHECKS if p.label == "player_matches")
    assert pc.discovery == "player_matches"
    assert "api/scrapers/players.py" in pc.source


def test_page_type_without_witnesses_is_unverifiable_not_broken():
    """No witness means no evidence, so required selectors are not "broken"."""
    result = _no_witness_result(watch_check(), [], "witness discovery returned nothing")

    assert result["unverifiable"] is True
    assert result["failed"] is False
    assert result["broken_required"] == []
    assert result["unwitnessed_required"] == []
    assert result["broken_optional"] == []
    assert result["ci_optional_failures"] == 0


def test_no_witness_reason_names_the_discovery_failure():
    """A blind check must say why, so it cannot pass silently in the report."""
    pc = watch_check(label="player", discovery="player")

    selector_module._DISCOVERY_ERRORS.pop("player", None)
    try:
        without_error = _no_witness_reason(pc)
        assert "player" in without_error
        assert "no selectors were asserted" in without_error

        selector_module._DISCOVERY_ERRORS["player"] = "ConnectError: blocked"
        with_error = _no_witness_reason(pc)
    finally:
        selector_module._DISCOVERY_ERRORS.pop("player", None)

    assert "ConnectError: blocked" in with_error


@pytest.mark.anyio
async def test_successful_discovery_clears_a_stale_error():
    """A later run must not inherit the previous run's failure message."""

    class _ListingClient:
        async def get(self, url, **kwargs):  # noqa: ANN001, ANN003
            body = (
                '<html><a href="/753450/team-a-vs-team-b">m</a></html>'
                if "/matches/results" in url
                else '<html><a href="/player/4774/name">p</a></html>'
            )

            class _Response:
                status_code = 200
                text = body

                def raise_for_status(self):
                    return None

            return _Response()

    selector_module._DISCOVERY_ERRORS["match"] = "ConnectError: stale"
    try:
        ids = await selector_module._discover(_ListingClient(), "match")
        assert ids == ["753450"]
        assert "match" not in selector_module._DISCOVERY_ERRORS
    finally:
        selector_module._DISCOVERY_ERRORS.pop("match", None)


@pytest.mark.anyio
async def test_grade_page_check_is_unverifiable_when_discovery_is_empty(monkeypatch):
    """The exact wiring that reproduced #183: no witness must not read as broken.

    Previously an empty discovery fell back to the rotted ``/player/9`` fixture,
    which no longer renders the agent table, so the suite failed a required
    selector and the daily workflow filed a fresh "layout change" comment.
    """

    async def no_witnesses(client):  # noqa: ANN001
        return {pc.label: [] for pc in selector_module.PAGE_CHECKS}

    monkeypatch.setattr(selector_module, "resolve_witnesses", no_witnesses)
    monkeypatch.setattr(selector_module, "_WITNESSES", {})

    player = next(pc for pc in selector_module.PAGE_CHECKS if pc.label == "player")
    result = await selector_module._grade_page_check(player)

    assert result["unverifiable"] is True
    assert result["failed"] is False
    assert result["broken_required"] == []
    assert result["unwitnessed_required"] == []
    assert "player" in result["unverifiable_reason"]


def test_unverifiable_page_warns_and_explains_the_skip():
    """Blindness has to be audible: pytest hides stdout for skipped tests."""
    result = _no_witness_result(
        watch_check(label="player"), [], "witness discovery returned no candidate pages"
    )

    with pytest.warns(UserWarning, match="no candidate pages"):
        message = _unverifiable_skip_message(result)

    assert "player" in message
    assert "no candidate pages" in message
    assert "0 page(s)" in message


# ---------------------------------------------------------------------------
# Page-dependent selectors (issue #190)
# ---------------------------------------------------------------------------


def test_match_detail_legacy_h2h_container_is_classified_not_escalated():
    """`.match-h2h-matches` renders on only a subset of live pages (#190).

    Measured across 12 live match pages: the parser's primary path
    ``.match-histories-item`` is present on all 12, while the legacy container
    ``.match-h2h-matches`` is present on 5 — vlr.gg is still serving the old
    container on some pages. With only three discovered witnesses, any window
    where all three happen to be new-layout pages reports it as "missing from
    every witness page", which is how #190 was filed.

    It therefore has to be classified after the ``.mod-ot`` pattern: still
    listed in ``optional`` so it shows up in reports, but in
    ``data_conditional`` so it never fails the build.
    """
    pc = next(p for p in PAGE_CHECKS if p.label == "match_detail")

    assert ".match-h2h-matches" in pc.optional, "must stay visible in reports"
    assert ".match-h2h-matches" in pc.data_conditional, (
        "page-dependent legacy markup must never be escalated"
    )
    # The path the parser actually reads stays asserted either way.
    assert ".match-histories-item" in pc.optional
    assert ".match-histories-item" not in pc.data_conditional


def test_match_detail_legacy_h2h_absence_does_not_fail_the_build():
    """The #190 witness window, graded against the real configuration.

    Only the two head-to-head selectors are in play here so a small fixture is
    enough; the classification under test comes straight from PAGE_CHECKS.
    """
    pc = next(p for p in PAGE_CHECKS if p.label == "match_detail")
    check = replace(
        pc,
        anchors=[".match-header-super"],
        required=[],
        optional=[".match-histories-item", ".match-h2h-matches"],
    )
    modern_h2h_only = MATCH_WITH_WATCH.replace(
        "</html>",
        '<a class="match-histories-item" href="/1/team-a-vs-team-b">'
        '<span class="match-histories-item-result mod-win">'
        '<span class="rf">2</span><span class="ra">1</span></span></a></html>',
    )

    result = grade_page(check, [page("https://vlr.gg/a", modern_h2h_only)])

    assert ".match-histories-item" not in result["broken_optional"]
    assert result["broken_optional"] == [".match-h2h-matches"]
    assert result["data_conditional_missing"] == [".match-h2h-matches"]
    assert result["ci_optional_failures"] == 0


# ---------------------------------------------------------------------------
# Witness readiness (issue #200)
# ---------------------------------------------------------------------------

# An unprocessed match: vlr.gg renders one placeholder inside the active stats
# game, and an empty-state block inside the VODs pane instead of any entry.
STATS_NOT_PUBLISHED = """
<html>
  <div class="vm-stats-container">
    <div class="vm-stats-game mod-active"><div class="vm-stats-empty">
      Stats from this match are not available yet</div></div>
  </div>
</html>
"""

# A processed match: the active game has numbers, while a block for a map that
# was never played still carries .vm-stats-empty. Measured live as 1 placeholder
# on a processed match versus 4 on an unprocessed one, so only the active block
# is allowed to decide readiness.
STATS_PUBLISHED = """
<html>
  <div class="vm-stats-container">
    <div class="vm-stats-game mod-active">
      <table class="wf-table-inset mod-matrix mod-normal"></table>
    </div>
    <div class="vm-stats-game"><div class="vm-stats-empty">map not played</div></div>
  </div>
</html>
"""

VODS_NOT_PUBLISHED = """
<html>
  <div class="sm-root">
    <div class="wf-label sm-tab">VODs (0)</div>
    <div class="sm-pane sm-pane-vods">
      <div class="wf-card mod-dark sm-empty">Not yet available</div>
    </div>
  </div>
</html>
"""

VODS_PUBLISHED = """
<html>
  <div class="sm-root">
    <div class="wf-label sm-tab">VODs (2)</div>
    <div class="sm-pane sm-pane-vods">
      <div class="sm-vod"><span class="sm-vod-name">Ascent</span></div>
    </div>
  </div>
</html>
"""


class _FakeClient:
    """Serves canned HTML per URL and records the requests it served."""

    def __init__(self, pages: dict[str, str]):
        self.pages = pages
        self.requests: list[str] = []

    async def get(self, url, **kwargs):  # noqa: ANN001, ANN003
        self.requests.append(url)
        body = self.pages.get(url, "<html></html>")

        class _Response:
            status_code = 200
            text = body

            def raise_for_status(self):
                return None

        return _Response()


@pytest.fixture(autouse=True)
def _clear_page_cache():
    """The fetch cache is session-scoped; keep canned pages from leaking."""
    selector_module._PAGE_CACHE.clear()
    yield
    selector_module._PAGE_CACHE.clear()


def test_stats_readiness_reads_only_the_active_game_block():
    assert _stats_are_published(SelectolaxParser(STATS_NOT_PUBLISHED)) is False
    assert _stats_are_published(SelectolaxParser(STATS_PUBLISHED)) is True


def test_stats_readiness_grades_an_unrecognised_page_rather_than_skipping_it():
    """A page without the wrapper must reach the grader and fail loudly."""
    assert _stats_are_published(SelectolaxParser("<html><div>?</div></html>")) is True


def test_vods_readiness_sees_the_empty_state_and_the_zero_count():
    assert _vods_are_published(SelectolaxParser(VODS_NOT_PUBLISHED)) is False
    assert _vods_are_published(SelectolaxParser(VODS_PUBLISHED)) is True
    # The tab count is an independent signal: it survives a redesign of the
    # entry markup that .sm-vod lives in.
    tab_says_zero = VODS_PUBLISHED.replace("VODs (2)", "VODs (0)")
    assert _vods_are_published(SelectolaxParser(tab_says_zero)) is False


def test_vods_readiness_grades_a_match_with_no_watch_module():
    """No pane and no tab is not "no data yet" — it is something to grade."""
    assert _vods_are_published(SelectolaxParser(MATCH_WITHOUT_WATCH)) is True


def test_readiness_markers_are_not_the_selectors_under_test():
    """Readiness has to stay independent, or a real break would go blind.

    Testing readiness with .sm-vod itself would invert #200: removing .sm-vod
    would make every page "not ready", discovery would yield nothing, and the
    check would skip instead of reporting that the VOD markup disappeared.
    """
    asserted = {sel for pc in PAGE_CHECKS for sel in (*pc.anchors, *pc.required)}
    assert {".vm-stats-empty", ".sm-empty"}.isdisjoint(asserted)


def test_probe_indices_always_starts_at_the_newest_page():
    assert _probe_indices(50)[0] == 0


def test_probe_indices_spreads_a_long_unprocessed_run_over_few_probes():
    """A fresh run of not-yet-populated matches must not eat the probe budget.

    The top of /matches/results is exactly that run, so probing in order would
    spend every probe on matches with no stats and then report the page type as
    unverifiable — or, before readiness existed, as broken (#200).
    """
    picks = _probe_indices(50, limit=8)

    assert len(picks) == 8
    assert picks == sorted(set(picks))
    assert picks[-1] == 49, "must reach the settled tail of the listing"
    assert max(b - a for a, b in zip(picks, picks[1:])) <= 7


def test_probe_indices_covers_everything_when_candidates_are_few():
    assert _probe_indices(3) == [0, 1, 2]
    assert _probe_indices(8) == list(range(8))
    assert _probe_indices(0) == []
    assert _probe_indices(1) == [0]


@pytest.mark.anyio
async def test_settled_witnesses_skips_matches_without_published_data():
    """#200: the newest results are not witnesses while their stats are pending."""
    ids = [f"100{i}" for i in range(10)]
    pages = {
        f"{VLR_BASE_URL}/{match_id}/?game=all&tab=economy": (
            STATS_PUBLISHED if index >= 4 else STATS_NOT_PUBLISHED
        )
        for index, match_id in enumerate(ids)
    }
    client = _FakeClient(pages)

    picked = await _settled_witnesses(client, "match_detail_econ", ids)

    assert picked == [
        f"{VLR_BASE_URL}/1004/?game=all&tab=economy",
        f"{VLR_BASE_URL}/1005/?game=all&tab=economy",
    ]
    # A probed page is graded from the same response, never fetched twice.
    assert len(client.requests) == len(set(client.requests))


@pytest.mark.anyio
async def test_settled_witnesses_reports_readiness_when_nothing_is_ready():
    """Blindness has to say why, not impersonate a layout change."""
    ids = ["2000", "2001", "2002"]
    pages = {
        f"{VLR_BASE_URL}/{match_id}/?game=all&tab=performance": STATS_NOT_PUBLISHED
        for match_id in ids
    }
    client = _FakeClient(pages)
    pc = next(p for p in PAGE_CHECKS if p.label == "match_detail_perf")

    try:
        picked = await _settled_witnesses(client, "match_detail_perf", ids)
        reason = _no_witness_reason(pc)
    finally:
        selector_module._READINESS_NOTES.pop("match_detail_perf", None)

    assert picked == []
    assert "published stats/VODs" in reason
    assert "match_detail_perf" in reason


@pytest.mark.anyio
async def test_resolve_witnesses_only_returns_pages_that_have_the_data():
    """The exact #200 wiring: no VODs and no stats means nothing to grade.

    Match 777942 was one of three discovered witnesses, all fetched before
    vlr.gg had published stats or VODs for them, so five selectors that exist on
    every settled page were reported as broken.
    """
    ids = ["3000", "3001", "3002"]
    listing = "".join(f'<a href="/{match_id}/slug">m</a>' for match_id in ids)
    pages: dict[str, str] = {f"{VLR_BASE_URL}/matches/results": f"<html>{listing}</html>"}
    for index, match_id in enumerate(ids):
        detail = VODS_PUBLISHED if index == 1 else VODS_NOT_PUBLISHED
        stats = STATS_PUBLISHED if index >= 1 else STATS_NOT_PUBLISHED
        pages[f"{VLR_BASE_URL}/{match_id}/"] = detail
        for tab in ("performance", "economy", "logs"):
            pages[f"{VLR_BASE_URL}/{match_id}/?game=all&tab={tab}"] = stats
    client = _FakeClient(pages)

    resolved = await resolve_witnesses(client)

    # The only detail page whose VODs are published.
    assert resolved["match_detail"] == [f"{VLR_BASE_URL}/3001/"]
    # Two stats witnesses, both processed; the pending one is skipped.
    assert resolved["match_detail_perf"] == [
        f"{VLR_BASE_URL}/3001/?game=all&tab=performance",
        f"{VLR_BASE_URL}/3002/?game=all&tab=performance",
    ]
    assert resolved["match_detail_econ"] == [
        f"{VLR_BASE_URL}/3001/?game=all&tab=economy",
        f"{VLR_BASE_URL}/3002/?game=all&tab=economy",
    ]


@pytest.mark.anyio
async def test_readiness_note_is_cleared_once_a_witness_is_found():
    """A later healthy run must not keep reporting an earlier empty window."""
    ids = ["4000"]
    pending = _FakeClient({f"{VLR_BASE_URL}/{mid}/?game=all&tab=economy": STATS_NOT_PUBLISHED
                          for mid in ids})
    settled = _FakeClient({f"{VLR_BASE_URL}/{mid}/?game=all&tab=economy": STATS_PUBLISHED
                          for mid in ids})

    try:
        await _settled_witnesses(pending, "match_detail_econ", ids)
        assert "match_detail_econ" in selector_module._READINESS_NOTES

        # A later run is a new process: no bytes cached from the empty window.
        selector_module._PAGE_CACHE.clear()
        picked = await _settled_witnesses(settled, "match_detail_econ", ids)
        assert picked == [f"{VLR_BASE_URL}/4000/?game=all&tab=economy"]
        assert "match_detail_econ" not in selector_module._READINESS_NOTES
    finally:
        selector_module._READINESS_NOTES.pop("match_detail_econ", None)

