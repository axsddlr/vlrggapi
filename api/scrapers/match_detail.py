"""
Scraper for individual VLR.GG match detail pages.
Fetches the base match page plus performance and economy tabs concurrently.
"""
import asyncio
import logging
import re

from selectolax.parser import HTMLParser

from utils.cache_manager import cache_manager
from utils.constants import (
    CACHE_TTL_MATCH_DETAIL,
    CACHE_TTL_MATCH_DETAIL_LIVE,
    VLR_BASE_URL,
)
from utils.error_handling import handle_scraper_errors
from utils.html_parsers import build_full_url, normalize_image_url, parse_href_id_slug
from utils.http_client import get_http_client

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Header section parsers
# ---------------------------------------------------------------------------

def _parse_event_info(html: HTMLParser) -> dict:
    """Extract event name, series, and logo from the match header."""
    event_name = ""
    event_series = ""
    event_logo = ""

    super_elem = html.css_first(".match-header-super")
    if super_elem:
        # The first child div holds the event name link
        first_div = super_elem.css_first("div")
        if first_div:
            # Try the anchor text within it first
            anchor = first_div.css_first("a")
            if anchor:
                event_name = anchor.text(strip=True)
            else:
                event_name = first_div.text(strip=True)

        series_elem = super_elem.css_first(".match-header-event-series")
        if series_elem:
            event_series = series_elem.text(strip=True)

    # Event logo lives in .match-header-event img
    logo_elem = html.css_first(".match-header-event img")
    if logo_elem:
        src = logo_elem.attributes.get("src", "")
        event_logo = normalize_image_url(src)

    return {"name": event_name, "series": event_series, "logo": event_logo}


def _parse_match_header(html: HTMLParser) -> dict:
    """Extract date, patch, and status from the match header."""
    date = ""
    patch = ""
    status = ""

    date_elem = html.css_first(".match-header-date")
    if date_elem:
        date = date_elem.text(strip=True)

    note_elem = html.css_first(".match-header-note")
    if note_elem:
        patch = note_elem.text(strip=True)

    vs_note_elem = html.css_first(".match-header-vs-note")
    if vs_note_elem:
        status = vs_note_elem.text(strip=True)

    return {"date": date, "patch": patch, "status": status}


def _is_live(html: HTMLParser) -> bool:
    """Return True if the match header indicates the match is currently LIVE."""
    vs_note_elem = html.css_first(".match-header-vs-note")
    if not vs_note_elem:
        return False
    return "LIVE" in vs_note_elem.text(strip=True).upper()


def _parse_teams(html: HTMLParser) -> list[dict]:
    """
    Extract both team entries from the match header.

    Returns a two-element list. Each entry contains name, tag, logo,
    score, and is_winner flag.
    """
    teams: list[dict] = []

    for mod in ("mod-1", "mod-2"):
        name_elem = html.css_first(f".match-header-link-name.{mod}")
        name = ""
        tag = ""
        if name_elem:
            # The full name block contains name + tag on separate lines
            full_text = name_elem.text()
            lines = [ln.strip() for ln in full_text.splitlines() if ln.strip()]
            if lines:
                name = lines[0]
            if len(lines) > 1:
                tag = lines[1]

        teams.append({"name": name, "tag": tag, "logo": "", "score": "", "is_winner": False})

    # Logos: two <img> elements inside .match-header-vs
    vs_elem = html.css_first(".match-header-vs")
    if vs_elem:
        logos = vs_elem.css("img")
        for idx, img in enumerate(logos[:2]):
            src = img.attributes.get("src", "")
            if src:
                teams[idx]["logo"] = normalize_image_url(src)

    # Scores
    score_elems = html.css(".match-header-vs-score span")
    winner_score = ""
    loser_score = ""
    winner_idx = -1

    for span in score_elems:
        cls = span.attributes.get("class") or ""
        if "match-header-vs-score-winner" in cls:
            winner_score = span.text(strip=True)
        elif "match-header-vs-score-loser" in cls:
            loser_score = span.text(strip=True)

    # Determine which team index is the winner based on score positioning.
    # VLR renders winner/loser spans in DOM order: left team first, right team second.
    # Collect all score spans in order to figure out which side won.
    scored_spans = [
        (span.attributes.get("class") or "", span.text(strip=True))
        for span in score_elems
        if span.text(strip=True).isdigit()
    ]

    if len(scored_spans) >= 2:
        cls0, val0 = scored_spans[0]
        cls1, val1 = scored_spans[1]
        teams[0]["score"] = val0
        teams[1]["score"] = val1
        if "match-header-vs-score-winner" in cls0:
            winner_idx = 0
        elif "match-header-vs-score-winner" in cls1:
            winner_idx = 1

    if winner_idx >= 0:
        teams[winner_idx]["is_winner"] = True

    return teams


