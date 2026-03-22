import logging

from selectolax.parser import HTMLParser

from utils.http_client import fetch_with_retries, get_http_client
from utils.constants import VLR_BASE_URL, VLR_EVENTS_URL, CACHE_TTL_EVENTS, CACHE_TTL_EVENT_MATCHES
from utils.cache_manager import cache_manager
from utils.error_handling import handle_scraper_errors
from utils.html_parsers import (
    extract_text_content,
    extract_prize_value,
    extract_date_range,
    extract_region_from_flag,
    normalize_image_url,
    build_full_url,
    parse_href_id_slug,
)

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
        full_url = build_full_url(event_item.attributes.get("href", ""))
        events.append({
            "title": title,
            "status": event_status,
            "prize": prize,
            "dates": dates,
            "region": region,
            "thumb": thumb,
            "url_path": full_url,
        })
    return events


@handle_scraper_errors
async def vlr_events(upcoming=True, completed=True, page=1):
    """
    Get Valorant events from VLR.GG

    Args:
        upcoming (bool): If True, include upcoming events
        completed (bool): If True, include completed events
        page (int): Page number for pagination (only applies to completed events)

    Returns:
        dict: Response with status code and events data
    """
    cache_key = ("events", upcoming, completed, page)

    async def build():
        if not upcoming and not completed:
            show_upcoming = show_completed = True
        else:
            show_upcoming, show_completed = upcoming, completed

        url = f"{VLR_EVENTS_URL}/?page={page}" if show_completed and page > 1 else VLR_EVENTS_URL

        client = get_http_client()
        resp = await fetch_with_retries(url, client=client)
        html = HTMLParser(resp.text)
        status = resp.status_code

        events = []

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

        return {"data": {"status": status, "segments": events}}

    return await cache_manager.get_or_create_async(CACHE_TTL_EVENTS, build, *cache_key)


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
        html = HTMLParser(resp.text)
        status = resp.status_code

        matches = []
        current_date = ""

        for elem in html.css(".wf-label.mod-large, a.wf-module-item.match-item"):
            classes = elem.attributes.get("class", "")

            if "wf-label" in classes:
                current_date = elem.text(strip=True)
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

            status_el = elem.css_first(".ml-status")
            eta_el = elem.css_first(".ml-eta")
            match_status = ""
            if status_el:
                match_status = status_el.text(strip=True)
            elif eta_el:
                match_status = eta_el.text(strip=True)

            vods = []
            for vod_el in elem.css(".match-item-vod .wf-tag"):
                vod_text = vod_el.text(strip=True)
                vod_link_el = vod_el if vod_el.tag == "a" else vod_el.parent
                vod_href = vod_link_el.attributes.get("href", "") if vod_link_el else ""
                if vod_href:
                    vod_href = build_full_url(vod_href)
                vods.append({"label": vod_text, "url": vod_href})

            note_el = elem.css_first(".match-item-note")
            note = note_el.text(strip=True) if note_el else ""

            matches.append({
                "match_id": match_id,
                "url": match_url,
                "date": current_date,
                "status": match_status,
                "note": note,
                "event_series": event_series,
                "team1": teams[0],
                "team2": teams[1],
                "vods": vods,
            })

        return {"data": {"status": status, "segments": matches}}

    return await cache_manager.get_or_create_async(
        CACHE_TTL_EVENT_MATCHES, build, *cache_key
    )
