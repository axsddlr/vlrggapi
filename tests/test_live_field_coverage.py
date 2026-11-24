"""Live field-coverage check: catch vlr.gg changes that silently empty API fields.

The selector check (``tests/test_vlr_selectors.py``) proves a CSS selector still
*exists*. It cannot tell that a value a selector feeds has gone empty: #247 was
exactly that — the agent cell moved, every ``agent`` came back ``""``, and no
selector was missing. This module closes that gap by asserting *data* coverage
on the live API instead of markup presence.

How it decides
  Each endpoint declares the fields it must carry, with a threshold and the
  reason that threshold is not 1.0. For every sampled record the field counts as
  present when it is a non-empty string, list, or dict, or a number/bool. A
  field fails when its coverage ratio falls below its threshold, when no records
  were sampled at all, or when a field is absent from the payload entirely.

  Thresholds are deliberately below 1.0 where vlr.gg legitimately omits data —
  an unplayed match has no score, some listings have no event — so the check
  flags a *collapse* (#247 measured 0.0) rather than ordinary variance.

Running it
  Contributor PRs never run the live part: ``pytest`` skips it unless
  ``FIELD_CHECK_LIVE=1``. The ``field-check`` workflow sets that and writes a
  JSON report for the issue body. Locally:

      FIELD_CHECK_LIVE=1 uv run pytest tests/test_live_field_coverage.py -v
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from api.utils.rate_limiter import get_rate_limiter
from main import app

LIVE = os.environ.get("FIELD_CHECK_LIVE") == "1"
REPORT_PATH = os.environ.get("FIELD_REPORT_PATH", "")

# Sampled live records per endpoint. Low on purpose: one match-details call
# already yields 10 players x N maps, and every extra page is a request to
# vlr.gg from a job that runs daily.
MATCHES = 2
TEAMS = 2
PLAYERS = 2

# Per-player stats appear a while after a match ends: a match completed minutes
# ago lists its maps but carries no ratings yet (measured 0/30 mid-matchday,
# 30/30 from ~2 days back). Sampling only settled matches keeps the thresholds
# strict instead of loosening them into uselessness.
MIN_AGE_HOURS = 24


@dataclass(frozen=True)
class FieldRule:
    """One field that must stay populated, with why its threshold is < 1.0."""

    name: str
    threshold: float
    reason: str


@dataclass(frozen=True)
class EndpointSpec:
    label: str
    fields: tuple[FieldRule, ...]


@dataclass
class Coverage:
    endpoint: str
    field: str
    present: int
    total: int
    threshold: float

    @property
    def ratio(self) -> float:
        return 0.0 if self.total == 0 else self.present / self.total

    @property
    def ok(self) -> bool:
        # No records is no evidence: an endpoint that suddenly returns nothing
        # is a break, not a pass.
        return self.total > 0 and self.ratio >= self.threshold

    def describe(self) -> str:
        return (
            f"{self.endpoint}: {self.field} {self.present}/{self.total} "
            f"({self.ratio:.0%}, needs >= {self.threshold:.0%})"
        )


SPECS: tuple[EndpointSpec, ...] = (
    EndpointSpec(
        "match results",
        (
            FieldRule("match_id", 1.0, "every listing row links to a match page"),
            FieldRule(
                "team1", 0.95, "both names normally present; allow 5% for TBD slots"
            ),
            FieldRule(
                "team2",
                0.95,
                "same as team1: rows without both names are a parse break",
            ),
            FieldRule(
                "tournament_name",
                0.90,
                "exhibition/showmatch rows sometimes carry no event",
            ),
            FieldRule(
                "score1",
                0.80,
                "completed rows carry a score; forfeits and unknown results may not",
            ),
        ),
    ),
    EndpointSpec(
        "match details players",
        (
            FieldRule(
                "agent",
                0.95,
                "#247: a markup move emptied this for every player (measured 0.0)",
            ),
            FieldRule(
                "rating",
                0.95,
                "settled matches carry a rating per player; sampled only >= 24h old",
            ),
            FieldRule("name", 1.0, "the player cell always carries the alias"),
        ),
    ),
    EndpointSpec(
        "match details maps",
        (
            FieldRule("map_name", 1.0, "every map section is titled"),
            FieldRule(
                "score",
                0.90,
                "some maps are listed but never played, so they carry no score",
            ),
        ),
    ),
    EndpointSpec(
        "team",
        (
            FieldRule("name", 1.0, "the team page is keyed by name"),
            FieldRule(
                "roster",
                0.50,
                "vlr.gg serves team pages with no roster section for new or "
                "unsigned orgs (measured: MALAJUNTA/25222 renders zero roster "
                "items), so only a collapse across the sample is a break",
            ),
        ),
    ),
    EndpointSpec(
        "player",
        (
            FieldRule("name", 1.0, "the player page is keyed by alias"),
            FieldRule(
                "agent_stats",
                0.50,
                "a player with no recorded maps has no agent table",
            ),
        ),
    ),
    EndpointSpec(
        "events",
        (
            FieldRule("event_id", 1.0, "every listing row links to an event"),
            FieldRule("title", 1.0, "every listing row is named"),
            FieldRule("dates", 0.80, "TBD events have no dates yet"),
        ),
    ),
)

SPEC_BY_LABEL = {spec.label: spec for spec in SPECS}


def has_value(value) -> bool:
    """True when ``value`` would be useful to an API consumer."""
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict, tuple, set)):
        return len(value) > 0
    return True


def coverage(records: list[dict], spec: EndpointSpec) -> list[Coverage]:
    """Coverage of every declared field across ``records``."""
    return [
        Coverage(
            endpoint=spec.label,
            field=rule.name,
            present=sum(1 for record in records if has_value(record.get(rule.name))),
            total=len(records),
            threshold=rule.threshold,
        )
        for rule in spec.fields
    ]


def failures(all_coverage: list[Coverage]) -> list[Coverage]:
    return [item for item in all_coverage if not item.ok]


# ---------------------------------------------------------------------------
# Offline tests: the decision logic, no network
# ---------------------------------------------------------------------------


def test_fully_populated_payload_passes():
    spec = SPEC_BY_LABEL["match details players"]
    records = [
        {"agent": "Viper", "rating": "1.23", "name": "Dillon"},
        {"agent": "Jett", "rating": "1.05", "name": "Hasagi"},
    ]

    result = coverage(records, spec)

    assert failures(result) == []
    assert all(item.ratio == 1.0 for item in result)


def test_emptied_agent_column_fails_and_names_the_field():
    """The #247 shape: everything parses, agents are all empty strings."""
    spec = SPEC_BY_LABEL["match details players"]
    records = [
        {"agent": "", "rating": "1.23", "name": "Dillon"},
        {"agent": "   ", "rating": "1.15", "name": "Hasagi"},
        {"agent": None, "rating": "0.97", "name": "wertlle"},
    ]

    broken = failures(coverage(records, spec))

    assert [item.field for item in broken] == ["agent"]
    assert broken[0].present == 0 and broken[0].total == 3
    assert "agent 0/3" in broken[0].describe()


