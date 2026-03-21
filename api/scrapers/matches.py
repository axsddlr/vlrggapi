import asyncio
import logging
import re
from datetime import datetime, timezone

from selectolax.parser import HTMLParser

from utils.http_client import fetch_with_retries, get_http_client
from utils.constants import (
    VLR_BASE_URL,
    VLR_MATCHES_URL,
    CACHE_TTL_UPCOMING,
    CACHE_TTL_LIVE,
    CACHE_TTL_RESULTS,
)
from utils.cache_manager import cache_manager
from utils.error_handling import handle_scraper_errors
from utils.html_parsers import (
    extract_match_teams,
    normalize_image_url,
    parse_eta_to_timedelta,
    combine_date_and_time,
    parse_match_timestamp,
)
from utils.pagination import PaginationConfig, scrape_multiple_pages

logger = logging.getLogger(__name__)


def _safe_text(node) -> str:
    """Safely extract stripped text from an HTML node."""
    if not node:
        return ""
    return node.text().strip()


def _safe_flag(team_node) -> str:
    """Safely extract the homepage flag token from a team node."""
    flag_elem = team_node.css_first(".flag") if team_node else None
    if not flag_elem:
        return ""
    flag_class = flag_elem.attributes.get("class", "")
    return flag_class.replace(" mod-", "").replace("16", "_")


def _safe_timestamp(item) -> str:
    """Extract a UTC timestamp string from a homepage match item."""
    ts_elem = item.css_first(".moment-tz-convert")
    if not ts_elem:
        return ""

    unix_ts = ts_elem.attributes.get("data-utc-ts", "")
    if not unix_ts:
        return ""

    try:
        return datetime.fromtimestamp(int(unix_ts), tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError, OSError):
        return ""


def _safe_match_page(item) -> str:
    """Build a homepage match URL when an href is present."""
    href = item.attributes.get("href", "")
    if not href:
        return ""
    return f"{VLR_BASE_URL}/{href.lstrip('/')}"


@handle_scraper_errors
async def vlr_upcoming_matches(num_pages=1, from_page=None, to_page=None):
    """Get upcoming matches from VLR.GG homepage."""
    cached = cache_manager.get(CACHE_TTL_UPCOMING, "upcoming")
    if cached is not None:
        return cached

    client = get_http_client()
    resp = await fetch_with_retries(VLR_BASE_URL, client=client)
    html = HTMLParser(resp.text)
    status = resp.status_code

    result = []
    for item in html.css(".js-home-matches-upcoming a.wf-module-item"):
        is_upcoming = item.css_first(".h-match-eta.mod-upcoming")
        if not is_upcoming:
            continue

        team1, team2 = extract_match_teams(item, ".h-match-team")

        eta = _safe_text(item.css_first(".h-match-eta"))
        if eta != "LIVE":
            eta = eta + " from now"

        match_event = _safe_text(item.css_first(".h-match-preview-event"))
        match_series = _safe_text(item.css_first(".h-match-preview-series"))
        timestamp = _safe_timestamp(item)
        url_path = _safe_match_page(item)

        result.append(
            {
                "team1": team1["name"],
                "team2": team2["name"],
                "flag1": team1["flag"],
                "flag2": team2["flag"],
                "time_until_match": eta,
                "match_series": match_series,
                "match_event": match_event,
                "unix_timestamp": timestamp,
                "match_page": url_path,
            }
        )

    data = {"data": {"status": status, "segments": result}}

    if status != 200:
        raise Exception("API response: {}".format(status))

    cache_manager.set(CACHE_TTL_UPCOMING, data, "upcoming")
    return data


