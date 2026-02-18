"""
Scrapers for VLR.GG team profile pages.

Provides three async scraper functions:
  - vlr_team: team profile (header, rating, roster, event placements)
  - vlr_team_matches: paginated match history for a team
  - vlr_team_transactions: roster transaction log for a team
"""
import logging
import re

from selectolax.parser import HTMLParser

from utils.cache_manager import cache_manager
from utils.constants import (
    CACHE_TTL_TEAM,
    CACHE_TTL_TEAM_MATCHES,
    CACHE_TTL_TEAM_TRANSACTIONS,
    VLR_BASE_URL,
)
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
# Private helpers
# ---------------------------------------------------------------------------


def _text(element, strip: bool = True) -> str:
    """Safely extract text from a selectolax element."""
    if not element:
        return ""
    return element.text(strip=strip)


def _attr(element, name: str, default: str = "") -> str:
    """Safely get an attribute from a selectolax element."""
    if not element:
        return default
    val = element.attributes.get(name, default)
    return val if val is not None else default


def _parse_team_header(html: HTMLParser, team_id: str) -> dict:
    """Extract team identity fields from the .team-header block."""
    header = html.css_first(".team-header")

    # Name — try the canonical h1 inside the name block first, then fall back
    name_block = header.css_first(".team-header-name") if header else None
    name = _text(name_block.css_first("h1") if name_block else None)
    if not name:
        name = _text(html.css_first("h1.wf-title"))

    # Tag (short identifier like "SEN")
    tag = _text(name_block.css_first("h2") if name_block else None)

    # Successor / alternate name label (present on some rebuilt orgs)
    successor_elem = html.css_first(".team-header-name-successor")
    successor = _text(successor_elem)

    # Logo
    logo_img = header.css_first("img") if header else None
    logo = normalize_image_url(_attr(logo_img, "src"))

    # Country — the flag element carries the country code in its class
    country_block = html.css_first(".team-header-country")
    flag_elem = country_block.css_first(".flag") if country_block else None
    country_code = extract_region_from_flag(flag_elem)
    # The visible country name sits as text next to the flag
    country_name = ""
    if country_block:
        raw = _text(country_block)
        country_name = raw.strip()

    # Social / external links
    social_links = _parse_social_links(html)

    # Optional free-text description
    desc_elem = html.css_first(".team-header-desc")
    description = _text(desc_elem)

    return {
        "id": team_id,
        "name": name,
        "tag": tag,
        "successor": successor,
        "logo": logo,
        "country": country_code,
        "country_name": country_name,
        "description": description,
        "social_links": social_links,
    }


def _parse_social_links(html: HTMLParser) -> list[dict]:
    """
    Collect all social / external links from the team header link bar.

    VLR marks social anchors with .social and a modifier class like
    .mod-twitter or .mod-discord.  The link bar (.team-header-links) may
    also contain a plain website link without a .social class.
    """
    links: list[dict] = []
    seen: set[str] = set()

    links_container = html.css_first(".team-header-links")
    anchors = links_container.css("a") if links_container else []

    # Also pick up any .social anchors that may live outside the container
    for anchor in html.css("a.social"):
        if anchor not in anchors:
            anchors.append(anchor)

    for anchor in anchors:
        href = _attr(anchor, "href").strip()
        if not href or href in seen:
            continue
        seen.add(href)

        # Try to infer the platform from the CSS class first (most reliable)
        css_class = _attr(anchor, "class", "")
        platform = ""
        for part in css_class.split():
            if part.startswith("mod-") and part != "mod-":
                platform = part[4:]  # strip "mod-" prefix
                break

        # Fall back to URL-based inference when no modifier class is present
        if not platform:
            platform = infer_platform(href)

        links.append({"platform": platform, "url": href})

    return links


def _parse_rating_info(html: HTMLParser) -> dict:
    """Extract team ranking / rating block data."""
    rating_container = html.css_first(".team-rating-info")
    if not rating_container:
        return {"rank": "", "rating": "", "peak_rating": "", "streak": ""}

    rank_section = rating_container.css_first(
        ".team-rating-info-section.mod-rank"
    )
    rating_section = rating_container.css_first(
        ".team-rating-info-section.mod-rating"
    )
    streak_section = rating_container.css_first(
        ".team-rating-info-section.mod-streak"
    )

    rank = _text(rank_section.css_first(".rank-num") if rank_section else None)
    rating = _text(
        rating_section.css_first(".rating-num") if rating_section else None
    )
    peak_rating = _text(
        rating_section.css_first(".rating-num-peak") if rating_section else None
    )
    # Streak section text may include a "Record" prefix and other labels
    streak_raw = _text(streak_section)
    streak = re.sub(r"^(?:Record|Streak)\s*", "", streak_raw, flags=re.IGNORECASE).strip()

    return {
        "rank": rank,
        "rating": rating,
        "peak_rating": peak_rating,
        "streak": streak,
    }


