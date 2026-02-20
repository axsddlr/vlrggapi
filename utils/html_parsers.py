"""
Common HTML parsing utilities for VLR.GG scrapers
"""
import re
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlparse

from zoneinfo import ZoneInfo


def extract_text_content(element, strip: bool = True) -> str:
    """Extract text content from an HTML element safely"""
    if not element:
        return ""
    return element.text(strip=strip)


def extract_prize_value(prize_elem) -> str:
    """
    Extract prize value from VLR.GG prize elements.
    Handles both monetary values ($250,000) and TBD cases.
    """
    if not prize_elem:
        return ""

    full_text = prize_elem.text(strip=True)

    # Split before "Prize Pool" label to get just the value
    parts = re.split(r'(?=Prize Pool|prize pool)', full_text, flags=re.IGNORECASE)
    if not parts:
        return ""

    first_part = re.sub(r'\s+', ' ', parts[0].strip())

    # Check for TBD
    if first_part.upper() == "TBD":
        return "TBD"
    # Check for dollar amounts
    elif re.match(r'^\$[\d,]+$', first_part):
        return first_part
    # Check for numeric values (add $ if missing)
    elif re.match(r'^[\d,]+$', first_part) and len(first_part) > 2:
        return "$" + first_part

    return ""


def extract_date_range(dates_elem) -> str:
    """
    Extract date range from VLR.GG date elements.
    Handles patterns like "Jul 15—Aug 31" and "Sep 15—TBD"
    """
    if not dates_elem:
        return ""

    full_text = dates_elem.text(strip=True)

    # Try to find date patterns first
    date_match = re.search(r"[A-Za-z]{3}\s+\d+[—\-–]+[A-Za-z]*\s*\d+", full_text)
    if date_match:
        return date_match.group()

    # Check for TBD in dates or fallback parsing
    if re.search(r"\bTBD\b", full_text, re.IGNORECASE):
        return "TBD"

    # Fallback: look for month abbreviations
    lines = full_text.split('\n')
    for line in lines:
        line = line.strip()
        if not line or any(keyword in line.lower() for keyword in ['dates', 'label', 'prize', 'pool']):
            continue

        if (any(month in line for month in ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                                          'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']) or
            '\u2014' in line):
            return line

    return ""


def extract_region_from_flag(flag_elem) -> str:
    """Extract region code from flag element class attribute"""
    if not flag_elem:
        return ""

    class_attr = flag_elem.attributes.get("class", "")
    return class_attr.replace("flag mod-", "").strip()


def normalize_image_url(src: str, base_url: str = "https://www.vlr.gg") -> str:
    """Normalize image URLs to absolute URLs"""
    if not src:
        return ""

    if src.startswith("//"):
        return "https:" + src
    elif src.startswith("/"):
        return base_url + src
    else:
        return src


def build_full_url(href: str, base_url: str = "https://www.vlr.gg") -> str:
    """Build full URL from relative href"""
    if not href:
        return ""
    return base_url + href if href.startswith("/") else href


def extract_tournament_icon(item) -> str:
    """Normalize icon URL extraction from a match/event item."""
    icon_elem = item.css_first(".match-item-icon img") or item.css_first("img")
    if not icon_elem:
        return ""
    src = icon_elem.attributes.get("src", "")
    return normalize_image_url(src)


def extract_match_teams(item, selector: str = ".h-match-team") -> tuple[dict, dict]:
    """
    Extract team info from a match item.
    Returns (team1_dict, team2_dict) each with name, flag, score.
    """
    teams = []
    for team_elem in item.css(selector):
        name_elem = team_elem.css_first(
            ".h-match-team-name"
        ) or team_elem.css_first(
            ".match-item-vs-team-name"
        )
        name = name_elem.text().strip() if name_elem else "TBD"

        flag_elem = team_elem.css_first(".flag")
        flag = ""
        if flag_elem:
            flag_class = flag_elem.attributes.get("class", "")
            flag = flag_class.replace(" mod-", "").replace("16", "_")
            flag = flag.replace("flag ", "") if flag.startswith("flag ") else flag

        score_elem = team_elem.css_first(
            ".h-match-team-score"
        ) or team_elem.css_first(
            ".match-item-vs-team-score"
        )
        score = score_elem.text().strip() if score_elem else ""

        teams.append({"name": name, "flag": flag, "score": score})

    while len(teams) < 2:
        teams.append({"name": "TBD", "flag": "", "score": ""})

    return teams[0], teams[1]


