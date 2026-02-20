"""
Scraper for VLR.GG player profile and match history pages.
"""
import logging
import re

from selectolax.parser import HTMLParser

from utils.cache_manager import cache_manager
from utils.constants import CACHE_TTL_PLAYER, CACHE_TTL_PLAYER_MATCHES, VLR_BASE_URL
from utils.error_handling import handle_scraper_errors
from utils.html_parsers import (
    build_full_url,
    extract_region_from_flag,
    infer_platform,
    normalize_image_url,
    parse_href_id_slug,
)
from utils.http_client import get_http_client

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_player_info(html: HTMLParser) -> dict:
    """Extract core player identity fields from the player header."""
    name = ""
    name_elem = html.css_first("h1.wf-title") or html.css_first(".wf-title")
    if name_elem:
        name = name_elem.text(strip=True)

    real_name = ""
    real_name_elem = html.css_first(".player-real-name")
    if real_name_elem:
        real_name = real_name_elem.text(strip=True)

    avatar = ""
    avatar_elem = html.css_first(".wf-avatar.mod-player img")
    if avatar_elem:
        avatar = normalize_image_url(avatar_elem.attributes.get("src", ""))

    country = ""
    # The flag element lives in or near the player header section
    header = html.css_first(".player-header")
    if header:
        flag_elem = header.css_first(".flag")
        if flag_elem:
            country = extract_region_from_flag(flag_elem)
    if not country:
        # Fallback: first flag on the page
        flag_elem = html.css_first(".flag")
        if flag_elem:
            country = extract_region_from_flag(flag_elem)

    social_links = _parse_social_links(html)

    return {
        "name": name,
        "real_name": real_name,
        "avatar": avatar,
        "country": country,
        "social_links": social_links,
    }


def _parse_social_links(html: HTMLParser) -> list[dict]:
    """Extract social platform links from `.social` anchor elements."""
    links: list[dict] = []
    for anchor in html.css("a.social"):
        href = anchor.attributes.get("href", "")
        if not href:
            continue
        # Platform can come from the mod-* class (e.g. mod-twitter) or be inferred from URL
        class_attr = anchor.attributes.get("class", "")
        platform = ""
        for part in class_attr.split():
            if part.startswith("mod-"):
                platform = part[4:]  # strip "mod-"
                break
        if not platform:
            platform = infer_platform(href)
        links.append({"platform": platform, "url": href})
    return links


def _parse_teams(html: HTMLParser) -> tuple[dict, list[dict]]:
    """
    Extract current team and past teams from `.player-summary-container-1`.

    VLR renders each team as a `.wf-module-item` with:
    - Team name as the first text node (before any `.ge-text-light` children)
    - Status tag in `.wf-tag.mod-light` (e.g. "stand-in")
    - Dates in the last `.ge-text-light` element (e.g. "March 2021 — September 2024")
    - Logo as an `img` element
    - The first item is typically the current team; if it has date text with
      a "—" separator showing an end date, it's actually a past team.
    """
    current_team: dict = {"name": "", "tag": "", "logo": "", "joined": ""}
    past_teams: list[dict] = []

    container = html.css_first(".player-summary-container-1")
    if not container:
        return current_team, past_teams

    for item in container.css(".wf-module-item"):
        # Logo
        logo = ""
        logo_elem = item.css_first("img")
        if logo_elem:
            logo = normalize_image_url(logo_elem.attributes.get("src", ""))

        # Status tag (e.g. "stand-in", "inactive")
        tag_elem = item.css_first(".wf-tag.mod-light")
        status = tag_elem.text(strip=True) if tag_elem else ""

        # Dates — last .ge-text-light with actual text
        dates = ""
        date_elems = item.css(".ge-text-light")
        for de in reversed(date_elems):
            dt = de.text(strip=True)
            if dt:
                dates = dt
                break

        # Team name: full text minus dates and status
        full_text = item.text(strip=True)
        name = full_text
        if status:
            name = name.replace(status, "")
        if dates:
            name = name.replace(dates, "")
        name = name.strip()

        if not name:
            continue

        # Determine if current or past: if dates contain "—" with text after it,
        # that indicates an end date (= past team)
        has_end_date = "\u2013" in dates or "\u2014" in dates or " – " in dates or " - " in dates
        is_current = not has_end_date

        if is_current and not current_team["name"]:
            joined = dates  # e.g. "joined in May 2025"
            current_team = {"name": name, "tag": status, "logo": logo, "joined": joined}
        else:
            past_teams.append(
                {"name": name, "tag": status, "dates": dates, "logo": logo}
            )

    return current_team, past_teams