def _parse_roster(html: HTMLParser) -> list[dict]:
    """
    Extract the full roster including staff members.

    VLR groups roster items under .wf-label headings (text like "active"
    and "staff"). We walk all elements in the summary container in document
    order, toggling the is_staff flag when we encounter a label.
    """
    roster: list[dict] = []
    seen_ids: set[str] = set()

    # The roster lives in .team-summary-container-1
    container = html.css_first(".team-summary-container-1")
    if not container:
        # Fallback: just grab all roster items without staff distinction
        for item in html.css(".team-roster-item"):
            player = _parse_single_roster_item(item, is_staff=False)
            if player["alias"] and player["alias"] not in seen_ids:
                seen_ids.add(player["alias"])
                roster.append(player)
        return roster

    # Walk direct children of the container to find labels and roster items
    is_staff = False
    for node in container.css("*"):
        css_class = node.attributes.get("class", "") or ""

        # Check for section labels
        if "wf-label" in css_class and "team-roster-item" not in css_class:
            label_text = node.text(strip=True).lower()
            if "staff" in label_text or "coach" in label_text:
                is_staff = True
            elif any(k in label_text for k in ("player", "roster", "active")):
                is_staff = False
            continue

        # Check for roster items — only match the direct .team-roster-item class
        if "team-roster-item" in css_class and "team-roster-item-" not in css_class:
            player = _parse_single_roster_item(node, is_staff)
            # Deduplicate by alias
            dedup_key = player["alias"] or player["id"]
            if dedup_key and dedup_key not in seen_ids:
                seen_ids.add(dedup_key)
                roster.append(player)

    return roster


def _iter_children_deep(node):
    """
    Yield every descendant node in document order.
    selectolax's css("*") already returns in document order.
    """
    seen: set[int] = set()
    for child in node.css("*"):
        nid = id(child)
        if nid not in seen:
            seen.add(nid)
            yield child


def _parse_single_roster_item(item, is_staff: bool) -> dict:
    """Parse one .team-roster-item node into a player/staff dict."""
    anchor = item.css_first("a")
    href = _attr(anchor, "href")
    player_id, _ = parse_href_id_slug(href)
    player_url = build_full_url(href)

    alias = _text(item.css_first(".team-roster-item-name-alias"))
    real_name = _text(item.css_first(".team-roster-item-name-real"))

    # Avatar
    avatar_img = item.css_first(".team-roster-item-img img")
    if not avatar_img:
        avatar_img = item.css_first("img")
    avatar = normalize_image_url(_attr(avatar_img, "src"))

    # Country flag
    flag_elem = item.css_first(".flag")
    country = extract_region_from_flag(flag_elem)

    # Captain indicator — presence of a star icon
    is_captain = item.css_first(".fa.fa-star") is not None

    # Role / position text (some items have an explicit IGL / coach label)
    role = ""
    name_block = item.css_first(".team-roster-item-name")
    if name_block:
        # Collect all text nodes, remove the alias and real name, what remains
        # (if anything) is the role label
        full_name_text = _text(name_block)
        stripped = full_name_text.replace(alias, "").replace(real_name, "").strip()
        # Clean up residual whitespace / separators
        role = re.sub(r"\s+", " ", stripped).strip(" -/|")

    return {
        "id": player_id,
        "url": player_url,
        "alias": alias,
        "real_name": real_name,
        "avatar": avatar,
        "country": country,
        "is_captain": is_captain,
        "role": role,
        "is_staff": is_staff,
    }


