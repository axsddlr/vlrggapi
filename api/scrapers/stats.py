import asyncio
import logging
from urllib.parse import urlencode

from fastapi import HTTPException

from utils.cache_manager import cache_manager
from utils.constants import CACHE_TTL_STATS, STATS_TIERS, VLR_STATS_URL
from utils.error_handling import (
    handle_scraper_errors,
    raise_for_upstream_status,
    validate_stats_map,
    validate_stats_region,
    validate_timespan,
)
from utils.html_parsers import extract_text_content, parse_html
from utils.http_client import fetch_with_retries, get_http_client

logger = logging.getLogger(__name__)

# vlr.gg emits stable, semantic ``data-col`` attributes on every stats <th> except
# the unlabelled player column. Read cells BY KEY so a future inserted column can
# never shift the mapping — the positional fragility fixed here has broken this
# scraper three times (upstream issues #4 and #14, both "vlr.gg added a column",
# each re-hardcoded to the new numbers). Pages without ``data-col`` fall back to
# ``_LEGACY_STATS_INDICES`` below, which does read fixed positions.
# Keys are the CURRENT vlr.gg data-col vocabulary. The October 2026 /stats filter
# revamp renamed two of them: the rating column went from ``rating2`` to
# ``rating``, and first-kill rate from ``fbpr`` to ``fkpr``. It also added
# maps/kmax/k/d/a/fk/fd, which this API does not expose yet.
_STATS_FIELD_MAP = {
    "rnd": "rounds_played",
    "rating": "rating",
    "acs": "average_combat_score",
    "kd": "kill_deaths",
    "kast": "kill_assists_survived_traded",
    "adr": "average_damage_per_round",
    "kpr": "kills_per_round",
    "apr": "assists_per_round",
    "fkpr": "first_kills_per_round",
    "fdpr": "first_deaths_per_round",
    "hsp": "headshot_percentage",
    "clp": "clutch_success_percentage",
    "cl": "clutch_attempts",
}

# If <thead> is keyed (>=1 data-col) but any of these is absent, the layout changed
# in a way we cannot safely parse -> fail closed rather than emit a keyed ``None``
# that would surface downstream as rating=0 and slip past shape guards.
REQUIRED_STATS_KEYS = frozenset({"rnd", "rating", "acs", "kd", "adr"})

# Legacy positional indices, used ONLY when <thead> emits no data-col attributes at
# all (pre-revamp markup / archived pages). Player is td[0], agents td[1].
_LEGACY_STATS_INDICES = {
    "rounds_played": 2,
    "rating": 3,
    "average_combat_score": 4,
    "kill_deaths": 5,
    "kill_assists_survived_traded": 6,
    "average_damage_per_round": 7,
    "kills_per_round": 8,
    "assists_per_round": 9,
    "first_kills_per_round": 10,
    "first_deaths_per_round": 11,
    "headshot_percentage": 12,
    "clutch_success_percentage": 13,
    "clutch_attempts": 14,
}

# Session priming state. vlr.gg binds /stats filter state to a ``PHPSESSID`` cookie:
# the FIRST request on a cold client returns the unfiltered global list regardless
# of ``region=``. The singleton httpx.AsyncClient shares cookies across concurrent
# requests, so the one-time prime is guarded by a lock + module flag.
_prime_lock = asyncio.Lock()
_primed = False


def _cell_text(cells: list, index: int | None) -> str:
    """Read a table cell by index without raising on sparse rows or missing keys."""
    if index is None or index >= len(cells):
        return ""
    return extract_text_content(cells[index])


def _build_column_map(html) -> dict | None:
    """Map each <thead> ``data-col`` attribute to its 0-based column index.

    Returns ``{data-col: index}`` when the header is keyed, or ``None`` when it
    carries no data-col attributes (old markup -> positional fallback). Indices are
    counted across all <th>, so they line up with the row's <td> positions; the
    player <th> is unlabelled and is simply absent from the map.
    """
    header = html.css_first("thead tr")
    if header is None:
        return None
    col_map: dict[str, int] = {}
    for index, th in enumerate(header.css("th")):
        data_col = th.attributes.get("data-col")
        if data_col:
            col_map[data_col] = index
    return col_map or None


