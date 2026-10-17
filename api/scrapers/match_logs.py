"""
Scraper for the vlr.gg match "logs" tab — the 2D replay (``tab=logs``).

Every round of the selected game embeds its replay as JSON in
``div.lg-map[data-map]``: the attacking team, a player roster, and one entry per
kill / spike plant / spike defuse carrying each player's position and health.
The surrounding DOM adds what the JSON omits: the round result, the per-player
buy (credits, weapon, armour) and the damage source of each kill.

Markup arrived in October 2026 and still carries a "New" badge on vlr.gg, so
every selector here is deliberately narrow and the whole parse degrades to an
empty ``rounds`` list instead of raising.
"""
import json
import logging
import re

from utils.cache_manager import cache_manager
from utils.constants import CACHE_TTL_MATCH_DETAIL, MATCH_DETAIL_TAB_FETCH_TIMEOUT, VLR_BASE_URL
from utils.error_handling import handle_scraper_errors, upstream_error_payload
from utils.html_parsers import HTMLParser, extract_text_content, parse_html
from utils.http_client import fetch_with_retries, get_http_client

logger = logging.getLogger(__name__)

_ARMOR = {
    "no armor": "none",
    "light armor": "light",
    "heavy armor": "heavy",
    "regen shield": "regen",
}

_SPIKE_SITE = re.compile(r"Spike (?:planted|defused)\s+([A-C])", re.IGNORECASE)


def _first_played_game_id(html: HTMLParser) -> str | None:
    """Return the first games-nav game ID that is not the aggregate or disabled."""
    for item in html.css(".vm-stats-gamesnav-item"):
        game_id = item.attributes.get("data-game-id") or ""
        if game_id and game_id != "all" and item.attributes.get("data-disabled") != "1":
            return game_id
    return None


def _round_strip(html: HTMLParser) -> dict[str, str]:
    """Map round number -> end reason from the replay round strip titles."""
    reasons: dict[str, str] = {}
    for column in html.css(".js-lg-round"):
        round_no = column.attributes.get("data-round")
        title = column.attributes.get("title") or ""
        if round_no and "," in title:
            reasons[round_no] = title.rsplit(",", 1)[-1].strip()
    return reasons


def _parse_band(html: HTMLParser) -> dict:
    """Read the score band: scores, which team attacks, and the round winner."""
    band = html.css_first(".lg-band")
    if band is None:
        return {"teams": {}, "score": {}, "winner": "", "attacking_side": ""}

    teams: dict[str, dict] = {}
    score: dict[str, int] = {}
    attacking_side = ""
    for side, index in ((".lg-band-team.mod-t1", 1), (".lg-band-team.mod-t2", 2)):
        team = band.css_first(side)
        if team is None:
            continue
        key = f"team{index}"
        name = team.css_first(".lg-band-name")
        tag = team.css_first(".lg-band-tag")
        score_el = team.css_first(".lg-band-score")
        teams[key] = {
            "name": (name.attributes.get("title") or extract_text_content(name)) if name else "",
            "tag": extract_text_content(tag) if tag else "",
        }
        score[key] = int(extract_text_content(score_el) or 0) if score_el else 0
        if "mod-atk" in (team.attributes.get("class") or ""):
            attacking_side = key

    winner = ""
    band_class = band.attributes.get("class") or ""
    if "mod-win-1" in band_class:
        winner = "team1"
    elif "mod-win-2" in band_class:
        winner = "team2"

    return {"teams": teams, "score": score, "winner": winner, "attacking_side": attacking_side}


def _parse_economy(round_el) -> list[dict]:
    """Read each player's buy for the round from the ``lg-mir`` table."""
    economy: list[dict] = []
    for index, team_block in enumerate(round_el.css(".lg-mir-team"), start=1):
        for row in team_block.css(".lg-mir-row"):
            name = row.css_first(".lg-mir-name")
            agent_img = row.css_first("img.lg-agent")
            weapon_img = row.css_first(".lg-kit-gun")
            left = row.css_first(".lg-mir-left")
            spent = row.css_first(".lg-kit-spent")
            shield = row.css_first(".lg-kit-shield")
            no_armor = row.css_first(".lg-noarmor")

            agent = ""
            if agent_img is not None:
                title = agent_img.attributes.get("title") or ""
                agent = title.rsplit("(", 1)[-1].rstrip(")").strip().lower()

            armor = "none"
            if shield is not None:
                armor = _ARMOR.get((shield.attributes.get("title") or "").lower(), "light")
            elif no_armor is None:
                armor = ""

            economy.append(
                {
                    "player": extract_text_content(name),
                    "team": index,
                    "agent": agent,
                    "credits": _as_int(left),
                    "spent": abs(_as_int(spent)),
                    "weapon": (weapon_img.attributes.get("title") or "") if weapon_img is not None else "",
                    "armor": armor,
                }
            )
    return economy


def _as_int(element) -> int:
    """Parse a cell like '50' or '−750' (U+2212 minus) into an int."""
    text = extract_text_content(element) if element is not None else ""
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else 0


def _parse_feed(round_el) -> dict[int, dict]:
    """Map event index -> data the replay JSON lacks (damage source, spike site)."""
    feed: dict[int, dict] = {}
    for row in round_el.css(".lg-row"):
        index = row.attributes.get("data-ev")
        if index is None or not index.isdigit():
            continue
        entry: dict[str, str] = {}
        source = row.css_first(".lg-source")
        if source is not None and source.attributes.get("title"):
            entry["source"] = source.attributes["title"]
        site = _SPIKE_SITE.search(extract_text_content(row.css_first(".lg-spike-what")))
        if site:
            entry["site"] = site.group(1).upper()
        feed[int(index)] = entry
    return feed