# --- Timestamp parsing helpers (moved from matches.py) ---

def parse_eta_to_timedelta(eta_text: str) -> Optional[timedelta]:
    """Parse '4h 1m' / '1d 2h' / '30m' into timedelta. Returns None for LIVE/ago/unparseable."""
    if not eta_text:
        return None
    eta_text = eta_text.strip()
    if not eta_text or "LIVE" in eta_text.upper() or "ago" in eta_text.lower():
        return None
    pattern = re.findall(r"(\d+)\s*([dhm])", eta_text.lower())
    if not pattern:
        return None
    total = timedelta()
    for value, unit in pattern:
        value = int(value)
        if unit == "d":
            total += timedelta(days=value)
        elif unit == "h":
            total += timedelta(hours=value)
        elif unit == "m":
            total += timedelta(minutes=value)
    return total if total > timedelta() else None


def combine_date_and_time(date_str: str, time_text: str) -> str:
    """Parse 'Mon, February 9, 2026' + '4:00 AM' -> UTC timestamp string.

    Interprets times as US Eastern. Returns '' on failure.
    """
    if not date_str or not time_text:
        return ""
    time_text = time_text.strip()
    if not time_text or time_text.upper() in ("TBD", "LIVE", "-"):
        return ""

    eastern = ZoneInfo("America/New_York")

    # Clean up date_str: remove day-of-week prefix like "Mon, "
    cleaned_date = re.sub(r"^[A-Za-z]+,\s*", "", date_str.strip())
    # Handle "Today" / "Tomorrow" by skipping date parse
    if cleaned_date.lower() in ("today", "tomorrow"):
        now_eastern = datetime.now(eastern)
        if cleaned_date.lower() == "tomorrow":
            now_eastern += timedelta(days=1)
        cleaned_date = now_eastern.strftime("%B %d, %Y")

    # Parse time: "4:00 AM" or "16:00"
    parsed_time = None
    for fmt in ("%I:%M %p", "%H:%M"):
        try:
            parsed_time = datetime.strptime(time_text, fmt).time()
            break
        except ValueError:
            continue
    if parsed_time is None:
        return ""

    # Parse date: "February 9, 2026"
    parsed_date = None
    for fmt in ("%B %d, %Y", "%b %d, %Y"):
        try:
            parsed_date = datetime.strptime(cleaned_date, fmt).date()
            break
        except ValueError:
            continue
    if parsed_date is None:
        return ""

    local_dt = datetime.combine(parsed_date, parsed_time, tzinfo=eastern)
    utc_dt = local_dt.astimezone(timezone.utc)
    return utc_dt.strftime("%Y-%m-%d %H:%M:%S")


def parse_match_timestamp(item, date_str: str) -> str:
    """Multi-strategy timestamp extraction for a match item.

    1. .moment-tz-convert[data-utc-ts]
    2. .ml-eta countdown -> utcnow() + delta
    3. date header + .match-item-time -> Eastern -> UTC
    4. '' if all fail
    """
    # Strategy 1: direct UTC timestamp element
    ts_elem = item.css_first(".moment-tz-convert")
    if ts_elem:
        unix_ts = ts_elem.attributes.get("data-utc-ts")
        if unix_ts:
            try:
                return datetime.fromtimestamp(
                    int(unix_ts), tz=timezone.utc
                ).strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, OSError):
                pass

    # Strategy 2: ETA countdown
    eta_elem = item.css_first(".ml-eta")
    if eta_elem:
        delta = parse_eta_to_timedelta(eta_elem.text())
        if delta is not None:
            utc_dt = datetime.now(timezone.utc) + delta
            return utc_dt.strftime("%Y-%m-%d %H:%M:%S")

    # Strategy 3: date header + match time
    time_elem = item.css_first(".match-item-time")
    if time_elem:
        time_text = time_elem.text().strip()
        result = combine_date_and_time(date_str, time_text)
        if result:
            return result

    return ""


