"""
Scraper for individual VLR.GG event detail pages.

Extracts event header info, prize pool breakdown, participating teams,
and group/stage standings tables.
"""
import logging

from utils.cache_manager import cache_manager
from utils.constants import CACHE_TTL_EVENTS, VLR_BASE_URL
from utils.error_handling import handle_scraper_errors, raise_for_upstream_status
from utils.html_parsers import HTMLParser, extract_text_content, normalize_image_url, parse_href_id_slug, parse_html
from utils.http_client import fetch_with_retries, get_http_client
from utils.id_mapper import id_mapper

logger = logging.getLogger(__name__)


def _parse_event_header(html: HTMLParser) -> dict:
    """Extract event name, series, dates, prize pool, location, and logo.

    Supports both the new VLR layout (event-header-main) and the legacy
    layout (event-desc-inner / event-desc-item).
    """
    series = ""
    name = ""
    subtitle = ""
    dates = ""
    prize = ""
    location = ""
    logo = ""

    header = html.css_first(".event-header") or html.css_first(".wf-card")
    if not header:
        return {"name": name, "series": series, "subtitle": subtitle,
                "dates": dates, "prize": prize, "location": location, "logo": logo}

    logo_elem = header.css_first(".event-header-thumb img") or header.css_first("img")
    if logo_elem:
        logo = normalize_image_url(logo_elem.attributes.get("src", ""))

    main = header.css_first(".event-header-main")
    if main:
        bc = main.css_first(".event-header-main-bc")
        if bc:
            series_link = bc.css_first("a")
            if series_link:
                series = extract_text_content(series_link)

        title = main.css_first("h1.event-header-main-title")
        if title:
            name = extract_text_content(title)

        sub = main.css_first("h2.event-header-main-desc")
        if sub:
            subtitle = extract_text_content(sub)

        meta = main.css_first(".event-header-main-meta")
        if meta:
            child = meta.child
            while child is not None:
                if hasattr(child, 'tag') and child.tag == "div":
                    label_elem = child.css_first(".label")
                    if label_elem:
                        label = extract_text_content(label_elem).rstrip(":").lower()
                        value_elem = child.css_first(".value")
                        value = extract_text_content(value_elem) if value_elem else ""
                        if label == "dates":
                            dates = value
                        elif label == "prize":
                            prize = value
                        elif label in ("location", "venue"):
                            location = value
                child = child.next
    else:
        desc_inner = header.css_first(".event-desc-inner")
        if desc_inner:
            series_link = desc_inner.css_first("a")
            if series_link:
                series = extract_text_content(series_link)

        title = header.css_first("h1.wf-title")
        if title:
            name = extract_text_content(title)

        sub = header.css_first(".event-desc-subtitle")
        if sub:
            subtitle = extract_text_content(sub)

        for item in header.css(".event-desc-item"):
            label_elem = item.css_first(".event-desc-item-label")
            value_elem = item.css_first(".event-desc-item-value")
            if not label_elem or not value_elem:
                continue
            label = extract_text_content(label_elem).rstrip(":")
            value = extract_text_content(value_elem)
            if label.lower() == "dates":
                dates = value
            elif label.lower() == "prize":
                prize = value
            elif label.lower() in ("location", "venue"):
                location = value

    return {
        "name": name,
        "series": series,
        "subtitle": subtitle,
        "dates": dates,
        "prize": prize,
        "location": location,
        "logo": logo,
    }


def _parse_prizes(html: HTMLParser) -> list[dict]:
    """Parse the prize breakdown table from the event page."""
    prizes: list[dict] = []

    # The prize table uses div.wf-ptable with div.row elements, inside a
    # .wf-card.mod-dark. Group tables and group match cards are mod-dark
    # cards too and come first on group-stage views, so take the first
    # mod-dark card that actually holds a ptable.
    ptable = None
    for card in html.css(".wf-card.mod-dark"):
        ptable = card.css_first(".wf-ptable")
        if ptable:
            break
    if not ptable:
        return prizes

    rows = ptable.css(".row")
    for row in rows[1:]:  # skip header row
        cells = row.css(".cell")
        if len(cells) < 3:
            continue

        placement = extract_text_content(cells[0])
        amount = extract_text_content(cells[1])

        # Team cell: contains an <a> link with name and optional region
        team_name = ""
        team_id = ""
        team_logo = ""
        team_region = ""

        team_link = cells[2].css_first("a")
        if team_link:
            href = team_link.attributes.get("href", "")
            team_id, _ = parse_href_id_slug(href)
            name_div = team_link.css_first(".text-of")
            if name_div:
                region_div = name_div.css_first(".ge-text-light")
                if region_div:
                    team_name = extract_text_content(name_div).replace(extract_text_content(region_div), "").strip()
                    team_region = extract_text_content(region_div)
                else:
                    team_name = extract_text_content(name_div)
            else:
                team_name = extract_text_content(team_link)
            img = team_link.css_first("img")
            if img:
                team_logo = normalize_image_url(img.attributes.get("src", ""))

        prizes.append({
            "placement": placement,
            "amount": amount,
            "team": {
                "id": team_id,
                "name": team_name,
                "logo": team_logo,
                "region": team_region,
            },
        })
        id_mapper.register_team(team_name, team_id)

    return prizes