def _parse_agent_stats(html: HTMLParser) -> list[dict]:
    """
    Extract per-agent statistics from the wf-table on the player page.

    Table columns (17 total):
      [0]  Agent (img alt/title)
      [1]  Use (count + %) — e.g. "(206) 46%"
      [2]  RND (rounds)
      [3]  Rating 2.0
      [4]  ACS
      [5]  K:D
      [6]  ADR
      [7]  KAST
      [8]  KPR
      [9]  APR
      [10] FKPR
      [11] FDPR
      [12] K (kills)
      [13] D (deaths)
      [14] A (assists)
      [15] FK
      [16] FD
    """
    agent_stats: list[dict] = []

    table = html.css_first("table.wf-table")
    if not table:
        return agent_stats

    for row in table.css("tbody tr"):
        cells = row.css("td")
        if len(cells) < 17:
            continue

        # Agent name
        agent = ""
        img = cells[0].css_first("img")
        if img:
            agent = img.attributes.get("alt", "") or img.attributes.get("title", "")
        if not agent:
            agent = cells[0].text(strip=True)
        if not agent:
            continue

        # Use column — split count and percentage
        use_text = cells[1].text(strip=True)
        usage_count = ""
        usage_pct = ""
        count_match = re.search(r"\((\d+)\)", use_text)
        if count_match:
            usage_count = count_match.group(1)
        pct_match = re.search(r"(\d+%)", use_text)
        if pct_match:
            usage_pct = pct_match.group(1)

        def val(idx: int) -> str:
            return cells[idx].text(strip=True) if idx < len(cells) else ""

        agent_stats.append({
            "agent": agent,
            "usage_count": usage_count,
            "usage_pct": usage_pct,
            "rounds": val(2),
            "rating": val(3),
            "acs": val(4),
            "kd": val(5),
            "adr": val(6),
            "kast": val(7),
            "kpr": val(8),
            "apr": val(9),
            "fkpr": val(10),
            "fdpr": val(11),
            "kills": val(12),
            "deaths": val(13),
            "assists": val(14),
            "fk": val(15),
            "fd": val(16),
        })

    return agent_stats


def _parse_event_placements(html: HTMLParser) -> list[dict]:
    """
    Extract tournament placement records.

    Items are `.wf-module-item.player-event-item` anchors. Structure:
    - `.text-of` child: event name
    - `.ge-text-light` child: series + placement text (e.g. "Playoffs — 4th")
    - Full text contains prize ($xxx), team name, and year
    """
    placements: list[dict] = []

    for item in html.css(".wf-module-item.player-event-item"):
        # Event name
        event_elem = item.css_first(".text-of")
        event = event_elem.text(strip=True) if event_elem else ""

        # Series and placement from .ge-text-light
        placement = ""
        series = ""
        detail_elem = item.css_first(".ge-text-light")
        if detail_elem:
            detail_text = detail_elem.text(strip=True)
            # Split on em-dash or hyphen to get series and placement
            # e.g. "Playoffs — 4th" or "Playoffs — 7th–8th"
            parts = re.split(r"\s*[—\u2014\u2013]\s*", detail_text, maxsplit=1)
            if len(parts) >= 2:
                series = parts[0].strip()
                placement = parts[1].strip()
            elif parts:
                # Might be just placement
                placement = parts[0].strip()

        # Prize from full text
        full_text = item.text(strip=True)
        prize = ""
        prize_match = re.search(r"\$[\d,]+", full_text)
        if prize_match:
            prize = prize_match.group(0)

        # Team and year: remaining text after removing known parts
        remaining = full_text
        for remove in [event, series, placement, prize]:
            if remove:
                remaining = remaining.replace(remove, "", 1)
        # Clean up special chars and collapse whitespace
        remaining = re.sub(r"[—\u2014\u2013$,\(\)]", " ", remaining)
        remaining = re.sub(r"\s+", " ", remaining).strip()

        # Year is typically the last 4-digit number
        year_match = re.search(r"(20\d{2})", remaining)
        date = year_match.group(1) if year_match else ""

        # Team name: what's left after removing the year
        team = remaining
        if date:
            # Split on the year boundary to separate team from year
            team = re.sub(r"20\d{2}", "", team).strip()

        href = item.attributes.get("href", "")
        url = build_full_url(href)

        if event or placement:
            placements.append({
                "event": event,
                "series": series,
                "placement": placement,
                "prize": prize,
                "team": team,
                "date": date,
                "url": url,
            })

    return placements