def _parse_replay(round_el) -> tuple[dict, dict]:
    """Return the round's replay JSON and its player roster, keyed by integer ID."""
    holder = round_el.css_first("div.lg-map[data-map]")
    if holder is None:
        return {}, {}
    try:
        payload = json.loads(holder.attributes.get("data-map") or "{}")
    except json.JSONDecodeError:
        logger.warning("Unparseable lg-map replay payload; skipping round replay")
        return {}, {}
    roster: dict[int, dict] = {}
    for player_id, info in (payload.get("players") or {}).items():
        if isinstance(info, list) and len(info) >= 3:
            roster[int(player_id)] = {"team": info[0], "agent": info[1], "name": info[2]}
    return payload, roster


def _xy(pair) -> dict | None:
    if not isinstance(pair, list) or len(pair) < 2:
        return None
    return {"x": pair[0], "y": pair[1]}


def _parse_events(payload: dict, roster: dict[int, dict], feed: dict[int, dict]) -> list[dict]:
    """Normalise the replay events, joining the roster and the DOM feed."""
    events: list[dict] = []
    for index, raw in enumerate(payload.get("events") or []):
        kind = raw.get("type") or ""
        event: dict = {"t": raw.get("t", ""), "type": kind}

        actor = roster.get(int(raw["by"])) if raw.get("by") else None
        if actor:
            event["player"] = actor["name"]
            event["team"] = actor["team"]

        if kind == "kill":
            victim = roster.get(int(raw["vid"])) if raw.get("vid") else None
            event["victim"] = victim["name"] if victim else raw.get("victim", "")
            event["victim_team"] = victim["team"] if victim else None

        for key in ("pos", "from"):
            point = _xy(raw.get(key))
            if point is not None:
                event[key] = point

        positions: list[dict] = []
        for entry in raw.get("locs") or []:
            if not isinstance(entry, list) or len(entry) < 4:
                continue
            player = roster.get(int(entry[0]))
            positions.append(
                {
                    "player": player["name"] if player else str(entry[0]),
                    "team": player["team"] if player else None,
                    "x": entry[1],
                    "y": entry[2],
                    "hp": entry[3],
                }
            )
        if positions:
            event["positions"] = positions

        event.update(feed.get(index) or {})
        events.append(event)
    return events


def _parse_round(round_el, reasons: dict[str, str]) -> dict:
    """Assemble one round: result, buy, and replay events."""
    round_no = round_el.attributes.get("data-round") or ""
    band = _parse_band(round_el)
    payload, roster = _parse_replay(round_el)
    return {
        "round": int(round_no) if round_no.isdigit() else None,
        "score": band["score"],
        "winner": band["winner"],
        "attacking_side": band["attacking_side"],
        "end_reason": reasons.get(round_no, ""),
        "economy": _parse_economy(round_el),
        "events": _parse_events(payload, roster, _parse_feed(round_el)),
    }


def parse_logs(html: HTMLParser) -> dict:
    """Parse one game's replay from the logs tab. Returns {"map", "teams", "rounds"}."""
    scope = html.css_first(".vm-stats-game.mod-active") or html
    art = scope.css_first(".lg-map-art")
    art_href = (art.attributes.get("href") or "") if art is not None else ""
    map_slug = ""
    if art_href:
        file_name = art_href.split("?")[0].rsplit("/", 1)[-1]
        map_slug = file_name.rsplit(".", 1)[0]

    reasons = _round_strip(scope)
    rounds = [_parse_round(round_el, reasons) for round_el in scope.css(".lg-round")]
    if not rounds:
        return {"map": map_slug, "teams": {}, "rounds": []}
    return {"map": map_slug, "teams": _parse_band(scope)["teams"], "rounds": rounds}


@handle_scraper_errors
async def vlr_match_logs(match_id: str, game_id: str | None = None) -> dict:
    """
    Scrape the 2D replay ("logs" tab) of one game of a match.

    Args:
        match_id: Numeric VLR.GG match ID.
        game_id: Optional numeric game ID. When omitted, the first played map of
            the match is used.

    Returns:
        ``{"data": {"status": int, "segments": [segment]}}`` where the segment is
        ``{match_id, game_id, map, teams, rounds}`` and each round carries its
        result, per-player buy and replay events. A game without replay data (for
        example a map that was never played) returns an empty ``rounds`` list.
    """
    cache_key = (match_id, game_id or "")
    cached = cache_manager.get(CACHE_TTL_MATCH_DETAIL, "match_logs", *cache_key)
    if cached is not None:
        return cached

    client = get_http_client()

    if game_id is None:
        base_resp = await fetch_with_retries(f"{VLR_BASE_URL}/{match_id}/", client=client)
        if base_resp.status_code >= 400:
            return upstream_error_payload(base_resp.status_code, f"match {match_id}")
        game_id = _first_played_game_id(parse_html(base_resp.text))
        if game_id is None:
            return {"data": {"status": base_resp.status_code, "segments": []}}

    tab_url = f"{VLR_BASE_URL}/{match_id}/?game={game_id}&tab=logs"
    tab_resp = await fetch_with_retries(
        tab_url, client=client, timeout=MATCH_DETAIL_TAB_FETCH_TIMEOUT
    )
    if tab_resp.status_code >= 400:
        return upstream_error_payload(tab_resp.status_code, f"match logs {match_id}")

    parsed = parse_logs(parse_html(tab_resp.text))
    segment = {
        "match_id": match_id,
        "game_id": game_id,
        "map": parsed["map"],
        "teams": parsed["teams"],
        "rounds": parsed["rounds"],
    }
    data = {"data": {"status": tab_resp.status_code, "segments": [segment]}}
    cache_manager.set(CACHE_TTL_MATCH_DETAIL, data, "match_logs", *cache_key)
    return data
