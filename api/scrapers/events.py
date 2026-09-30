import logging
import re
from datetime import UTC, datetime, timedelta

from utils.cache_manager import cache_manager
from utils.constants import CACHE_TTL_EVENT_MATCHES, CACHE_TTL_EVENTS, VLR_BASE_URL, VLR_EVENTS_URL
from utils.error_handling import handle_scraper_errors, upstream_error_payload
from utils.html_parsers import (
    build_full_url,
    extract_date_range,
    extract_prize_value,
    extract_region_from_flag,
    extract_text_content,
    normalize_image_url,
    parse_eta_to_timedelta,
    parse_href_id_slug,
    parse_html,
    parse_local_datetime,
)
from utils.http_client import fetch_with_retries, get_http_client

logger = logging.getLogger(__name__)


def _parse_event_cards(container) -> list:
    """Parse all event cards from a section container."""
    events = []
    for event_item in container.css("a.event-item"):
        title = extract_text_content(event_item.css_first(".event-item-title"))
        event_status = extract_text_content(event_item.css_first(".event-item-desc-item-status"))
        prize = extract_prize_value(event_item.css_first(".event-item-desc-item.mod-prize"))
        dates = extract_date_range(event_item.css_first(".event-item-desc-item.mod-dates"))
        region = extract_region_from_flag(event_item.css_first(".event-item-desc-item.mod-location .flag"))
        img_elem = event_item.css_first(".event-item-thumb img")
        thumb = normalize_image_url(img_elem.attributes.get("src", "") if img_elem else "")
        href = event_item.attributes.get("href", "")
        event_id, _ = parse_href_id_slug(href)
        full_url = build_full_url(href)
        events.append({
            "title": title,
            "event_id": event_id,
            "status": event_status,
            "prize": prize,
            "dates": dates,
            "region": region,
            "thumb": thumb,
            "url_path": full_url,
        })
    return events


def _parse_home_sidebar_events_by_label(container, label: str) -> list:
    """Parse events from a js-home-events sidebar section by header label (live, ongoing, etc.)."""
    events = []
    for section_header in container.css("h1.wf-label.mod-sidebar"):
        if label.lower() not in section_header.text(strip=True).lower():
            continue
        items_wrapper = section_header.parent
        if not items_wrapper:
            continue
        card = items_wrapper.css_first("div.wf-module.wf-card.mod-sidebar")
        if not card:
            continue
        for event_item in card.css("a.event-item"):
            title_el = event_item.css_first(".event-item-name")
            title = title_el.text(strip=True) if title_el else ""

            img_el = event_item.css_first("img.event-item-icon")
            thumb = normalize_image_url(img_el.attributes.get("src", "") if img_el else "")

            href = event_item.attributes.get("href", "")
            event_id_str, _ = parse_href_id_slug(href)
            full_url = build_full_url(href)

            tag_els = event_item.css("div.event-item-tag")
            region = tag_els[0].text(strip=True) if tag_els else ""
            status_text = tag_els[1].text(strip=True) if len(tag_els) > 1 else ""

            events.append({
                "title": title,
                "event_id": event_id_str,
                "status": status_text,
                "region": region,
                "thumb": thumb,
                "url_path": full_url,
            })
    return events


@handle_scraper_errors
async def vlr_events(upcoming=True, completed=True, page=1, live=False):
    """
    Get Valorant events from VLR.GG

    Args:
        upcoming (bool): If True, include upcoming events
        completed (bool): If True, include completed events
        page (int): Page number for pagination (only applies to completed events)
        live (bool): If True, include live events from the homepage sidebar

    Returns:
        dict: Response with status code and events data
    """
    cache_key = ("events", upcoming, completed, page, live)

    async def build():
        if not upcoming and not completed and not live:
            show_upcoming = show_completed = True
            show_live = False
        else:
            show_upcoming, show_completed, show_live = upcoming, completed, live

        events = []
        status = 200

        if show_upcoming or show_completed:
            url = f"{VLR_EVENTS_URL}/?page={page}" if show_completed and page > 1 else VLR_EVENTS_URL

            client = get_http_client()
            resp = await fetch_with_retries(url, client=client)
            status = resp.status_code
            if status >= 400:
                return upstream_error_payload(status, "events")

            html = parse_html(resp.text)

            if show_upcoming:
                for section in html.css("div.wf-label.mod-large.mod-upcoming"):
                    parent = section.parent
                    if parent and parent.css("a.event-item"):
                        events.extend(_parse_event_cards(parent))

            if show_completed:
                for section in html.css("div.wf-label.mod-large.mod-completed"):
                    parent = section.parent
                    if parent and parent.css("a.event-item"):
                        events.extend(_parse_event_cards(parent))

        if show_live:
            client = get_http_client()
            home_resp = await fetch_with_retries(VLR_BASE_URL, client=client)
            if home_resp.status_code < 400:
                home_html = parse_html(home_resp.text)
                live_container = home_html.css_first("div.js-home-events")
                if live_container:
                    events.extend(_parse_home_sidebar_events_by_label(live_container, "live"))

        return {"data": {"status": status, "segments": events}}

    return await cache_manager.get_or_create_async(CACHE_TTL_EVENTS, build, *cache_key)