def test_sparse_but_above_threshold_passes():
    """Four of five rows carrying a score clears the 0.80 threshold."""
    spec = SPEC_BY_LABEL["match results"]
    records = [
        {"match_id": str(i), "team1": "a", "team2": "b", "tournament_name": "e",
         "score1": score}
        for i, score in enumerate(["13", "2", "0", "", "7"])
    ]

    result = {item.field: item for item in coverage(records, spec)}

    assert result["score1"].ratio == 0.8
    assert result["score1"].ok
    assert failures(list(result.values())) == []


def test_sparse_below_threshold_fails():
    spec = SPEC_BY_LABEL["match results"]
    records = [
        {"match_id": str(i), "team1": "a", "team2": "b", "tournament_name": "e",
         "score1": "" if i < 2 else "13"}
        for i in range(5)
    ]

    broken = failures(coverage(records, spec))

    assert [item.field for item in broken] == ["score1"]
    assert broken[0].ratio == 0.6


def test_no_records_is_a_failure_not_a_pass():
    """An endpoint that returns nothing must not read as 100% covered."""
    for spec in SPECS:
        result = coverage([], spec)
        assert failures(result), f"{spec.label} passed with no records"
        assert all(item.ratio == 0.0 for item in result)


def test_missing_key_counts_as_absent():
    spec = EndpointSpec("probe", (FieldRule("kept", 1.0, "always rendered"),))
    assert failures(coverage([{"other": "x"}], spec))
    assert not failures(coverage([{"kept": 0}], spec))  # 0 is a real value