def _parse_streams_vods(html: HTMLParser) -> tuple[list[dict], list[dict]]:
    """Extract stream buttons and VOD links from the match page."""
    streams: list[dict] = []
    vods: list[dict] = []

    for btn in html.css(".match-streams-btn"):
        href = btn.attributes.get("href", "")
        name = btn.text(strip=True)
        if name or href:
            streams.append({"name": name, "url": build_full_url(href)})

    vods_container = html.css_first(".match-vods")
    if vods_container:
        for anchor in vods_container.css("a"):
            href = anchor.attributes.get("href", "")
            name = anchor.text(strip=True)
            if name or href:
                vods.append({"name": name, "url": href})

    return streams, vods


# ---------------------------------------------------------------------------
# Per-map game data parsers
# ---------------------------------------------------------------------------

def _parse_player_row(cells: list) -> dict:
    """
    Parse a single player table row into a stat dict.

    Actual VLR column layout (14 cells):
      [0]  mod-player   — player name
      [1]  mod-agents   — agent icon (img title)
      [2]  mod-stat     — rating
      [3]  mod-stat     — ACS
      [4]  mod-vlr-kills — kills
      [5]  mod-vlr-deaths — deaths
      [6]  mod-vlr-assists — assists
      [7]  mod-kd-diff  — K/D +/-
      [8]  mod-stat     — KAST
      [9]  mod-stat     — ADR
      [10] mod-stat     — HS%
      [11] mod-fb       — first kills
      [12] mod-fd       — first deaths
      [13] mod-fk-diff  — FK +/-

    Values are in .side.mod-both spans or direct text.
    """

    def cell_val(cell) -> str:
        """Extract the .side.mod-both span value, falling back to raw text."""
        if not cell:
            return ""
        both = cell.css_first(".side.mod-both")
        if both:
            return both.text(strip=True)
        return cell.text(strip=True)

    def safe_val(idx: int) -> str:
        return cell_val(cells[idx]) if idx < len(cells) else ""

    # Player name — [0] mod-player
    player_name = ""
    if cells:
        player_cell = cells[0]
        name_div = player_cell.css_first(".text-of")
        if name_div:
            player_name = name_div.text(strip=True)
        else:
            player_name = player_cell.text(strip=True)

    # Agent — [1] mod-agents, icon title
    agent = ""
    if len(cells) > 1:
        img = cells[1].css_first("img")
        if img:
            agent = img.attributes.get("title", "") or img.attributes.get("alt", "")

    return {
        "name": player_name,
        "agent": agent,
        "rating": safe_val(2),
        "acs": safe_val(3),
        "kills": safe_val(4),
        "deaths": safe_val(5),
        "assists": safe_val(6),
        "kd_diff": safe_val(7),
        "kast": safe_val(8),
        "adr": safe_val(9),
        "hs_pct": safe_val(10),
        "fk": safe_val(11),
        "fd": safe_val(12),
        "fk_diff": safe_val(13),
    }


def _parse_map_players(game_elem) -> dict:
    """
    Parse player stat tables inside a single .vm-stats-game element.

    VLR.GG renders two back-to-back <table> blocks inside
    .vm-stats-container — one per team. We treat each table
    as one team's roster.
    """
    team1_players: list[dict] = []
    team2_players: list[dict] = []

    tables = game_elem.css("table.wf-table-inset.mod-overview")

    def parse_table_rows(table) -> list[dict]:
        players = []
        for row in table.css("tbody tr"):
            cells = row.css("td")
            if not cells:
                continue
            # Skip separator rows: they typically contain very few cells
            if len(cells) < 5:
                continue
            try:
                players.append(_parse_player_row(cells))
            except Exception as exc:
                logger.debug("Skipping player row due to parse error: %s", exc)
        return players

    if len(tables) >= 1:
        team1_players = parse_table_rows(tables[0])
    if len(tables) >= 2:
        team2_players = parse_table_rows(tables[1])

    return {"team1": team1_players, "team2": team2_players}