def _parse_news(html: HTMLParser) -> list[dict]:
    """
    Extract news articles linked from the player page.

    VLR.GG embeds news item links typically as `a` elements whose href
    starts with `/` and whose path segment starts with a news-article
    pattern. We look for anchor elements that contain date text and a title
    within the news section of the page.
    """
    news_items: list[dict] = []

    # Try dedicated news section first
    news_section = html.css_first(".player-news") or html.css_first(".wf-card.mod-dark")
    scope = news_section if news_section else html

    for anchor in scope.css("a"):
        href = anchor.attributes.get("href", "")
        if not href:
            continue
        # VLR news articles have numeric slugs like /1234/some-title
        parts = href.strip("/").split("/")
        if not (len(parts) >= 2 and parts[0].isdigit()):
            continue

        title_elem = anchor.css_first(".wf-module-item-title") or anchor.css_first("h2")
        title = title_elem.text(strip=True) if title_elem else anchor.text(strip=True)
        if not title:
            continue

        date_elem = anchor.css_first(".m-item-date") or anchor.css_first(".ge-text-light")
        date = date_elem.text(strip=True) if date_elem else ""

        url = build_full_url(href)
        news_items.append({"title": title, "url": url, "date": date})

    return news_items


def _parse_total_winnings(html: HTMLParser) -> str:
    """
    Look for a total prize money figure on the player page.

    VLR.GG shows it as a highlighted stat-like block near the event
    placements section. We search for a `$` prefixed amount in likely
    containers and return the largest value found, as that is most likely
    the cumulative total.
    """
    # Try a dedicated earnings element first
    for selector in (".player-earnings", ".wf-card .player-earnings-total", ".wf-label"):
        elem = html.css_first(selector)
        if elem:
            text = elem.text(strip=True)
            match = re.search(r"\$[\d,]+", text)
            if match:
                return match.group(0)

    # Fallback: collect all dollar amounts on the page and return the largest
    all_amounts: list[int] = []
    full_page_text = html.root.text() if html.root else ""
    for m in re.finditer(r"\$([\d,]+)", full_page_text):
        try:
            all_amounts.append(int(m.group(1).replace(",", "")))
        except ValueError:
            continue

    if all_amounts:
        return f"${max(all_amounts):,}"

    return ""


# ---------------------------------------------------------------------------
# Match-history page helpers
# ---------------------------------------------------------------------------


def _parse_player_match_item(item) -> dict | None:
    """
    Parse a single match item from the player match history page.

    Match cards use `.wf-card.fc-flex.m-item` as the container anchor.
    """
    href = item.attributes.get("href", "")
    match_id, _ = parse_href_id_slug(href)
    url = build_full_url(href)

    # Result — check classes on `.m-item-result`
    result_elem = item.css_first(".m-item-result")
    result = ""
    if result_elem:
        result_class = result_elem.attributes.get("class", "")
        if "mod-win" in result_class:
            result = "win"
        elif "mod-loss" in result_class:
            result = "loss"

    # Score text from result element (e.g. "2 - 0")
    score = ""
    if result_elem:
        score = result_elem.text(strip=True)

    # Teams (there should be two `.m-item-team` elements)
    team_elems = item.css(".m-item-team")
    teams = []
    for te in team_elems:
        name_el = te.css_first(".m-item-team-name")
        tag_el = te.css_first(".m-item-team-tag")
        logo_el = te.css_first(".m-item-logo img") or te.css_first("img")

        name = name_el.text(strip=True) if name_el else ""
        tag = tag_el.text(strip=True) if tag_el else ""
        logo = ""
        if logo_el:
            logo = normalize_image_url(logo_el.attributes.get("src", ""))
        teams.append({"name": name, "tag": tag, "logo": logo})

    while len(teams) < 2:
        teams.append({"name": "", "tag": "", "logo": ""})

    # Event name
    event_elem = item.css_first(".m-item-event")
    event = event_elem.text(strip=True) if event_elem else ""

    # Date
    date_elem = item.css_first(".m-item-date")
    date = date_elem.text(strip=True) if date_elem else ""

    if not match_id and not url:
        return None

    return {
        "match_id": match_id,
        "url": url,
        "event": event,
        "date": date,
        "team1": teams[0],
        "team2": teams[1],
        "score": score,
        "result": result,
    }


