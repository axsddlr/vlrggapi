"""
HTML parsers for VLR.GG team profile pages.

Covers team header, rating, roster, event placements,
match history items, transaction log items, grouped roster,
and upcoming fixture cards.
"""
import logging
import re

from utils.html_parsers import (
    HTMLParser,
    build_full_url,
    extract_region_from_flag,
    infer_platform,
    normalize_image_url,
    parse_href_id_slug,
)

logger = logging.getLogger(__name__)


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


# ---------------------------------------------------------------------------
# Team profile parsers
# ---------------------------------------------------------------------------


def _parse_team_header(html: HTMLParser, team_id: str) -> dict:
    """Extract team identity fields from the .team-header block."""
    header = html.css_first(".team-header")

    name_block = header.css_first(".team-header-name") if header else None
    name = _text(name_block.css_first("h1") if name_block else None)
    if not name:
        name = _text(html.css_first("h1.wf-title"))

    tag = _text(name_block.css_first("h2") if name_block else None)

    successor_elem = html.css_first(".team-header-name-successor")
    successor = _text(successor_elem)

    logo_img = header.css_first("img") if header else None
    logo = normalize_image_url(_attr(logo_img, "src"))

    country_block = html.css_first(".team-header-country")
    flag_elem = country_block.css_first(".flag") if country_block else None
    country_code = extract_region_from_flag(flag_elem)
    country_name = ""
    if country_block:
        country_name = _text(country_block)

    social_links = _parse_social_links(html)

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
    """Collect all social / external links from the team header link bar."""
    links: list[dict] = []
    seen: set[str] = set()

    links_container = html.css_first(".team-header-links")
    anchors = links_container.css("a") if links_container else []

    for anchor in html.css("a.social"):
        if anchor not in anchors:
            anchors.append(anchor)

    for anchor in anchors:
        href = _attr(anchor, "href").strip()
        if not href or href in seen:
            continue
        seen.add(href)

        css_class = _attr(anchor, "class", "")
        platform = ""
        for part in css_class.split():
            if part.startswith("mod-") and part != "mod-":
                platform = part[4:]
                break

        if not platform:
            platform = infer_platform(href)

        links.append({"platform": platform, "url": href})

    return links


def _parse_rating_info(html: HTMLParser) -> dict:
    """Extract team ranking / rating block data."""
    rating_container = html.css_first(".team-rating-info")
    if not rating_container:
        return {"rank": "", "rating": "", "peak_rating": "", "streak": ""}

    rank_section = rating_container.css_first(".team-rating-info-section.mod-rank")
    rating_section = rating_container.css_first(".team-rating-info-section.mod-rating")
    streak_section = rating_container.css_first(".team-rating-info-section.mod-streak")

    rank = _text(rank_section.css_first(".rank-num") if rank_section else None)
    rating = _text(rating_section.css_first(".rating-num") if rating_section else None)
    peak_rating = _text(rating_section.css_first(".rating-num-peak") if rating_section else None)
    streak_raw = _text(streak_section)
    streak = re.sub(r"^(?:Record|Streak)\s*", "", streak_raw, flags=re.IGNORECASE).strip()

    return {"rank": rank, "rating": rating, "peak_rating": peak_rating, "streak": streak}


def _parse_roster(html: HTMLParser) -> list[dict]:
    """Extract the full roster including staff members."""
    roster: list[dict] = []
    seen_ids: set[str] = set()

    container = html.css_first(".team-summary-container-1")
    if not container:
        for item in html.css(".team-roster-item"):
            player = _parse_single_roster_item(item, is_staff=False)
            if player["alias"] and player["alias"] not in seen_ids:
                seen_ids.add(player["alias"])
                roster.append(player)
        return roster

    is_staff = False
    for node in container.css("*"):
        css_class = node.attributes.get("class", "") or ""

        if "wf-label" in css_class and "team-roster-item" not in css_class:
            label_text = node.text(strip=True).lower()
            if "staff" in label_text or "coach" in label_text:
                is_staff = True
            elif any(k in label_text for k in ("player", "roster", "active")):
                is_staff = False
            continue

        if "team-roster-item" in css_class and "team-roster-item-" not in css_class:
            player = _parse_single_roster_item(node, is_staff)
            dedup_key = player["alias"] or player["id"]
            if dedup_key and dedup_key not in seen_ids:
                seen_ids.add(dedup_key)
                roster.append(player)

    return roster


