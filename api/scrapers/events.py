import re
import requests
from selectolax.parser import HTMLParser

from utils.utils import headers


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
        url = f"https://www.vlr.gg/events/?page={page}"
    else:
        url = "https://www.vlr.gg/events"
    
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
            title = event_item.css_first(".event-item-title")
            title = title.text(strip=True) if title else ""

            status_elem = event_item.css_first(".event-item-desc-item-status")
            event_status = status_elem.text(strip=True) if status_elem else ""

            # Prize - extract monetary value or TBD (before the nested label div)
            prize_elem = event_item.css_first(".event-item-desc-item.mod-prize")
            prize = ""
            if prize_elem:
                # Get the HTML and extract text before the first nested div
                full_text = prize_elem.text(strip=True)
                
                # Split by common separators and take the first meaningful part
                # The structure is: "$250,000<div>Prize Pool</div>" or "TBD<div>Prize Pool</div>"
                parts = re.split(r'(?=Prize Pool|prize pool)', full_text, flags=re.IGNORECASE)
                if parts:
                    first_part = parts[0].strip()
                    
                    # Clean up any remaining whitespace or newlines
                    first_part = re.sub(r'\s+', ' ', first_part).strip()
                    
                    # Check for TBD
                    if first_part.upper() == "TBD":
                        prize = "TBD"
                    # Check for dollar amounts
                    elif re.match(r'^\$[\d,]+$', first_part):
                        prize = first_part
                    # Check for numeric values (add $ if missing)
                    elif re.match(r'^[\d,]+$', first_part) and len(first_part) > 2:
                        prize = "$" + first_part

            # Dates - extract date range like "Jul 15—Aug 31", avoid TBD if it's for prize
            dates_elem = event_item.css_first(".event-item-desc-item.mod-dates")
            dates = ""
            if dates_elem:
                full_text = dates_elem.text(strip=True)
                # Use regex to find date patterns like "Jul 15—Aug 31" or "Dec 1—15"
                date_match = re.search(
                    r"[A-Za-z]{3}\s+\d+[—\-–]+[A-Za-z]*\s*\d+", full_text
                )
                if date_match:
                    dates = date_match.group()
                else:
                    # If TBD was found in prize section from dates, don't use TBD as dates
                    if prize != "TBD" and re.search(
                        r"\bTBD\b", full_text, re.IGNORECASE
                    ):
                        dates = "TBD"
                    else:
                        # Fallback: look for any text before "Dates" or similar keywords
                        lines = full_text.split("\n")
                        for line in lines:
                            line = line.strip()
                            if line and not any(
                                keyword in line.lower()
                                for keyword in ["dates", "label", "prize", "pool"]
                            ):
                                # Look for lines that contain month abbreviations or date-like patterns
                                if (
                                    any(
                                        month in line
                                        for month in [
                                            "Jan",
                                            "Feb",
                                            "Mar",
                                            "Apr",
                                            "May",
                                            "Jun",
                                            "Jul",
                                            "Aug",
                                            "Sep",
                                            "Oct",
                                            "Nov",
                                            "Dec",
                                        ]
                                    )
                                    or "—" in line
                                ):
                                    dates = line
                                    break

            # Region from flag
            region = ""
            flag_elem = event_item.css_first(".event-item-desc-item.mod-location .flag")
            if flag_elem:
                class_attr = flag_elem.attributes.get("class", "")
                region = class_attr.replace("flag mod-", "").strip()

            # Thumbnail
            thumb = ""
            img_elem = event_item.css_first(".event-item-thumb img")
            if img_elem:
                src = img_elem.attributes.get("src", "")
                if src.startswith("//"):
                    thumb = "https:" + src
                elif src.startswith("/"):
                    thumb = "https://www.vlr.gg" + src
                else:
                    thumb = src

            # URL path
            url_path = event_item.attributes.get("href", "")
            full_url = "https://www.vlr.gg" + url_path if url_path else ""

            events.append(
                {
                    "title": title,
                    "status": event_status,
                    "prize": prize,
                    "dates": dates,
                    "region": region,
                    "thumb": thumb,
                    "url_path": full_url,
                }
            )

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