@handle_scraper_errors
async def vlr_live_score(num_pages=1, from_page=None, to_page=None):
    """Get live match scores from VLR.GG. Fetches match detail pages concurrently."""
    cached = cache_manager.get(CACHE_TTL_LIVE, "live_score")
    if cached is not None:
        return cached

    client = get_http_client()
    resp = await fetch_with_retries(VLR_BASE_URL, client=client)
    html = HTMLParser(resp.text)
    status = resp.status_code

    matches = html.css(".js-home-matches-upcoming a.wf-module-item")
    live_matches = []
    for match in matches:
        is_live = match.css_first(".h-match-eta.mod-live")
        if not is_live:
            continue

        teams = []
        flags = []
        scores = []
        round_texts = []
        for team in match.css(".h-match-team"):
            teams.append(_safe_text(team.css_first(".h-match-team-name")) or "TBD")
            flags.append(_safe_flag(team))
            scores.append(_safe_text(team.css_first(".h-match-team-score")))
            round_info_ct = team.css(".h-match-team-rounds .mod-ct")
            round_info_t = team.css(".h-match-team-rounds .mod-t")
            round_text_ct = round_info_ct[0].text().strip() if round_info_ct else "N/A"
            round_text_t = round_info_t[0].text().strip() if round_info_t else "N/A"
            round_texts.append({"ct": round_text_ct, "t": round_text_t})

        while len(teams) < 2:
            teams.append("TBD")
        while len(flags) < 2:
            flags.append("")
        while len(scores) < 2:
            scores.append("")
        while len(round_texts) < 2:
            round_texts.append({"ct": "N/A", "t": "N/A"})

        match_event = _safe_text(match.css_first(".h-match-preview-event"))
        match_series = _safe_text(match.css_first(".h-match-preview-series"))
        timestamp = _safe_timestamp(match)
        url_path = _safe_match_page(match)

        live_matches.append({
            "teams": teams,
            "flags": flags,
            "scores": scores,
            "round_texts": round_texts,
            "match_event": match_event,
            "match_series": match_series,
            "timestamp": timestamp,
            "url_path": url_path,
        })

    # Fetch all match detail pages concurrently (fix N+1)
    async def fetch_match_detail(url):
        try:
            return await fetch_with_retries(url, client=client)
        except Exception as e:
            logger.warning("Failed to fetch match detail %s: %s", url, e)
            return None

    detail_responses = await asyncio.gather(
        *[fetch_match_detail(m["url_path"]) for m in live_matches]
    )

    result = []
    for match_data, detail_resp in zip(live_matches, detail_responses):
        team_logos = ["", ""]
        current_map = "Unknown"
        map_number = "Unknown"

        if detail_resp is not None:
            match_html = HTMLParser(detail_resp.text)

            logos = []
            for img in match_html.css(".match-header-vs img"):
                logo_url = "https:" + img.attributes.get("src", "")
                logos.append(logo_url)
            if len(logos) >= 2:
                team_logos = logos[:2]

            current_map_element = match_html.css_first(
                ".vm-stats-gamesnav-item.js-map-switch.mod-active.mod-live"
            )
            if current_map_element:
                map_text = (
                    current_map_element.css_first("div", default="Unknown")
                    .text().strip().replace("\n", "").replace("\t", "")
                )
                current_map = re.sub(r"^\d+", "", map_text)
                map_number_match = re.search(r"^\d+", map_text)
                map_number = map_number_match.group(0) if map_number_match else "Unknown"

        rt = match_data["round_texts"]
        result.append(
            {
                "team1": match_data["teams"][0],
                "team2": match_data["teams"][1],
                "flag1": match_data["flags"][0],
                "flag2": match_data["flags"][1],
                "team1_logo": team_logos[0],
                "team2_logo": team_logos[1],
                "score1": match_data["scores"][0],
                "score2": match_data["scores"][1],
                "team1_round_ct": rt[0]["ct"] if len(rt) > 0 else "N/A",
                "team1_round_t": rt[0]["t"] if len(rt) > 0 else "N/A",
                "team2_round_ct": rt[1]["ct"] if len(rt) > 1 else "N/A",
                "team2_round_t": rt[1]["t"] if len(rt) > 1 else "N/A",
                "map_number": map_number,
                "current_map": current_map,
                "time_until_match": "LIVE",
                "match_event": match_data["match_event"],
                "match_series": match_data["match_series"],
                "unix_timestamp": match_data["timestamp"],
                "match_page": match_data["url_path"],
            }
        )

    data = {"data": {"status": status, "segments": result}}

    if status != 200:
        raise Exception("API response: {}".format(status))

    cache_manager.set(CACHE_TTL_LIVE, data, "live_score")
    return data