def _parse_single_roster_item(item, is_staff: bool) -> dict:
    """Parse one .team-roster-item node into a player/staff dict."""
    anchor = item.css_first("a")
    href = _attr(anchor, "href")
    player_id, _ = parse_href_id_slug(href)
    player_url = build_full_url(href)

    alias = _text(item.css_first(".team-roster-item-name-alias"))
    real_name = _text(item.css_first(".team-roster-item-name-real"))

    avatar_img = item.css_first(".team-roster-item-img img")
    if not avatar_img:
        avatar_img = item.css_first("img")
    avatar = normalize_image_url(_attr(avatar_img, "src"))

    flag_elem = item.css_first(".flag")
    country = extract_region_from_flag(flag_elem)

    is_captain = item.css_first(".fa.fa-star") is not None

    role = ""
    name_block = item.css_first(".team-roster-item-name")
    if name_block:
        full_name_text = _text(name_block)
        stripped = full_name_text.replace(alias, "").replace(real_name, "").strip()
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
    """Parse event placement history from the team results section."""
    placements: list[dict] = []
    total_winnings = ""

    container = html.css_first(".team-summary-container-2")
    if not container:
        container = html.css_first(".team-summary-container")

    if not container:
        return placements, total_winnings

    for wf_card in container.css(".wf-card"):
        raw = _text(wf_card)
        match = re.search(r"\$([\d,]+(?:\.\d+)?)", raw)
        if match and not total_winnings:
            total_winnings = "$" + match.group(1)

    for event_anchor in container.css("a.team-event-item"):
        href = _attr(event_anchor, "href")
        if not href:
            continue
        event_url = build_full_url(href)

        event_name_elem = (
            event_anchor.css_first(".wf-title-med")
            or event_anchor.css_first(".event-item-title")
            or event_anchor.css_first(".text-of")
            or event_anchor.css_first("div")
        )
        event_name = _text(event_name_elem) if event_name_elem else _text(event_anchor)

        series_elem = event_anchor.css_first(".team-event-item-series")
        series = _text(series_elem)

        full_text = _text(event_anchor)
        placement = _extract_placement(full_text)
        prize = _extract_prize_from_text(full_text)

        all_divs = event_anchor.css("div")
        date = _text(all_divs[-1]) if all_divs else ""

        if event_name or placement:
            placements.append({
                "event": _normalize_ws(event_name),
                "series": _normalize_ws(series),
                "placement": _normalize_ws(placement),
                "prize": _normalize_ws(prize),
                "date": _normalize_ws(date),
                "url": event_url,
            })

    return placements, total_winnings


def _normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _extract_placement(text: str) -> str:
    if not text:
        return ""
    match = re.search(
        r"\b(\d+(?:st|nd|rd|th)(?:\s*[-–]\s*\d+(?:st|nd|rd|th))?)\b",
        text,
        re.IGNORECASE,
    )
    return match.group(1) if match else ""


def _extract_prize_from_text(text: str) -> str:
    if not text:
        return ""
    match = re.search(
        r"\$(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:[KMkm])?",
        text,
    )
    if not match:
        return ""
    return match.group(0)


def _extract_date_from_text(text: str) -> str:
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
# Match history item parser
# ---------------------------------------------------------------------------