def _event_match_utc_offset(rows: list[tuple], now: datetime) -> timedelta | None:
    """Infer the timezone VLR rendered an event matches page in.

    VLR renders ``.match-item-time`` and the date headers in the viewer's
    timezone (chosen server-side, with no marker in the HTML), so the wall
    clock alone is not a reliable time. A countdown with minute precision
    (``15h 15m`` until an upcoming match, ``8h 45m`` since a completed one;
    no day part) pins that match's scheduled start to within a minute; the
    page offset is its wall clock minus that UTC start, rounded to 15 minutes.
    Returns None when no row qualifies.

    ``rows`` holds ``(local_datetime, eta_text, direction)`` tuples, where
    direction is 1 for upcoming, -1 for completed and 0 for anything else.
    """
    now_naive = now.astimezone(UTC).replace(tzinfo=None, second=0, microsecond=0)
    for local_dt, eta_text, direction in rows:
        if local_dt is None or direction == 0 or re.search(r"\d\s*[dw]", eta_text.lower()):
            continue
        delta = parse_eta_to_timedelta(eta_text)
        if delta is None:
            continue
        start_utc = now_naive + direction * delta
        offset_minutes = (local_dt - start_utc).total_seconds() / 60
        return timedelta(minutes=round(offset_minutes / 15) * 15)
    return None


@handle_scraper_errors
async def vlr_event_matches(event_id: str):
    """Get match list for a specific event from VLR.GG.

    Args:
        event_id: The numeric event ID from vlr.gg

    Returns:
        dict: Response with status code and match list data
    """
    cache_key = ("event_matches", event_id)

    async def build():
        url = f"{VLR_BASE_URL}/event/matches/{event_id}"
        client = get_http_client()
        resp = await fetch_with_retries(url, client=client)
        status = resp.status_code
        if status >= 400:
            return upstream_error_payload(status, f"event matches {event_id}")

        html = parse_html(resp.text)

        matches = []
        timing_rows = []
        current_date = ""

        for elem in html.css(".wf-label.mod-large, a.wf-module-item.match-item"):
            classes = elem.attributes.get("class", "")

            if "wf-label" in classes:
                # Direct text only: VLR appends a "Today"/"Yesterday" wf-tag span
                current_date = elem.text(deep=False, strip=True)
                continue

            href = elem.attributes.get("href", "")
            match_id, _ = parse_href_id_slug(href)
            match_url = build_full_url(href)

            team_elems = elem.css(".match-item-vs-team")
            teams = []
            for te in team_elems:
                name_el = te.css_first(".match-item-vs-team-name")
                score_el = te.css_first(".match-item-vs-team-score")
                name = name_el.text(strip=True) if name_el else "TBD"
                score = score_el.text(strip=True) if score_el else ""
                is_winner = "mod-winner" in te.attributes.get("class", "")
                teams.append({"name": name, "score": score, "is_winner": is_winner})

            while len(teams) < 2:
                teams.append({"name": "TBD", "score": "", "is_winner": False})

            series_el = elem.css_first(".match-item-event-series")
            event_series = series_el.text(strip=True) if series_el else ""
            # The stage ("Group Stage", "Playoffs") is the event cell's own text,
            # after the nested series div
            event_el = elem.css_first(".match-item-event")
            stage = event_el.text(deep=False, strip=True) if event_el else ""

            time_el = elem.css_first(".match-item-time")
            match_time = extract_text_content(time_el)

            status_el = elem.css_first(".ml-status")
            eta_el = elem.css_first(".ml-eta")
            match_status = ""
            if status_el:
                match_status = status_el.text(strip=True)
            elif eta_el:
                match_status = eta_el.text(strip=True)

            note_el = elem.css_first(".match-item-note")
            note = note_el.text(strip=True) if note_el else ""

            # Countdown direction: until an upcoming match, since a completed one
            ml_el = elem.css_first(".ml")
            ml_classes = ml_el.attributes.get("class", "") if ml_el else ""
            direction = 0
            if eta_el and "mod-completed" in ml_classes:
                direction = -1
            elif eta_el and "mod-live" not in ml_classes:
                direction = 1
            timing_rows.append(
                (parse_local_datetime(current_date, match_time), extract_text_content(eta_el), direction)
            )

            matches.append({
                "match_id": match_id,
                "url": match_url,
                "date": current_date,
                "time": match_time,
                "unix_timestamp": "",
                "status": match_status,
                "note": note,
                "stage": stage,
                "event_series": event_series,
                "team1": teams[0],
                "team2": teams[1],
            })

        offset = _event_match_utc_offset(timing_rows, datetime.now(UTC))
        if offset is not None:
            for match, (local_dt, _, _) in zip(matches, timing_rows, strict=True):
                if local_dt is not None:
                    match["unix_timestamp"] = (local_dt - offset).strftime("%Y-%m-%d %H:%M:%S")

        return {"data": {"status": status, "segments": matches}}

    return await cache_manager.get_or_create_async(
        CACHE_TTL_EVENT_MATCHES, build, *cache_key
    )