def _parse_map_scores(game_elem) -> dict:
    """
    Extract team scores and CT/T/OT splits from a single game header.

    The header has `.team` blocks each containing:
    - `.score` for the total round score
    - `.mod-ct` for CT-side rounds
    - `.mod-t` for T-side rounds
    - `.mod-ot` for overtime rounds (optional)
    """
    result = {
        "score": {"team1": "", "team2": ""},
        "score_ct": {"team1": "", "team2": ""},
        "score_t": {"team1": "", "team2": ""},
        "score_ot": {"team1": "", "team2": ""},
    }

    header = game_elem.css_first(".vm-stats-game-header")
    if not header:
        return result

    team_blocks = header.css(".team")
    keys = ["team1", "team2"]

    for idx, block in enumerate(team_blocks[:2]):
        key = keys[idx]

        score_el = block.css_first(".score")
        if score_el:
            val = score_el.text(strip=True)
            try:
                result["score"][key] = int(val)
            except (ValueError, TypeError):
                result["score"][key] = val

        ct_el = block.css_first(".mod-ct")
        if ct_el:
            result["score_ct"][key] = ct_el.text(strip=True)

        t_el = block.css_first(".mod-t")
        if t_el:
            result["score_t"][key] = t_el.text(strip=True)

        ot_el = block.css_first(".mod-ot")
        if ot_el:
            result["score_ot"][key] = ot_el.text(strip=True)

    return result


def _parse_rounds(game_elem) -> list[dict]:
    """
    Parse round-by-round outcomes from a .vlr-rounds container.

    Structure: each .vlr-rounds-row contains .vlr-rounds-row-col elements,
    one per round. Each column has two .rnd-sq spans — [0] = team1, [1] = team2.
    The span with `mod-win` indicates the winner. The side (mod-ct / mod-t)
    tells which side that team was on.

    There are two rows: row 0 covers the first half (+ overtime),
    row 1 covers the second half.
    """
    rounds: list[dict] = []
    rounds_container = game_elem.css_first(".vlr-rounds")
    if not rounds_container:
        return rounds

    round_num = 0
    for row in rounds_container.css(".vlr-rounds-row"):
        for col in row.css(".vlr-rounds-row-col"):
            cls = col.attributes.get("class", "")
            if "mod-spacing" in cls:
                continue

            sqs = col.css(".rnd-sq")
            if not sqs:
                continue

            round_num += 1

            # Determine winner from whichever sq has mod-win
            winner = ""
            winning_side = ""
            for idx, sq in enumerate(sqs):
                sq_cls = sq.attributes.get("class", "")
                if "mod-win" in sq_cls:
                    winner = "team1" if idx == 0 else "team2"
                    if "mod-ct" in sq_cls:
                        winning_side = "ct"
                    elif "mod-t" in sq_cls:
                        winning_side = "t"
                    break

            rounds.append({
                "round_num": round_num,
                "winner": winner,
                "side": winning_side,
            })

    return rounds


def _parse_maps(html: HTMLParser) -> list[dict]:
    """Parse all per-map game blocks from the base match page."""
    maps: list[dict] = []

    for game_elem in html.css("div.vm-stats-game"):
        game_id = game_elem.attributes.get("data-game-id", "")
        if game_id == "all":
            continue

        # Map name — the .map container has child spans for pick info and
        # duration that we need to exclude. Extract just the first text node.
        map_name = ""
        picked_by = ""
        map_container = game_elem.css_first(".vm-stats-game-header .map")
        if map_container:
            # Get the map name from the span that contains only the name,
            # excluding .picked and .map-duration children
            pick_elem = map_container.css_first(".picked") or map_container.css_first(".pick")
            dur_elem = map_container.css_first(".map-duration")
            if pick_elem:
                picked_by = pick_elem.text(strip=True)
            # Remove child text to isolate map name
            full_text = map_container.text(strip=True)
            subtract = ""
            if pick_elem:
                subtract += pick_elem.text(strip=True)
            if dur_elem:
                subtract += dur_elem.text(strip=True)
            map_name = full_text
            for s in [subtract]:
                map_name = map_name.replace(s, "")
            map_name = re.sub(r"\s+", " ", map_name).strip()

        # Duration
        duration = ""
        dur_elem = game_elem.css_first(".map-duration")
        if dur_elem:
            duration = dur_elem.text(strip=True)

        scores = _parse_map_scores(game_elem)
        players = _parse_map_players(game_elem)
        rounds = _parse_rounds(game_elem)

        maps.append({
            "map_name": map_name,
            "picked_by": picked_by,
            "duration": duration,
            "score": scores["score"],
            "score_ct": scores["score_ct"],
            "score_t": scores["score_t"],
            "score_ot": scores["score_ot"],
            "players": players,
            "rounds": rounds,
        })

    return maps