def _parse_event_teams(html: HTMLParser) -> list[dict]:
    """Parse participating teams from event-team cards."""
    teams: list[dict] = []

    for card in html.css(".wf-card.event-team"):
        # Team name link
        name_link = card.css_first(".event-team-name")
        team_name = ""
        team_id = ""
        if name_link:
            team_name = extract_text_content(name_link)
            href = name_link.attributes.get("href", "")
            team_id, _ = parse_href_id_slug(href)

        # Players
        players: list[dict] = []
        for player_link in card.css(".event-team-players-item"):
            href = player_link.attributes.get("href", "")
            p_id, _ = parse_href_id_slug(href)
            p_name = extract_text_content(player_link)
            # Parse flag class (e.g. "flag mod-us")
            flag = ""
            flag_elem = player_link.css_first(".flag")
            if flag_elem:
                flag_class = flag_elem.attributes.get("class", "")
                flag = flag_class.replace("flag ", "").replace(" mod-", "_")
            players.append({"id": p_id, "name": p_name, "flag": flag})

        # Qualification note
        note = ""
        note_elem = card.css_first(".event-team-note")
        if note_elem:
            note_link = note_elem.css_first("a")
            if note_link:
                note = extract_text_content(note_link)

        teams.append({
            "id": team_id,
            "name": team_name,
            "players": players,
            "qualification": note,
        })
        id_mapper.register_team(team_name, team_id)
        for p in players:
            id_mapper.register_team(p["name"], "")

    return teams


def _parse_standings(html: HTMLParser) -> list[dict]:
    """Parse group/stage standings tables from the event page.

    VLR uses div.wf-ptable elements inside .wf-card containers for standings.
    Handles variable column counts (3-column groups, 5/6-column full tables).
    """
    standings: list[dict] = []

    for card in html.css(".wf-card"):
        ptable = card.css_first(".wf-ptable")
        if not ptable:
            continue
        # Skip the prize table (already handled in _parse_prizes)
        parent_classes = card.attributes.get("class", "")
        if "mod-dark" in parent_classes:
            continue

        # Check for a stage/group label before the table
        stage = ""
        label_elem = card.css_first(".wf-label") or card.css_first("h2")
        if label_elem:
            stage = extract_text_content(label_elem)

        # Parse headers
        header_row = ptable.css_first(".row")
        if not header_row:
            continue
        headers: list[str] = []
        for cell in header_row.css(".cell"):
            headers.append(extract_text_content(cell))

        if not headers:
            continue

        # Parse data rows
        rows: list[dict[str, str]] = []
        for row in ptable.css(".row")[1:]:
            cells = row.css(".cell")
            if len(cells) < 1:
                continue
            row_data: dict[str, str] = {}
            for idx, cell in enumerate(cells):
                label = headers[idx] if idx < len(headers) else str(idx)
                # Team column may have an anchor with name
                team_link = cell.css_first("a")
                if team_link and idx == 0:
                    row_data[label] = extract_text_content(team_link)
                else:
                    row_data[label] = extract_text_content(cell)
            rows.append(row_data)

        standings.append({"stage": stage, "columns": headers, "rows": rows})

    standings.extend(_parse_group_tables(html))
    return standings


def _preceding_label(node, max_depth: int = 4) -> str:
    """Text of the nearest .wf-label before ``node`` (checking up to ``max_depth`` ancestors)."""
    current = node
    for _ in range(max_depth):
        sibling = current.prev
        while sibling is not None:
            if sibling.tag and "wf-label" in (sibling.attributes.get("class") or ""):
                return extract_text_content(sibling)
            sibling = sibling.prev
        current = current.parent
        if current is None:
            break
    return ""


def _parse_group_tables(html: HTMLParser) -> list[dict]:
    """Parse group / round-robin standings (table.wf-table.mod-group).

    Each table sits under a stage label ("Round Robin", "Group Stage"); a
    multi-group stage names the group in the table's th.mod-title.
    """
    standings: list[dict] = []

    for table in html.css("table.wf-table.mod-group"):
        header_cells = table.css("thead th")
        if not header_cells:
            continue
        group = extract_text_content(header_cells[0])
        # The title th spans the logo and team columns
        columns = ["Team"] + [extract_text_content(th) for th in header_cells[1:]]

        rows: list[dict[str, str]] = []
        for tr in table.css("tbody tr"):
            team_link = tr.css_first("a.event-group-team")
            if not team_link:
                continue
            name_elem = team_link.css_first(".event-group-team-name") or team_link
            team_name = extract_text_content(name_elem)
            region_elem = name_elem.css_first(".event-group-team-region")
            if region_elem:
                team_name = team_name.replace(extract_text_content(region_elem), "").strip()

            cells = tr.css("td")[2:]  # skip the logo and team cells
            row_data = {"Team": team_name}
            for label, cell in zip(columns[1:], cells, strict=False):
                row_data[label] = extract_text_content(cell)
            rows.append(row_data)

        standings.append({
            "stage": _preceding_label(table),
            "group": group,
            "columns": columns,
            "rows": rows,
        })

    return standings


@handle_scraper_errors
async def vlr_event_detail(event_id: str) -> dict:
    """Fetch full event detail: header, prizes, teams, and standings.

    Args:
        event_id: Numeric VLR.GG event ID.
    """
    async def build():
        base_url = f"{VLR_BASE_URL}/event/{event_id}"
        client = get_http_client()
        resp = await fetch_with_retries(base_url, client=client)
        status = resp.status_code
        raise_for_upstream_status(status, f"event detail {event_id}")

        html = parse_html(resp.text)

        header = _parse_event_header(html)
        prizes = _parse_prizes(html)
        teams = _parse_event_teams(html)
        standings = _parse_standings(html)

        data = {
            "data": {
                "status": status,
                "segments": {
                    "event": header,
                    "prizes": prizes,
                    "teams": teams,
                    "standings": standings,
                },
            }
        }
        return data

    return await cache_manager.get_or_create_async(
        CACHE_TTL_EVENTS, build, "event_detail", event_id
    )