def test_every_threshold_is_justified():
    """A threshold below 1.0 must say why, or it is an unexplained hole."""
    for spec in SPECS:
        for rule in spec.fields:
            assert 0.0 < rule.threshold <= 1.0
            assert rule.reason, f"{spec.label}.{rule.name} has no reason"
            if rule.threshold < 1.0:
                assert len(rule.reason) > 10


# ---------------------------------------------------------------------------
# Live driver
# ---------------------------------------------------------------------------


def _segments(payload: dict) -> list:
    data = payload.get("data") or {}
    segments = data.get("segments")
    if isinstance(segments, list):
        return segments
    return [segments] if segments else []


def _first_segment(payload: dict) -> dict:
    segments = _segments(payload)
    return segments[0] if segments and isinstance(segments[0], dict) else {}


def age_hours(completed: str | None) -> float | None:
    """Hours since completion, from vlr.gg's relative stamp ("2d 3h ago").

    Returns ``None`` when the stamp cannot be read, which callers treat as
    "unknown age" rather than "fresh".
    """
    if not completed or "ago" not in completed:
        return None
    match = re.search(
        r"(?:(\d+)\s*d)?\s*(?:(\d+)\s*h)?\s*(?:(\d+)\s*m)?", completed.replace("ago", "")
    )
    if not match or not any(match.groups()):
        return None
    days, hours, minutes = (int(g) if g else 0 for g in match.groups())
    return days * 24 + hours + minutes / 60


def select_settled(
    results: list[dict], min_age_hours: float = MIN_AGE_HOURS, limit: int = MATCHES
) -> list[str]:
    """Match IDs old enough that per-player stats should be published."""
    settled: list[str] = []
    for row in results:
        match_id = row.get("match_id")
        age = age_hours(row.get("time_completed"))
        if not match_id or age is None or age < min_age_hours:
            continue
        settled.append(str(match_id))
        if len(settled) == limit:
            break
    return settled


async def _collect_live() -> dict[str, list[dict]]:
    """Sample the live API and return ``{endpoint label: records}``."""
    collected: dict[str, list[dict]] = {spec.label: [] for spec in SPECS}
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", timeout=180
    ) as client:
        # Results double as the source of match IDs for the detail probes.
        get_rate_limiter()._stores.clear()
        results_payload = (await client.get("/v2/match?q=results")).json()
        results = [r for r in _segments(results_payload) if isinstance(r, dict)]
        collected["match results"] = results

        match_ids = select_settled(results)
        team_ids: list[str] = []
        player_ids: list[str] = []

        for match_id in match_ids:
            get_rate_limiter()._stores.clear()
            detail = _first_segment(
                (await client.get(f"/v2/match/{match_id}/details")).json()
            )
            for team in detail.get("teams") or []:
                if team.get("id") and team["id"] not in team_ids:
                    team_ids.append(str(team["id"]))
            for map_entry in detail.get("maps") or []:
                collected["match details maps"].append(
                    {
                        "map_name": map_entry.get("map_name"),
                        "score": map_entry.get("score"),
                    }
                )
                for side in ("team1", "team2"):
                    for player in (map_entry.get("players") or {}).get(side) or []:
                        collected["match details players"].append(
                            {
                                "name": player.get("name"),
                                "agent": player.get("agent"),
                                "rating": player.get("rating"),
                            }
                        )

        for team_id in team_ids[:TEAMS]:
            get_rate_limiter()._stores.clear()
            team = _first_segment((await client.get(f"/v2/team/{team_id}")).json())
            roster = team.get("roster") or []
            collected["team"].append({"name": team.get("name"), "roster": roster})
            for member in roster:
                if member.get("id") and str(member["id"]) not in player_ids:
                    player_ids.append(str(member["id"]))

        for player_id in player_ids[:PLAYERS]:
            get_rate_limiter()._stores.clear()
            player = _first_segment(
                (await client.get(f"/v2/player/{player_id}")).json()
            )
            collected["player"].append(
                {
                    "name": player.get("name"),
                    "agent_stats": player.get("agent_stats"),
                }
            )

        get_rate_limiter()._stores.clear()
        events_payload = (await client.get("/v2/events?q=completed")).json()
        collected["events"] = [
            e for e in _segments(events_payload) if isinstance(e, dict)
        ]

    return collected