# ---------------------------------------------------------------------------
# Head-to-head history parser
# ---------------------------------------------------------------------------

def _parse_head_to_head(html: HTMLParser) -> list[dict]:
    """Parse head-to-head match history entries."""
    h2h: list[dict] = []

    container = html.css_first(".match-h2h-matches")
    if not container:
        return h2h

    for row in container.css(".wf-module-item"):
        # Team entries: each has mod-win for the winning side
        team_elems = row.css(".match-h2h-matches-team")
        teams = []
        for te in team_elems:
            cls = te.attributes.get("class", "")
            is_winner = "mod-win" in cls
            teams.append({"name": te.text(strip=True), "is_winner": is_winner})

        score_elem = row.css_first(".match-h2h-matches-score")
        score = score_elem.text(strip=True) if score_elem else ""

        event_elem = row.css_first(".match-h2h-matches-event-name")
        event = event_elem.text(strip=True) if event_elem else ""

        date_elem = row.css_first(".match-h2h-matches-date")
        date = date_elem.text(strip=True) if date_elem else ""

        href = row.attributes.get("href", "")
        url = build_full_url(href)

        h2h.append({
            "event": event,
            "date": date,
            "teams": teams,
            "score": score,
            "url": url,
        })

    return h2h


# ---------------------------------------------------------------------------
# Game ID extraction
# ---------------------------------------------------------------------------

def _extract_game_ids(html: HTMLParser) -> list[str]:
    """Return all data-game-id values from the stats nav, excluding 'all'."""
    game_ids: list[str] = []
    for item in html.css(".vm-stats-gamesnav-item"):
        gid = item.attributes.get("data-game-id", "")
        if gid and gid != "all":
            game_ids.append(gid)
    return game_ids


# ---------------------------------------------------------------------------
# Performance tab parsers
# ---------------------------------------------------------------------------

def _parse_kill_matrix(html: HTMLParser) -> list[dict]:
    """
    Parse the kill matrix table from the performance tab.

    Each row represents a player; each cell is the kill count versus
    a specific opponent.
    """
    matrix: list[dict] = []

    table = html.css_first("table.wf-table-inset.mod-matrix.mod-normal")
    if not table:
        return matrix

    # Header row holds opponent names
    header_row = table.css_first("thead tr")
    opponents: list[str] = []
    if header_row:
        for th in header_row.css("th"):
            opponents.append(th.text(strip=True))

    for row in table.css("tbody tr"):
        cells = row.css("td")
        if not cells:
            continue

        player_cell = cells[0]
        player_name = player_cell.text(strip=True)

        kills_vs: dict[str, str] = {}
        for idx, cell in enumerate(cells[1:], start=1):
            opponent = opponents[idx] if idx < len(opponents) else str(idx)
            kills_vs[opponent] = cell.text(strip=True)

        matrix.append({"player": player_name, "kills_vs": kills_vs})

    return matrix


def _parse_advanced_stats(html: HTMLParser) -> list[dict]:
    """
    Parse the advanced stats table from the performance tab.

    Columns: 2K, 3K, 4K, 5K, 1v1, 1v2, 1v3, 1v4, 1v5, Econ, Plants, Defuses
    """
    advanced: list[dict] = []

    table = html.css_first("table.wf-table-inset.mod-adv-stats")
    if not table:
        return advanced

    # Derive header labels
    header_row = table.css_first("thead tr")
    headers: list[str] = []
    if header_row:
        for th in header_row.css("th"):
            headers.append(th.text(strip=True))

    for row in table.css("tbody tr"):
        cells = row.css("td")
        if not cells:
            continue

        player_name = cells[0].text(strip=True) if cells else ""
        stat_dict: dict[str, str] = {"player": player_name}

        for idx, cell in enumerate(cells[1:], start=1):
            label = headers[idx] if idx < len(headers) else str(idx)
            stat_dict[label] = cell.text(strip=True)

        advanced.append(stat_dict)

    return advanced


# ---------------------------------------------------------------------------
# Economy tab parser
# ---------------------------------------------------------------------------