def _parse_stats_row(item, col_map: dict | None = None) -> dict:
    """Parse one stats table row.

    With ``col_map`` (from :func:`_build_column_map`) cells are read by semantic
    ``data-col`` key; without it, the legacy positional indices are used. The player
    cell is always positional ``td[0]``. The org selector tries the new
    ``.st-pl-country`` class first and falls back to the pre-revamp
    ``.stats-player-country`` so either markup parses.
    """
    cells = item.css("td")
    player_cell = item.css_first("td.mod-player")

    player_name = extract_text_content(player_cell.css_first(".text-of")) if player_cell else ""
    org_cell = None
    if player_cell:
        org_cell = (
            player_cell.css_first(".st-pl-country")
            or player_cell.css_first(".stats-player-country")
        )
    org = extract_text_content(org_cell) if org_cell else ""
    if not org:
        org = "N/A"

    agents = []
    for agent_img in item.css("td.mod-agents img"):
        src = agent_img.attributes.get("src", "")
        if not src:
            continue
        agents.append(src.split("/")[-1].split(".")[0])

    row = {"player": player_name, "org": org, "agents": agents}
    if col_map is not None:
        for data_col, out_key in _STATS_FIELD_MAP.items():
            row[out_key] = _cell_text(cells, col_map.get(data_col))
    else:
        for out_key, index in _LEGACY_STATS_INDICES.items():
            row[out_key] = _cell_text(cells, index)
    return row


def _selected_region(html) -> str | None:
    """Return the region vlr.gg actually applied to this response.

    This is the ground truth of which filter the server used. The October 2026
    revamp replaced the ``<select name="region">`` with a ``form.st-filter``
    whose regions are ``<input name="region[]">`` checkboxes, so the applied
    value is now the one carrying ``checked``; a form with nothing ticked means
    no region restriction ("all"). The legacy select is still read as a
    fallback. Returns ``None`` when neither shape is present, so callers skip
    response validation on markup we do not model.
    """
    form = html.css_first("form.st-filter")
    if form is not None:
        checked = form.css('input[name="region[]"][checked]')
        if checked:
            return checked[0].attributes.get("value") or None
        return "all"

    select = html.css_first('select[name="region"]')
    if select is None:
        return None
    selected = select.css_first("option[selected]")
    if selected is None:
        return None
    value = selected.attributes.get("value")
    return value if value is not None else (extract_text_content(selected) or None)


async def _fetch_stats_page(client, url: str) -> tuple[int, object]:
    """Fetch the stats page, raising on an upstream error status; return (status, tree)."""
    resp = await fetch_with_retries(url, client=client)
    raise_for_upstream_status(resp.status_code, "stats")
    return resp.status_code, parse_html(resp.text)


async def _prime_session(client, *, force: bool = False) -> None:
    """Issue one throwaway GET to the /stats page so vlr.gg sets ``PHPSESSID``.

    Guarded by a lock + module flag so the singleton client primes once per boot,
    not once per call. Raises on failure — a cold response must never be fetched
    (and cached for ``CACHE_TTL_STATS`` seconds) unfiltered. ``force=True`` re-primes
    after a detected region mismatch.
    """
    global _primed
    async with _prime_lock:
        if _primed and not force:
            return
        resp = await fetch_with_retries(f"{VLR_STATS_URL}/", client=client)
        raise_for_upstream_status(resp.status_code, "stats prime")
        _primed = True


