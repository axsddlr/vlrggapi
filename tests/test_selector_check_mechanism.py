"""Unit tests for the witnessed-selector grading mechanism.

These are deliberately offline: the mechanism must be correct *before* it is
pointed at live vlr.gg, otherwise a bug in the grader looks like a layout break.
The live assertions live in ``test_vlr_selectors.py``.
"""

from __future__ import annotations

from dataclasses import replace

from selectolax.parser import HTMLParser as SelectolaxParser

from tests.test_vlr_selectors import (
    PageCheck,
    PageData,
    _extract_match_ids,
    _extract_player_ids,
    _label_witnesses,
    grade_page,
)

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


def test_label_witnesses_uses_discovered_ids_and_falls_back():
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

    # Discovery failure falls back to the static fixture rather than nothing.
    assert _label_witnesses("match_detail", []) == ["https://www.vlr.gg/706350"]
    assert _label_witnesses("match_detail_perf", []) == [
        "https://www.vlr.gg/706350/?game=all&tab=performance"
    ]