def _parse_economy(html: HTMLParser) -> list[dict]:
    """
    Parse the economy table from the economy tab.

    Rows per team with pistol/eco/semi-buy/full-buy win rates.
    """
    economy: list[dict] = []

    table = html.css_first("table.wf-table-inset.mod-econ")
    if not table:
        return economy

    header_row = table.css_first("thead tr")
    headers: list[str] = []
    if header_row:
        for th in header_row.css("th"):
            headers.append(th.text(strip=True))

    for row in table.css("tbody tr"):
        cells = row.css("td")
        if not cells:
            continue

        row_dict: dict[str, str] = {}
        for idx, cell in enumerate(cells):
            label = headers[idx] if idx < len(headers) else str(idx)
            row_dict[label] = cell.text(strip=True)

        economy.append(row_dict)

    return economy


# ---------------------------------------------------------------------------
# Main scraper
# ---------------------------------------------------------------------------

@handle_scraper_errors
async def vlr_match_detail(match_id: str) -> dict:
    """
    Scrape a single VLR.GG match page and return structured match data.

    Fetches the base page, then concurrently fetches the performance and
    economy tabs for the first game. Cache TTL is 30 s for live matches
    and 300 s for completed matches.

    Args:
        match_id: Numeric VLR.GG match ID (e.g. "123456").

    Returns:
        Standard response dict with shape::

            {
                "data": {
                    "status": 200,
                    "segments": [{ ... match fields ... }]
                }
            }
    """
    base_url = f"{VLR_BASE_URL}/{match_id}"

    # Determine cache TTL after we know if the match is live.
    # We first check the live-TTL cache, then the completed-TTL cache.
    cached = cache_manager.get(CACHE_TTL_MATCH_DETAIL_LIVE, "match_detail", match_id)
    if cached is not None:
        return cached
    cached = cache_manager.get(CACHE_TTL_MATCH_DETAIL, "match_detail", match_id)
    if cached is not None:
        return cached

    client = get_http_client()

    # 1. Fetch the base page
    base_resp = await client.get(base_url)
    base_html = HTMLParser(base_resp.text)
    http_status = base_resp.status_code

    # 2. Discover game IDs for tab fetches
    game_ids = _extract_game_ids(base_html)
    first_game_id = game_ids[0] if game_ids else None

    # 3. Concurrently fetch performance and economy tabs for the first game
    performance_html: HTMLParser | None = None
    economy_html: HTMLParser | None = None

    if first_game_id:
        perf_url = f"{base_url}/?game={first_game_id}&tab=performance"
        econ_url = f"{base_url}/?game={first_game_id}&tab=economy"

        async def _safe_fetch(url: str) -> HTMLParser | None:
            try:
                resp = await client.get(url)
                return HTMLParser(resp.text)
            except Exception as exc:
                logger.warning("Failed to fetch tab page %s: %s", url, exc)
                return None

        perf_result, econ_result = await asyncio.gather(
            _safe_fetch(perf_url),
            _safe_fetch(econ_url),
        )
        performance_html = perf_result
        economy_html = econ_result

    # 4. Parse all sections from the base page
    event_info = _parse_event_info(base_html)
    header_info = _parse_match_header(base_html)
    teams = _parse_teams(base_html)
    streams, vods = _parse_streams_vods(base_html)
    maps = _parse_maps(base_html)
    h2h = _parse_head_to_head(base_html)

    # 5. Parse performance and economy tabs
    kill_matrix: list[dict] = []
    advanced_stats: list[dict] = []
    economy: list[dict] = []

    if performance_html is not None:
        kill_matrix = _parse_kill_matrix(performance_html)
        advanced_stats = _parse_advanced_stats(performance_html)

    if economy_html is not None:
        economy = _parse_economy(economy_html)

    # 6. Assemble the response
    segment = {
        "match_id": match_id,
        "event": event_info,
        "date": header_info["date"],
        "patch": header_info["patch"],
        "status": header_info["status"],
        "teams": teams,
        "streams": streams,
        "vods": vods,
        "maps": maps,
        "head_to_head": h2h,
        "performance": {
            "kill_matrix": kill_matrix,
            "advanced_stats": advanced_stats,
        },
        "economy": economy,
    }

    data = {"data": {"status": http_status, "segments": [segment]}}

    # 7. Cache with appropriate TTL
    live = _is_live(base_html)
    ttl = CACHE_TTL_MATCH_DETAIL_LIVE if live else CACHE_TTL_MATCH_DETAIL
    cache_manager.set(ttl, data, "match_detail", match_id)

    return data
