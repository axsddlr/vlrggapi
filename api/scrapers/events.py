import requests
from selectolax.parser import HTMLParser

from utils.utils import headers
from utils.constants import VLR_EVENTS_URL
from utils.html_parsers import (
    extract_text_content,
    extract_prize_value,
    extract_date_range,
    extract_region_from_flag,
    normalize_image_url,
    build_full_url
)


def vlr_events(upcoming=True, completed=True, page=1):
    """
    Get Valorant events from VLR.GG

    Args:
        upcoming (bool): If True, include upcoming events
        completed (bool): If True, include completed events
        page (int): Page number for pagination (only applies to completed events)

    Returns:
        dict: Response with status code and events data
    """
    # Build URL with pagination for completed events
    if completed and page > 1:
        url = f"{VLR_EVENTS_URL}/?page={page}"
    else:
        url = VLR_EVENTS_URL
    
    resp = requests.get(url, headers=headers)
    html = HTMLParser(resp.text)
    status = resp.status_code

    # If both are False, show both (default behavior)
    if not upcoming and not completed:
        upcoming = True
        completed = True

    events = []

    def parse_events(container):
        """Helper function to parse event cards"""
        for event_item in container.css("a.event-item"):
            # Extract basic information using utility functions
            title = extract_text_content(event_item.css_first(".event-item-title"))
            event_status = extract_text_content(event_item.css_first(".event-item-desc-item-status"))
            
            # Extract complex parsed data
            prize = extract_prize_value(event_item.css_first(".event-item-desc-item.mod-prize"))
            dates = extract_date_range(event_item.css_first(".event-item-desc-item.mod-dates"))
            region = extract_region_from_flag(event_item.css_first(".event-item-desc-item.mod-location .flag"))
            
            # Extract and normalize URLs
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

    # Parse upcoming events
    if upcoming:
        upcoming_sections = html.css("div.wf-label.mod-large.mod-upcoming")
        for section in upcoming_sections:
            parent = section.parent
            if parent and parent.css("a.event-item"):
                parse_events(parent)

    # Parse completed events
    if completed:
        completed_sections = html.css("div.wf-label.mod-large.mod-completed")
        for section in completed_sections:
            parent = section.parent
            if parent and parent.css("a.event-item"):
                parse_events(parent)

    return {"data": {"status": status, "segments": events}}