def _parse_event_placements(html: HTMLParser) -> tuple[list[dict], str]:
    """
    Parse event placement history from the team results section.

    VLR renders event history in the right-hand summary block, typically
    inside .team-summary-container-2.  Each row links to an event and
    carries the series label, placement, and prize text.

    Returns (placements_list, total_winnings_str).
    """
    placements: list[dict] = []
    total_winnings = ""

    # Try the dedicated summary container first
    container = html.css_first(".team-summary-container-2")
    if not container:
        # Some pages put everything in a single summary container
        container = html.css_first(".team-summary-container")

    if not container:
        return placements, total_winnings

    # Total winnings is often shown in a top-level text block before the list
    for wf_card in container.css(".wf-card"):
        raw = _text(wf_card)
        # Look for a dollar-prefixed total at the start of the card text
        match = re.search(r"\$([\d,]+(?:\.\d+)?)", raw)
        if match and not total_winnings:
            total_winnings = "$" + match.group(1)

    # Event placement rows — vlr uses anchor tags that link to the event
    for event_anchor in container.css("a"):
        href = _attr(event_anchor, "href")
        if not href:
            continue
        event_url = build_full_url(href)

        # Event name: may be in a child span or as direct text
        event_name_elem = (
            event_anchor.css_first(".wf-title-med")
            or event_anchor.css_first(".event-item-title")
            or event_anchor.css_first("div")
        )
        event_name = _text(event_name_elem) if event_name_elem else _text(event_anchor)

        # Series label (e.g., "VCT 2025 Americas Kickoff")
        series_elem = event_anchor.css_first(".team-event-item-series")
        series = _text(series_elem)

        # Placement and prize come from sibling/child text nodes
        full_text = _text(event_anchor)
        placement = _extract_placement(full_text)
        prize = _extract_prize_from_text(full_text)

        # Date: look for a date-shaped substring
        date = _extract_date_from_text(full_text)

        if event_name or placement:
            placements.append(
                {
                    "event": event_name,
                    "series": series,
                    "placement": placement,
                    "prize": prize,
                    "date": date,
                    "url": event_url,
                }
            )

    return placements, total_winnings


def _extract_placement(text: str) -> str:
    """
    Pull a placement string like "1st", "3rd-4th", "5th-8th" from free text.
    """
    if not text:
        return ""
    match = re.search(
        r"\b(\d+(?:st|nd|rd|th)(?:\s*[-–]\s*\d+(?:st|nd|rd|th))?)\b",
        text,
        re.IGNORECASE,
    )
    return match.group(1) if match else ""


def _extract_prize_from_text(text: str) -> str:
    """Pull a dollar-amount string from free text."""
    if not text:
        return ""
    match = re.search(r"\$([\d,]+(?:\.\d+)?(?:[KMkm])?)", text)
    return match.group(0) if match else ""


def _extract_date_from_text(text: str) -> str:
    """Pull a short date or year from free text (e.g. '2024', 'Jan 2025')."""
    if not text:
        return ""
    match = re.search(
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*"
        r"\.?\s+\d{4}\b|\b\d{4}\b",
        text,
        re.IGNORECASE,
    )
    return match.group(0) if match else ""


# ---------------------------------------------------------------------------
# Match history helpers (used by vlr_team_matches)
# ---------------------------------------------------------------------------


def _parse_team_match_item(item) -> dict | None:
    """
    Parse one match row from the team match history page.

    VLR uses .wf-card elements containing .m-item anchors (or the anchor
    itself carries .wf-card .m-item classes).
    """
    # The anchor may be the item itself or a child
    anchor = item if item.tag == "a" else item.css_first("a")
    href = _attr(anchor, "href") if anchor else _attr(item, "href")
    if not href:
        return None

    match_id, _ = parse_href_id_slug(href)
    match_url = build_full_url(href)

    # Result: win or loss derived from class modifiers
    item_class = _attr(item, "class", "")
    result_elem = item.css_first(".m-item-result")
    result_class = _attr(result_elem, "class", "") if result_elem else ""
    result = ""
    if "mod-win" in result_class or "mod-win" in item_class:
        result = "win"
    elif "mod-loss" in result_class or "mod-loss" in item_class:
        result = "loss"

    # Score text — sits inside the result block
    score = _text(result_elem)

    # Teams — VLR renders both teams; the "home" team is typically listed first
    team_elems = item.css(".m-item-team")
    teams: list[dict] = []
    for te in team_elems:
        t_name = _text(te.css_first(".m-item-team-name"))
        t_tag = _text(te.css_first(".m-item-team-tag"))
        t_logo_img = te.css_first(".m-item-logo img") or te.css_first("img")
        t_logo = normalize_image_url(_attr(t_logo_img, "src"))
        teams.append({"name": t_name, "tag": t_tag, "logo": t_logo})

    while len(teams) < 2:
        teams.append({"name": "", "tag": "", "logo": ""})

    # Event name
    event_elem = item.css_first(".m-item-event")
    event_lines = [
        ln.strip()
        for ln in (_text(event_elem)).split("\n")
        if ln.strip()
    ]
    event = event_lines[-1] if event_lines else ""

    # Date
    date_elem = item.css_first(".m-item-date")
    date = _text(date_elem)

    return {
        "match_id": match_id,
        "url": match_url,
        "event": event,
        "date": date,
        "team1": teams[0],
        "team2": teams[1],
        "score": score,
        "result": result,
    }