def _write_report(all_coverage: list[Coverage], collected: dict[str, list[dict]]) -> None:
    if not REPORT_PATH:
        return
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "checks": [
            {
                "endpoint": item.endpoint,
                "field": item.field,
                "present": item.present,
                "total": item.total,
                "ratio": round(item.ratio, 4),
                "threshold": item.threshold,
                "ok": item.ok,
            }
            for item in all_coverage
        ],
        "sampled": {label: len(records) for label, records in collected.items()},
        "failures": [
            {"endpoint": item.endpoint, "field": item.field,
             "present": item.present, "total": item.total,
             "threshold": item.threshold}
            for item in failures(all_coverage)
        ],
    }
    Path(REPORT_PATH).write_text(json.dumps(report, indent=2), encoding="utf-8")


@pytest.mark.skipif(
    not LIVE, reason="live field check: set FIELD_CHECK_LIVE=1 to run"
)
def test_live_field_coverage():
    """Every declared field still carries data on the live vlr.gg API."""
    collected = asyncio.run(_collect_live())

    all_coverage: list[Coverage] = []
    for label, records in collected.items():
        all_coverage.extend(coverage(records, SPEC_BY_LABEL[label]))

    _write_report(all_coverage, collected)

    print("\nfield coverage:")
    for item in all_coverage:
        print(f"  {'ok  ' if item.ok else 'FAIL'} {item.describe()}")

    broken = failures(all_coverage)
    assert not broken, "field coverage collapsed:\n  " + "\n  ".join(
        item.describe() for item in broken
    )


def test_age_hours_reads_relative_stamps():
    assert age_hours("2d 3h ago") == pytest.approx(51.0)
    assert age_hours("6d 17h ago") == pytest.approx(161.0)
    assert age_hours("12h 38m ago") == pytest.approx(12 + 38 / 60)
    assert age_hours("5h 13m ago") == pytest.approx(5 + 13 / 60)
    assert age_hours("9m ago") == pytest.approx(0.15)
    assert age_hours("") is None
    assert age_hours(None) is None
    assert age_hours("scheduled") is None


def test_select_settled_skips_fresh_matches_and_respects_limit():
    results = [
        {"match_id": "1", "time_completed": "5h 13m ago"},   # too fresh: stats pending
        {"match_id": "2", "time_completed": "23h 0m ago"},   # just under the cutoff
        {"match_id": "3", "time_completed": "2d 0h ago"},
        {"match_id": "4", "time_completed": "6d 17h ago"},
        {"match_id": "5", "time_completed": "9d 1h ago"},
        {"match_id": "6", "time_completed": "unknown"},
    ]

    assert select_settled(results, limit=2) == ["3", "4"]
    assert select_settled(results, limit=10) == ["3", "4", "5"]


def test_select_settled_is_empty_when_every_match_is_fresh():
    """No settled match must surface as missing data, not as a silent pass."""
    results = [{"match_id": "1", "time_completed": "1h 0m ago"}]

    assert select_settled(results) == []
    for spec in SPECS:
        assert not coverage([], spec)[0].ok