def _parse_single_match(item, date_str, page):
    """Extract all match fields from one <a> element. Returns dict or None."""
    eta_element = item.css_first(".ml-eta")
    if eta_element and "ago" in eta_element.text():
        return None

    href = item.attributes.get("href", "")
    url_path = "https://www.vlr.gg" + href if href else ""

    # Get match status/eta
    eta = item.css_first(".ml-status").text().strip() if item.css_first(".ml-status") else ""
    if not eta:
        eta_elem = item.css_first(".ml-eta")
        if eta_elem:
            eta_text = eta_elem.text().strip()
            if eta_text and "ago" not in eta_text:
                eta = eta_text

    # Get teams
    teams = []
    flags = []
    scores_list = []
    for team_div in item.css(".match-item-vs-team"):
        team_name_elem = team_div.css_first(".match-item-vs-team-name")
        teams.append(team_name_elem.text().strip() if team_name_elem else "TBD")

        flag_elem = team_div.css_first(".flag")
        if flag_elem:
            flag_class = flag_elem.attributes.get("class")
            flags.append(flag_class.replace("flag ", "").replace(" mod-", "_") if flag_class else "")
        else:
            flags.append("")

        score_elem = team_div.css_first(".match-item-vs-team-score")
        scores_list.append(score_elem.text().strip() if score_elem else "")

    while len(teams) < 2:
        teams.append("TBD")
    while len(flags) < 2:
        flags.append("")
    while len(scores_list) < 2:
        scores_list.append("")

    # Get match event and series info
    match_event_elem = item.css_first(".match-item-event-series")
    match_series = ""
    if match_event_elem:
        event_text = match_event_elem.text().replace("\n", "").replace("\t", "").strip()
        parts = event_text.split()
        if parts:
            match_series = " ".join(parts)

    tourney_elem = item.css_first(".match-item-event")
    tourney = ""
    if tourney_elem:
        tourney_lines = [line.strip() for line in tourney_elem.text().split("\n") if line.strip()]
        tourney = tourney_lines[-1] if tourney_lines else ""

    tourney_icon_elem = item.css_first(".match-item-icon img")
    tourney_icon_url = ""
    if tourney_icon_elem:
        icon_src = tourney_icon_elem.attributes.get("src", "")
        if icon_src:
            tourney_icon_url = normalize_image_url(icon_src)

    # Get timestamp using multi-strategy approach
    timestamp = parse_match_timestamp(item, date_str)

    return {
        "team1": teams[0],
        "team2": teams[1],
        "flag1": flags[0],
        "flag2": flags[1],
        "score1": scores_list[0],
        "score2": scores_list[1],
        "time_until_match": eta,
        "match_series": match_series,
        "match_event": tourney,
        "unix_timestamp": timestamp,
        "match_page": url_path,
        "tournament_icon": tourney_icon_url,
        "page_number": page,
    }


def _parse_upcoming_page(html: HTMLParser, page: int) -> list[dict]:
    """Parse callback for scrape_multiple_pages — upcoming extended matches."""
    page_results = []
    date_labels = html.css(".wf-label.mod-large")

    if date_labels:
        for label in date_labels:
            date_str = label.text().strip()
            sibling = label.next
            card = None
            while sibling is not None:
                if hasattr(sibling, 'tag') and sibling.tag and sibling.attributes:
                    classes = sibling.attributes.get("class", "")
                    if "wf-card" in classes:
                        card = sibling
                        break
                sibling = sibling.next
            if card is None:
                continue
            for item in card.css("a.wf-module-item"):
                try:
                    match_data = _parse_single_match(item, date_str, page)
                    if match_data is not None:
                        page_results.append(match_data)
                except Exception as e:
                    logger.warning("Failed to parse match on page %d: %s", page, e)
    else:
        for item in html.css("a.wf-module-item"):
            try:
                match_data = _parse_single_match(item, "", page)
                if match_data is not None:
                    page_results.append(match_data)
            except Exception as e:
                logger.warning("Failed to parse match on page %d: %s", page, e)

    return page_results