# ---------------------------------------------------------------------------
# Public scraper functions
# ---------------------------------------------------------------------------


@handle_scraper_errors
async def vlr_player(player_id: str, timespan: str = "90d") -> dict:
    """
    Scrape a VLR.GG player profile page.

    Args:
        player_id: Numeric player ID (e.g. "2").
        timespan: Agent stats window — one of "30d", "60d", "90d", "all".

    Returns:
        Standard API envelope with a single-element segments list.
    """
    cache_key = ("player", player_id, timespan)
    cached = cache_manager.get(CACHE_TTL_PLAYER, *cache_key)
    if cached is not None:
        return cached

    url = f"{VLR_BASE_URL}/player/{player_id}/?timespan={timespan}"
    client = get_http_client()
    resp = await client.get(url)
    status = resp.status_code

    html = HTMLParser(resp.text)

    player_info = _parse_player_info(html)
    current_team, past_teams = _parse_teams(html)
    agent_stats = _parse_agent_stats(html)
    event_placements = _parse_event_placements(html)
    news = _parse_news(html)
    total_winnings = _parse_total_winnings(html)

    segment = {
        "id": player_id,
        "name": player_info["name"],
        "real_name": player_info["real_name"],
        "avatar": player_info["avatar"],
        "country": player_info["country"],
        "social_links": player_info["social_links"],
        "current_team": current_team,
        "past_teams": past_teams,
        "agent_stats": agent_stats,
        "event_placements": event_placements,
        "news": news,
        "total_winnings": total_winnings,
    }

    data = {"data": {"status": status, "segments": [segment]}}
    cache_manager.set(CACHE_TTL_PLAYER, data, *cache_key)
    return data


@handle_scraper_errors
async def vlr_player_matches(player_id: str, page: int = 1) -> dict:
    """
    Scrape the match history page for a VLR.GG player.

    Args:
        player_id: Numeric player ID (e.g. "2").
        page: Pagination index, 1-based.

    Returns:
        Standard API envelope with match segments and a meta block.
    """
    cache_key = ("player_matches", player_id, page)
    cached = cache_manager.get(CACHE_TTL_PLAYER_MATCHES, *cache_key)
    if cached is not None:
        return cached

    url = f"{VLR_BASE_URL}/player/matches/{player_id}/?page={page}"
    client = get_http_client()
    resp = await client.get(url)
    status = resp.status_code

    html = HTMLParser(resp.text)

    matches: list[dict] = []

    # Primary selector: anchor cards with the m-item pattern
    for item in html.css("a.wf-card.m-item"):
        try:
            parsed = _parse_player_match_item(item)
            if parsed is not None:
                matches.append(parsed)
        except Exception as exc:
            logger.warning(
                "Failed to parse player match item for player %s page %d: %s",
                player_id, page, exc,
            )

    # Fallback: the page may use fc-flex on the card element
    if not matches:
        for item in html.css("a.wf-card.fc-flex.m-item"):
            try:
                parsed = _parse_player_match_item(item)
                if parsed is not None:
                    matches.append(parsed)
            except Exception as exc:
                logger.warning(
                    "Failed to parse player match item (fc-flex) for player %s page %d: %s",
                    player_id, page, exc,
                )

    data = {
        "data": {
            "status": status,
            "segments": matches,
            "meta": {"page": page},
        }
    }
    cache_manager.set(CACHE_TTL_PLAYER_MATCHES, data, *cache_key)
    return data