# ---------------------------------------------------------------------------
# Transaction helpers (used by vlr_team_transactions)
# ---------------------------------------------------------------------------


def _parse_transaction_item(item) -> dict | None:
    """
    Parse one transaction row from the team transactions page.

    VLR renders transactions as table rows or card items.  The selector
    priority order is:
      1. tr.txn-item  (table row layout)
      2. .wf-card containing player + action text  (card layout)

    Both layouts are handled defensively.
    """
    # --- Table row layout ---
    date = ""
    action = ""
    player_name = ""
    player_id = ""
    player_url = ""
    player_avatar = ""
    player_country = ""
    role = ""

    # Date cell
    date_cell = (
        item.css_first("td.txn-item-date")
        or item.css_first(".txn-date")
        or item.css_first(".ge-text-light")
    )
    date = _text(date_cell)

    # Action cell (join / leave / benched / inactive …)
    action_cell = (
        item.css_first("td.txn-item-action")
        or item.css_first(".txn-action")
        or item.css_first(".txn-item-action")
    )
    action = _text(action_cell).lower()

    # Player anchor
    player_anchor = item.css_first("a[href*='/player/']")
    if not player_anchor:
        player_anchor = item.css_first("a")
    if player_anchor:
        p_href = _attr(player_anchor, "href")
        player_id, _ = parse_href_id_slug(p_href)
        player_url = build_full_url(p_href)

    # Player name — prefer the explicit alias selector
    name_elem = (
        item.css_first(".txn-player-alias")
        or item.css_first(".ge-text")
        or item.css_first("b")
        or player_anchor
    )
    player_name = _text(name_elem)

    # Avatar
    avatar_img = item.css_first("img")
    if avatar_img:
        player_avatar = normalize_image_url(_attr(avatar_img, "src"))

    # Country
    flag_elem = item.css_first(".flag")
    player_country = extract_region_from_flag(flag_elem)

    # Role / position
    role_elem = (
        item.css_first(".txn-player-role")
        or item.css_first(".txn-item-role")
        or item.css_first("td:last-child")
    )
    role = _text(role_elem)
    # Avoid duplicating the action text as the role
    if role and role.lower() == action.lower():
        role = ""

    if not player_name and not player_id and not date:
        return None

    return {
        "date": date,
        "action": action,
        "player": {
            "name": player_name,
            "id": player_id,
            "url": player_url,
            "avatar": player_avatar,
            "country": player_country,
        },
        "role": role,
    }


# ---------------------------------------------------------------------------
# Public scraper functions
# ---------------------------------------------------------------------------


@handle_scraper_errors
async def vlr_team(team_id: str) -> dict:
    """
    Scrape a team profile page from VLR.GG.

    Fetches ``/team/{team_id}`` and extracts the team header, rating block,
    roster, and event placement history.

    Args:
        team_id: Numeric VLR.GG team identifier (e.g. ``"2593"``).

    Returns:
        Standard ``{"data": {"status": int, "segments": [...]}}`` response
        dict containing a single team segment on success.

    Example::

        result = await vlr_team("2593")
        team = result["data"]["segments"][0]
        print(team["name"], team["roster"])
    """
    cache_key = ("team", team_id)
    cached = cache_manager.get(CACHE_TTL_TEAM, *cache_key)
    if cached is not None:
        return cached

    url = f"{VLR_BASE_URL}/team/{team_id}"
    client = get_http_client()
    resp = await client.get(url)
    status = resp.status_code

    if status != 200:
        logger.warning("Non-200 response %d for team %s", status, team_id)
        data = {"data": {"status": status, "segments": []}}
        return data

    html = HTMLParser(resp.text)

    header_info = _parse_team_header(html, team_id)
    rating = _parse_rating_info(html)
    roster = _parse_roster(html)
    event_placements, total_winnings = _parse_event_placements(html)

    segment = {
        **header_info,
        "rating": rating,
        "roster": roster,
        "event_placements": event_placements,
        "total_winnings": total_winnings,
    }

    data = {"data": {"status": status, "segments": [segment]}}
    cache_manager.set(CACHE_TTL_TEAM, data, *cache_key)
    return data