def _parse_results_page(html: HTMLParser, page: int) -> list[dict]:
    """Parse callback for scrape_multiple_pages — match results."""
    page_results = []
    items = html.css("a.wf-module-item")

    for item in items:
        try:
            url_path = item.attributes["href"]
            eta = item.css_first("div.ml-eta").text() + " ago"
            rounds = (
                item.css_first("div.match-item-event-series")
                .text()
                .replace("\u2013", "-")
                .replace("\n", "")
                .replace("\t", "")
            )
            tourney = (
                item.css_first("div.match-item-event")
                .text()
                .replace("\t", " ")
                .strip()
                .split("\n")[1]
                .strip()
            )
            tourney_icon_url = f"https:{item.css_first('img').attributes['src']}"

            try:
                team_array = (
                    item.css_first("div.match-item-vs").css_first("div:nth-child(2)").text()
                )
            except Exception:
                team_array = "TBD"
            team_array = (
                team_array.replace("\t", " ")
                .replace("\n", " ")
                .strip()
                .split("                                  ")
            )
            team1 = team_array[0]
            score1 = team_array[1].replace(" ", "").strip()
            team2 = team_array[4].strip()
            score2 = team_array[-1].replace(" ", "").strip()

            flag_list = [
                flag_parent.attributes["class"].replace(" mod-", "_")
                for flag_parent in item.css(".flag")
            ]
            flag1 = flag_list[0] if len(flag_list) > 0 else ""
            flag2 = flag_list[1] if len(flag_list) > 1 else ""

            page_results.append(
                {
                    "team1": team1,
                    "team2": team2,
                    "score1": score1,
                    "score2": score2,
                    "flag1": flag1,
                    "flag2": flag2,
                    "time_completed": eta,
                    "round_info": rounds,
                    "tournament_name": tourney,
                    "match_page": url_path,
                    "tournament_icon": tourney_icon_url,
                    "page_number": page,
                }
            )
        except Exception as e:
            logger.warning("Failed to parse result on page %d: %s", page, e)
            continue

    return page_results


@handle_scraper_errors
async def vlr_upcoming_matches_extended(
    num_pages=1, from_page=None, to_page=None,
    max_retries=3, request_delay=1.0, timeout=30,
):
    """Scrape upcoming matches from the paginated matches page."""
    config = PaginationConfig(
        num_pages=num_pages, from_page=from_page, to_page=to_page,
        max_retries=max_retries, request_delay=request_delay, timeout=timeout,
    )
    cache_key = ("upcoming_ext", num_pages, from_page, to_page)
    cached = cache_manager.get(CACHE_TTL_UPCOMING, *cache_key)
    if cached is not None:
        return cached

    data = await scrape_multiple_pages(
        base_url=VLR_MATCHES_URL,
        parse_func=_parse_upcoming_page,
        config=config,
    )
    cache_manager.set(CACHE_TTL_UPCOMING, data, *cache_key)
    return data


@handle_scraper_errors
async def vlr_match_results(
    num_pages=1, from_page=None, to_page=None,
    max_retries=3, request_delay=1.0, timeout=30,
):
    """Scrape match results with pagination."""
    config = PaginationConfig(
        num_pages=num_pages, from_page=from_page, to_page=to_page,
        max_retries=max_retries, request_delay=request_delay, timeout=timeout,
    )
    cache_key = ("results", num_pages, from_page, to_page)
    cached = cache_manager.get(CACHE_TTL_RESULTS, *cache_key)
    if cached is not None:
        return cached

    data = await scrape_multiple_pages(
        base_url=f"{VLR_MATCHES_URL}/results",
        parse_func=_parse_results_page,
        config=config,
    )
    cache_manager.set(CACHE_TTL_RESULTS, data, *cache_key)
    return data