def _parse_team_match_item(item) -> dict | None:
    """Parse one match row from the team match history page."""
    anchor = item if item.tag == "a" else item.css_first("a")
    href = _attr(anchor, "href") if anchor else _attr(item, "href")
    if not href:
        return None

    match_id, _ = parse_href_id_slug(href)
    match_url = build_full_url(href)

    item_class = _attr(item, "class", "")
    result_elem = item.css_first(".m-item-result")
    result_class = _attr(result_elem, "class", "") if result_elem else ""
    result = ""
    if "mod-win" in result_class or "mod-win" in item_class:
        result = "win"
    elif "mod-loss" in result_class or "mod-loss" in item_class:
        result = "loss"

    score = _text(result_elem)

    team_elems = item.css(".m-item-team")
    logo_imgs = item.css(".m-item-logo img")
    teams: list[dict] = []
    for i, te in enumerate(team_elems):
        t_name = _text(te.css_first(".m-item-team-name"))
        t_tag = _text(te.css_first(".m-item-team-tag"))
        t_logo_img = logo_imgs[i] if i < len(logo_imgs) else None
        t_logo = normalize_image_url(_attr(t_logo_img, "src")) if t_logo_img else ""
        teams.append({"name": t_name, "tag": t_tag, "logo": t_logo})

    while len(teams) < 2:
        teams.append({"name": "", "tag": "", "logo": ""})

    event_elem = item.css_first(".m-item-event")
    event_lines = [
        ln.strip() for ln in (_text(event_elem)).split("\n") if ln.strip()
    ]
    event = event_lines[-1] if event_lines else ""

    date_elem = item.css_first(".m-item-date")
    raw = _text(date_elem) if date_elem else ""
    m = re.match(r"(\d{4}/\d{2}/\d{2})", raw)
    date = m.group(1) if m else ""
    time = raw[m.end():].strip() if m else raw.strip()

    return {
        "match_id": match_id,
        "url": match_url,
        "event": event,
        "date": date,
        "time": time,
        "team1": teams[0],
        "team2": teams[1],
        "score": score,
        "result": result,
    }


# ---------------------------------------------------------------------------
# Transaction item parser
# ---------------------------------------------------------------------------


def _parse_transaction_item(item) -> dict | None:
    """Parse one transaction row from the team transactions page."""
    date_cell = (
        item.css_first("td.txn-item-date")
        or item.css_first(".txn-date")
        or item.css_first(".ge-text-light")
    )
    date = _text(date_cell)

    action_cell = (
        item.css_first("td.txn-item-action")
        or item.css_first(".txn-action")
        or item.css_first(".txn-item-action")
    )
    action = _text(action_cell).lower()

    player_anchor = item.css_first("a[href*='/player/']")
    if not player_anchor:
        player_anchor = item.css_first("a")
    player_id = ""
    player_url = ""
    if player_anchor:
        p_href = _attr(player_anchor, "href")
        player_id, _ = parse_href_id_slug(p_href)
        player_url = build_full_url(p_href)

    name_elem = (
        item.css_first(".txn-player-alias")
        or item.css_first(".ge-text")
        or item.css_first("b")
        or player_anchor
    )
    player_name = _text(name_elem)

    avatar_img = item.css_first("img")
    player_avatar = ""
    if avatar_img:
        player_avatar = normalize_image_url(_attr(avatar_img, "src"))

    flag_elem = item.css_first(".flag")
    player_country = extract_region_from_flag(flag_elem)

    role_elem = (
        item.css_first(".txn-player-role")
        or item.css_first(".txn-item-role")
        or item.css_first("td:last-child")
    )
    role = _text(role_elem)
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
# Grouped roster parser — splits roster into active / staff / former / benched
# ---------------------------------------------------------------------------