# --- Shared helpers for new scrapers ---

def parse_href_id_slug(href: str) -> tuple[str, str]:
    """Extract numeric ID and slug from VLR hrefs like '/player/1234/tenz'.

    Returns (id, slug). Either may be '' if not found.
    """
    if not href:
        return "", ""
    parts = href.strip("/").split("/")
    for i, part in enumerate(parts):
        if part.isdigit():
            slug = parts[i + 1] if i + 1 < len(parts) else ""
            return part, slug
    return "", ""


_PLATFORM_PATTERNS = {
    "twitter": ("twitter.com", "x.com"),
    "twitch": ("twitch.tv",),
    "instagram": ("instagram.com",),
    "youtube": ("youtube.com", "youtu.be"),
    "discord": ("discord.gg", "discord.com"),
    "facebook": ("facebook.com",),
    "vk": ("vk.com",),
}


def infer_platform(url: str) -> str:
    """Detect social platform from URL. Returns lowercase name or 'other'."""
    if not url:
        return "other"
    host = urlparse(url).netloc.lower().lstrip("www.")
    for platform, domains in _PLATFORM_PATTERNS.items():
        if any(d in host for d in domains):
            return platform
    return "other"


def parse_match_items(html, container_selector: str = "a.wf-module-item.match-item") -> list[dict]:
    """Parse match list items shared by player/team match history pages.

    Returns list of dicts with: url, teams, scores, event, date, status.
    """
    items = html.css(container_selector)
    results = []
    for item in items:
        href = item.attributes.get("href", "")
        match_id, _ = parse_href_id_slug(href)
        url = build_full_url(href)

        # Teams
        team_elems = item.css(".match-item-vs-team")
        teams = []
        for te in team_elems:
            name_el = te.css_first(".match-item-vs-team-name")
            score_el = te.css_first(".match-item-vs-team-score")
            name = name_el.text(strip=True) if name_el else "TBD"
            score = score_el.text(strip=True) if score_el else ""
            teams.append({"name": name, "score": score})
        while len(teams) < 2:
            teams.append({"name": "TBD", "score": ""})

        # Event
        event_el = item.css_first(".match-item-event")
        event_text = ""
        if event_el:
            lines = [l.strip() for l in event_el.text().split("\n") if l.strip()]
            event_text = lines[-1] if lines else ""
        series_el = item.css_first(".match-item-event-series")
        event_series = " ".join(series_el.text().split()) if series_el else ""

        # ETA / status
        eta_el = item.css_first(".ml-status") or item.css_first(".ml-eta")
        status = eta_el.text(strip=True) if eta_el else ""

        # Timestamp
        ts_el = item.css_first(".moment-tz-convert")
        timestamp = ""
        if ts_el:
            unix_ts = ts_el.attributes.get("data-utc-ts")
            if unix_ts:
                try:
                    timestamp = datetime.fromtimestamp(
                        int(unix_ts), tz=timezone.utc
                    ).strftime("%Y-%m-%d %H:%M:%S")
                except (ValueError, OSError):
                    pass

        results.append({
            "match_id": match_id,
            "url": url,
            "team1": teams[0],
            "team2": teams[1],
            "event": event_text,
            "event_series": event_series,
            "status": status,
            "timestamp": timestamp,
        })

    return results