@handle_scraper_errors
async def vlr_stats(
    region_key: str,
    timespan: str,
    event_id: str | None = None,
    map_name: str = "all",
    min_rounds: int = 200,
    min_rating: float = 1.55,
):
    # Normalize alias -> canonical BEFORE the cache key is formed so na and americas
    # resolve to one entry, and validate up front so bad input fails without a fetch.
    region_key = validate_stats_region(region_key)
    validate_timespan(timespan)
    map_id = validate_stats_map(map_name)
    min_rounds = max(0, int(min_rounds))
    min_rating = max(0.0, float(min_rating))

    async def build():
        resolved_event_id = event_id if event_id else "all"
        # The revamped filter form submits the region and tier groups as checkbox
        # arrays (``region[]`` / ``tier[]``). The legacy singular names are still
        # accepted server-side, but the plural is what the site itself sends.
        #
        # The tier group is not optional: omit it and vlr.gg applies its own
        # default of VCT alone (the form's ``data-defaults`` say tier=vct and only
        # the vct box comes back checked), narrowing the ladder to VCT events.
        #
        # Built as an explicit pair list rather than ``urlencode(..., doseq=True)``
        # so that only the two array-valued filters can repeat: doseq would also
        # expand any single-valued filter that happened to hold a sequence.
        filters = [
            ("event_group_id", "all"),
            ("event_id", resolved_event_id),
            ("region[]", region_key),
            *(("tier[]", tier) for tier in STATS_TIERS),
            ("country", "all"),
            ("min_rounds", min_rounds),
            # vlr.gg expresses the rating floor on a x1000 integer scale.
            ("min_rating", int(round(min_rating * 1000))),
            ("agent", "all"),
            ("map_id", map_id),
            ("timespan", "all" if timespan.lower() == "all" else f"{timespan}d"),
        ]
        query = urlencode(filters)
        url = f"{VLR_STATS_URL}/?{query}"

        client = get_http_client()
        await _prime_session(client)

        status, html = await _fetch_stats_page(client, url)

        # Response-level validation is the correctness signal (not cookie presence):
        # the page echoes the applied filter back (today as the checked ``region[]``
        # box). On a mismatch, re-prime and refetch once; a second mismatch means
        # vlr.gg is ignoring the region param -> raise rather than cache a
        # globally-scoped list under a specific region key.
        selected = _selected_region(html)
        if selected is not None and selected != region_key:
            logger.warning(
                "VLR.GG /stats applied region '%s' but '%s' was requested; re-priming",
                selected, region_key,
            )
            await _prime_session(client, force=True)
            status, html = await _fetch_stats_page(client, url)
            selected = _selected_region(html)
            if selected is not None and selected != region_key:
                raise HTTPException(
                    status_code=502,
                    detail=(
                        f"VLR.GG /stats ignored the region filter: requested "
                        f"'{region_key}', page applied '{selected}'"
                    ),
                )

        col_map = _build_column_map(html)
        if col_map is not None:
            missing = REQUIRED_STATS_KEYS - col_map.keys()
            if missing:
                raise HTTPException(
                    status_code=502,
                    detail=(
                        "VLR.GG /stats column layout changed: required columns "
                        f"{sorted(missing)} missing from header"
                    ),
                )
        elif html.css_first("table") is not None:
            # A table without data-col attributes is genuinely legacy markup. A page
            # with NO table at all is a legitimately-empty result set (vlr.gg renders
            # no table for zero rows, e.g. sparse tier/span windows) — stay quiet.
            logger.warning(
                "VLR.GG /stats header has no data-col attributes; "
                "falling back to legacy positional column indices"
            )

        result = []
        for item in html.css("tbody tr"):
            parsed = _parse_stats_row(item, col_map)
            if parsed["player"]:
                result.append(parsed)

        return {"data": {"status": status, "segments": result}}

    return await cache_manager.get_or_create_async(
        CACHE_TTL_STATS,
        build,
        "stats",
        region_key,
        timespan,
        event_id or "all",
        map_id,
        min_rounds,
        min_rating,
    )