def _parse_grouped_roster(html: HTMLParser) -> dict:
    """Parse the team roster into labelled groups.

    Walks the children of ``.team-summary-container-1`` and assigns each
    ``.team-roster-item`` to one of four buckets: ``active``, ``staff``,
    ``former``, or ``benched``, switching on ``.wf-label`` text.

    Returns:
        ``{"active": [...], "staff": [...], "former": [...], "benched": [...]}``
    """
    groups: dict[str, list[dict]] = {
        "active": [],
        "staff": [],
        "former": [],
        "benched": [],
    }
    seen_ids: set[str] = set()
    current_group = "active"

    container = html.css_first(".team-summary-container-1")
    if not container:
        for item in html.css(".team-roster-item"):
            player = _parse_single_roster_item(item, is_staff=False)
            dedup_key = player["alias"] or player["id"]
            if dedup_key and dedup_key not in seen_ids:
                seen_ids.add(dedup_key)
                groups["active"].append(player)
        return groups

    for node in container.css("*"):
        css_class = node.attributes.get("class", "") or ""

        # Section headers — update current_group when a label is found
        if "wf-label" in css_class and "team-roster-item" not in css_class:
            label = node.text(strip=True).lower()
            if any(kw in label for kw in ("staff", "coach", "analyst", "manager")):
                current_group = "staff"
            elif any(kw in label for kw in ("former", "past", "previous")):
                current_group = "former"
            elif any(kw in label for kw in ("bench", "inactive", "reserve", "substitute")):
                current_group = "benched"
            elif any(kw in label for kw in ("player", "roster", "active", "current")):
                current_group = "active"
            continue

        # Roster items — add to the active group
        if "team-roster-item" in css_class and "team-roster-item-" not in css_class:
            is_staff = current_group == "staff"
            player = _parse_single_roster_item(node, is_staff)
            dedup_key = player["alias"] or player["id"]
            if dedup_key and dedup_key not in seen_ids:
                seen_ids.add(dedup_key)
                groups[current_group].append(player)

    return groups


# ---------------------------------------------------------------------------
# Team fixture card parser — single upcoming match from the team page sidebar
# ---------------------------------------------------------------------------


def _parse_team_fixture(item) -> dict | None:
    """Parse a single upcoming-match card from a team profile page.

    Extracts match id, url, event name, date, time, eta, and both team
    identities from one ``.m-item`` or ``a[href*='/match/']`` node.

    Returns ``None`` when the node lacks a match url.
    """
    anchor = item if item.tag == "a" else item.css_first("a")
    href = _attr(anchor, "href") if anchor else _attr(item, "href")
    if not href:
        return None

    match_id, _ = parse_href_id_slug(href)
    match_url = build_full_url(href)

    team_elems = item.css(".m-item-team")
    logo_imgs = item.css(".m-item-logo img")
    teams: list[dict] = []
    for i, te in enumerate(team_elems):
        t_name = _text(te.css_first(".m-item-team-name"))
        t_tag = _text(te.css_first(".m-item-team-tag"))
        t_logo_img = logo_imgs[i] if i < len(logo_imgs) else None
        t_logo = normalize_image_url(_attr(t_logo_img, "src")) if t_logo_img else ""
        teams.append({"name": t_name, "tag": t_tag, "logo": t_logo})

    while len(teams) < 2:
        teams.append({"name": "", "tag": "", "logo": ""})

    event_elem = item.css_first(".m-item-event")
    event_lines = [
        ln.strip() for ln in (_text(event_elem)).split("\n") if ln.strip()
    ] if event_elem else []
    event = event_lines[-1] if event_lines else ""

    date_elem = item.css_first(".m-item-date")
    raw = _text(date_elem) if date_elem else ""
    m = re.match(r"(\d{4}/\d{2}/\d{2})", raw)
    date = m.group(1) if m else ""
    time = raw[m.end():].strip() if m else raw.strip()

    eta_elem = item.css_first(".h-match-eta") or item.css_first(".match-item-eta")
    eta = _text(eta_elem)

    return {
        "match_id": match_id,
        "url": match_url,
        "event": event,
        "date": date,
        "time": time,
        "eta": eta,
        "team1": teams[0],
        "team2": teams[1],
    }
