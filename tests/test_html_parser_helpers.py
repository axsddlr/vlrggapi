"""Unit tests for the shared HTML parsing helpers."""
from utils.html_parsers import find_elements_by_selectors, pad_to_length, parse_html

# ---------------------------------------------------------------------------
# pad_to_length
# ---------------------------------------------------------------------------

def test_pad_to_length_pads_up_to_the_requested_length():
    teams = [{"name": "A"}]

    pad_to_length(teams, 2, lambda: {"name": "TBD"})

    assert teams == [{"name": "A"}, {"name": "TBD"}]


def test_pad_to_length_is_a_noop_at_the_exact_length():
    teams = ["A", "B"]

    pad_to_length(teams, 2, lambda: "TBD")

    assert teams == ["A", "B"]


def test_pad_to_length_does_not_truncate_a_longer_list():
    teams = ["A", "B", "C"]

    pad_to_length(teams, 2, lambda: "TBD")

    assert teams == ["A", "B", "C"]


def test_pad_to_length_builds_a_fresh_value_for_each_entry():
    teams = []

    pad_to_length(teams, 2, lambda: {"name": "TBD"})
    teams[0]["name"] = "mutated"

    assert teams[1] == {"name": "TBD"}


def test_pad_to_length_only_fills_the_gap():
    calls = []

    def factory():
        calls.append(1)
        return "TBD"

    teams = ["A"]

    pad_to_length(teams, 3, factory)

    assert teams == ["A", "TBD", "TBD"]
    assert len(calls) == 2


# ---------------------------------------------------------------------------
# find_elements_by_selectors
# ---------------------------------------------------------------------------

def test_find_elements_by_selectors_returns_the_first_matching_selector():
    html = parse_html("<div class='b'><span>hit</span></div>")

    found = find_elements_by_selectors(html, [".a", ".b", "body"])

    assert [node.css_first("span").text() for node in found] == ["hit"]


def test_find_elements_by_selectors_returns_empty_when_nothing_matches():
    html = parse_html("<div class='other'></div>")

    assert find_elements_by_selectors(html, [".a", ".b"]) == []