@handle_scraper_errors
async def vlr_team_matches(team_id: str, page: int = 1) -> dict:
    """
    Scrape the paginated match history for a team from VLR.GG.

    Fetches ``/team/matches/{team_id}/?page={page}`` and extracts each
    match row with teams, scores, event name, date, and result.

    Args:
        team_id: Numeric VLR.GG team identifier.
        page: Page number (1-indexed).  Defaults to ``1``.

    Returns:
        Standard response dict with a ``"segments"`` list of match dicts and
        a ``"meta"`` key carrying the current page number.

    Example::

        result = await vlr_team_matches("2593", page=1)
        matches = result["data"]["segments"]
    """
    # Clamp page to a sane range
    page = max(1, min(page, 100))

    cache_key = ("team_matches", team_id, page)
    cached = cache_manager.get(CACHE_TTL_TEAM_MATCHES, *cache_key)
    if cached is not None:
        return cached

    url = f"{VLR_BASE_URL}/team/matches/{team_id}/?page={page}"
    client = get_http_client()
    resp = await client.get(url)
    status = resp.status_code

    if status != 200:
        logger.warning(
            "Non-200 response %d for team matches %s page %d", status, team_id, page
        )
        data = {"data": {"status": status, "segments": [], "meta": {"page": page}}}
        return data

    html = HTMLParser(resp.text)
    matches: list[dict] = []

    # VLR team match pages use .wf-card elements that contain .m-item anchors.
    # Try the most specific selector first, then progressively widen.
    selectors = [
        "a.wf-card.m-item",
        ".wf-card a.m-item",
        "a.m-item",
    ]
    items = []
    for sel in selectors:
        items = html.css(sel)
        if items:
            break

    # If the above all fail, look for any card-anchors inside the main content
    if not items:
        content = html.css_first(".col.mod-1") or html.css_first(".col")
        if content:
            items = content.css("a[href*='/match/']") or content.css("a[href*='/matches/']")

    for item in items:
        try:
            parsed = _parse_team_match_item(item)
            if parsed is not None:
                matches.append(parsed)
        except Exception as exc:
            logger.warning(
                "Failed to parse match item for team %s: %s", team_id, exc
            )

    data = {
        "data": {
            "status": status,
            "segments": matches,
            "meta": {"page": page},
        }
    }
    cache_manager.set(CACHE_TTL_TEAM_MATCHES, data, *cache_key)
    return data


@handle_scraper_errors
async def vlr_team_transactions(team_id: str) -> dict:
    """
    Scrape the roster transaction history for a team from VLR.GG.

    Fetches ``/team/transactions/{team_id}/`` and extracts each transaction
    entry with date, action type, player info, and role.

    Args:
        team_id: Numeric VLR.GG team identifier.

    Returns:
        Standard response dict with a ``"segments"`` list of transaction dicts.

    Example::

        result = await vlr_team_transactions("2593")
        txns = result["data"]["segments"]
    """
    cache_key = ("team_transactions", team_id)
    cached = cache_manager.get(CACHE_TTL_TEAM_TRANSACTIONS, *cache_key)
    if cached is not None:
        return cached

    url = f"{VLR_BASE_URL}/team/transactions/{team_id}/"
    client = get_http_client()
    resp = await client.get(url)
    status = resp.status_code

    if status != 200:
        logger.warning(
            "Non-200 response %d for team transactions %s", status, team_id
        )
        data = {"data": {"status": status, "segments": []}}
        return data

    html = HTMLParser(resp.text)
    transactions: list[dict] = []

    # Selector priority: table rows, then generic card items
    selectors = [
        "tr.txn-item",
        ".txn-item",
        ".wf-card .txn-item",
    ]
    items = []
    for sel in selectors:
        items = html.css(sel)
        if items:
            break

    # Fallback: scan every table row that has a player link inside it
    if not items:
        items = [
            row
            for row in html.css("tr")
            if row.css_first("a[href*='/player/']")
        ]

    # Second fallback: wf-card based layout (some older team pages)
    if not items:
        content = html.css_first(".col.mod-1") or html.css_first(".col")
        if content:
            items = [
                card
                for card in content.css(".wf-card")
                if card.css_first("a[href*='/player/']")
            ]

    for item in items:
        try:
            parsed = _parse_transaction_item(item)
            if parsed is not None:
                transactions.append(parsed)
        except Exception as exc:
            logger.warning(
                "Failed to parse transaction item for team %s: %s", team_id, exc
            )

    data = {"data": {"status": status, "segments": transactions}}
    cache_manager.set(CACHE_TTL_TEAM_TRANSACTIONS, data, *cache_key)
    return data
