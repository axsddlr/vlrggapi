import re
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests
from selectolax.parser import HTMLParser

from utils.utils import headers


def vlr_upcoming_matches(num_pages=1, from_page=None, to_page=None):
    """
    Get upcoming matches from VLR.GG.
    
    Args:
        num_pages (int): Number of pages to scrape from page 1 (ignored if from_page/to_page specified)
        from_page (int, optional): Starting page number (1-based)
        to_page (int, optional): Ending page number (1-based, inclusive)
    """
    # Note: VLR.GG upcoming matches are typically only on the homepage
    # Page range parameters are included for API consistency but may not apply
    url = "https://www.vlr.gg"
    resp = requests.get(url, headers=headers)
    html = HTMLParser(resp.text)
    status = resp.status_code

    result = []
    for item in html.css(".js-home-matches-upcoming a.wf-module-item"):
        is_upcoming = item.css_first(".h-match-eta.mod-upcoming")
        if is_upcoming:
            teams = []
            flags = []
            scores = []
            for team in item.css(".h-match-team"):
                teams.append(team.css_first(".h-match-team-name").text().strip())
                flags.append(
                    team.css_first(".flag")
                    .attributes["class"]
                    .replace(" mod-", "")
                    .replace("16", "_")
                )
                scores.append(team.css_first(".h-match-team-score").text().strip())

            eta = item.css_first(".h-match-eta").text().strip()
            if eta != "LIVE":
                eta = eta + " from now"

            match_event = item.css_first(".h-match-preview-event").text().strip()
            match_series = item.css_first(".h-match-preview-series").text().strip()
            timestamp = datetime.fromtimestamp(
                int(item.css_first(".moment-tz-convert").attributes["data-utc-ts"]),
                tz=timezone.utc,
            ).strftime("%Y-%m-%d %H:%M:%S")
            url_path = "https://www.vlr.gg/" + item.attributes["href"]

            result.append(
                {
                    "team1": teams[0],
                    "team2": teams[1],
                    "flag1": flags[0],
                    "flag2": flags[1],
                    "time_until_match": eta,
                    "match_series": match_series,
                    "match_event": match_event,
                    "unix_timestamp": timestamp,
                    "match_page": url_path,
                }
            )

    segments = {"status": status, "segments": result}
    data = {"data": segments}

    if status != 200:
        raise Exception("API response: {}".format(status))
    return data


def vlr_live_score(num_pages=1, from_page=None, to_page=None):
    """
    Get live match scores from VLR.GG.
    
    Args:
        num_pages (int): Number of pages to scrape from page 1 (ignored if from_page/to_page specified)
        from_page (int, optional): Starting page number (1-based)
        to_page (int, optional): Ending page number (1-based, inclusive)
    """
    # Note: VLR.GG live matches are typically only on the homepage
    # Page range parameters are included for API consistency but may not apply
    url = "https://www.vlr.gg"
    resp = requests.get(url, headers=headers)
    html = HTMLParser(resp.text)
    status = resp.status_code

    matches = html.css(".js-home-matches-upcoming a.wf-module-item")
    result = []
    for match in matches:
        is_live = match.css_first(".h-match-eta.mod-live")
        if is_live:
            teams = []
            flags = []
            scores = []
            round_texts = []
            for team in match.css(".h-match-team"):
                teams.append(team.css_first(".h-match-team-name").text().strip())
                flags.append(
                    team.css_first(".flag")
                    .attributes["class"]
                    .replace(" mod-", "")
                    .replace("16", "_")
                )
                scores.append(team.css_first(".h-match-team-score").text().strip())
                round_info_ct = team.css(".h-match-team-rounds .mod-ct")
                round_info_t = team.css(".h-match-team-rounds .mod-t")
                round_text_ct = (
                    round_info_ct[0].text().strip() if round_info_ct else "N/A"
                )
                round_text_t = round_info_t[0].text().strip() if round_info_t else "N/A"
                round_texts.append({"ct": round_text_ct, "t": round_text_t})

            eta = "LIVE"
            match_event = match.css_first(".h-match-preview-event").text().strip()
            match_series = match.css_first(".h-match-preview-series").text().strip()
            timestamp = datetime.fromtimestamp(
                int(match.css_first(".moment-tz-convert").attributes["data-utc-ts"]),
                tz=timezone.utc,
            ).strftime("%Y-%m-%d %H:%M:%S")
            url_path = "https://www.vlr.gg/" + match.attributes["href"]

            match_page = requests.get(url_path, headers=headers)
            match_html = HTMLParser(match_page.text)
            
            team_logos = []
            for img in match_html.css(".match-header-vs img"):
                logo_url = "https:" + img.attributes.get("src", "")
                team_logos.append(logo_url)

            current_map_element = match_html.css_first(
                ".vm-stats-gamesnav-item.js-map-switch.mod-active.mod-live"
            )
            current_map = "Unknown"
            if current_map_element:
                current_map = (
                    current_map_element.css_first("div", default="Unknown")
                    .text()
                    .strip()
                    .replace("\n", "")
                    .replace("\t", "")
                )
                current_map = re.sub(r"^\d+", "", current_map)
                map_number_match = (
                    current_map_element.css_first("div", default="Unknown")
                    .text()
                    .strip()
                    .replace("\n", "")
                    .replace("\t", "")
                )
                map_number_match = re.search(r"^\d+", map_number_match)
                map_number = (
                    map_number_match.group(0) if map_number_match else "Unknown"
                )

            team1_round_ct = round_texts[0]["ct"] if len(round_texts) > 0 else "N/A"
            team1_round_t = round_texts[0]["t"] if len(round_texts) > 0 else "N/A"
            team2_round_ct = round_texts[1]["ct"] if len(round_texts) > 1 else "N/A"
            team2_round_t = round_texts[1]["t"] if len(round_texts) > 1 else "N/A"
            result.append(
                {
                    "team1": teams[0],
                    "team2": teams[1],
                    "flag1": flags[0],
                    "flag2": flags[1],
                    "team1_logo": team_logos[0] if len(team_logos) > 0 else "",
                    "team2_logo": team_logos[1] if len(team_logos) > 1 else "",
                    "score1": scores[0],
                    "score2": scores[1],
                    "team1_round_ct": team1_round_ct,
                    "team1_round_t": team1_round_t,
                    "team2_round_ct": team2_round_ct,
                    "team2_round_t": team2_round_t,
                    "map_number": map_number,
                    "current_map": current_map,
                    "time_until_match": eta,
                    "match_event": match_event,
                    "match_series": match_series,
                    "unix_timestamp": timestamp,
                    "match_page": url_path,
                }
            )

    segments = {"status": status, "segments": result}
    data = {"data": segments}

    if status != 200:
        raise Exception("API response: {}".format(status))
    return data


def _parse_eta_to_timedelta(eta_text):
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


def _combine_date_and_time(date_str, time_text):
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
    time_text = time_text.strip()
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


def _parse_match_timestamp(item, date_str):
    """Multi-strategy timestamp extraction for a match item.

    1. .moment-tz-convert[data-utc-ts] (future-proofing)
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
        delta = _parse_eta_to_timedelta(eta_elem.text())
        if delta is not None:
            utc_dt = datetime.now(timezone.utc) + delta
            return utc_dt.strftime("%Y-%m-%d %H:%M:%S")

    # Strategy 3: date header + match time
    time_elem = item.css_first(".match-item-time")
    if time_elem:
        time_text = time_elem.text().strip()
        result = _combine_date_and_time(date_str, time_text)
        if result:
            return result

    return ""


def _parse_single_match(item, date_str, page):
    """Extract all match fields from one <a> element. Returns dict or None."""
    # Skip completed matches
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
    scores = []
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
        scores.append(score_elem.text().strip() if score_elem else "")

    while len(teams) < 2:
        teams.append("TBD")
    while len(flags) < 2:
        flags.append("")
    while len(scores) < 2:
        scores.append("")

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
            tourney_icon_url = f"https:{icon_src}" if icon_src.startswith("//") else icon_src

    # Get timestamp using multi-strategy approach
    timestamp = _parse_match_timestamp(item, date_str)

    return {
        "team1": teams[0],
        "team2": teams[1],
        "flag1": flags[0],
        "flag2": flags[1],
        "score1": scores[0],
        "score2": scores[1],
        "time_until_match": eta,
        "match_series": match_series,
        "match_event": tourney,
        "unix_timestamp": timestamp,
        "match_page": url_path,
        "tournament_icon": tourney_icon_url,
        "page_number": page,
    }


def vlr_upcoming_matches_extended(num_pages=1, from_page=None, to_page=None, max_retries=3, request_delay=1.0, timeout=30):
    """
    Scrape upcoming matches from the paginated matches page with robust error handling.

    Args:
        num_pages (int): Number of pages to scrape from page 1 (ignored if from_page/to_page specified)
        from_page (int, optional): Starting page number (1-based)
        to_page (int, optional): Ending page number (1-based, inclusive)
        max_retries (int): Maximum retry attempts per page
        request_delay (float): Delay between requests in seconds
        timeout (int): Request timeout in seconds

    Returns:
        dict: API response with match data
    """

    result = []
    status = 200
    failed_pages = []

    # Determine page range
    if from_page is not None and to_page is not None:
        if from_page < 1:
            raise ValueError("from_page must be >= 1")
        if to_page < from_page:
            raise ValueError("to_page must be >= from_page")
        start_page = from_page
        end_page = to_page
        total_pages = end_page - start_page + 1
    elif from_page is not None:
        if from_page < 1:
            raise ValueError("from_page must be >= 1")
        start_page = from_page
        end_page = from_page + num_pages - 1
        total_pages = num_pages
    elif to_page is not None:
        if to_page < 1:
            raise ValueError("to_page must be >= 1")
        start_page = max(1, to_page - num_pages + 1)
        end_page = to_page
        total_pages = end_page - start_page + 1
    else:
        # Default behavior: scrape from page 1
        start_page = 1
        end_page = num_pages
        total_pages = num_pages

    # Create a session for connection pooling and efficiency
    session = requests.Session()
    session.headers.update(headers)

    print(f"Starting to scrape pages {start_page}-{end_page} ({total_pages} pages) with {request_delay}s delay between requests...")

    for page in range(start_page, end_page + 1):
        page_success = False
        retry_count = 0

        while not page_success and retry_count < max_retries:
            try:
                if page == 1:
                    url = "https://www.vlr.gg/matches"
                else:
                    url = f"https://www.vlr.gg/matches/?page={page}"

                current_page_num = page - start_page + 1
                print(f"Scraping page {page} ({current_page_num}/{total_pages}) (attempt {retry_count + 1}/{max_retries})")

                # Add timeout and handle potential connection issues
                resp = session.get(url, timeout=timeout)
                html = HTMLParser(resp.text)
                current_status = resp.status_code

                if current_status != 200:
                    print(f"Warning: Page {page} returned status {current_status}")
                    retry_count += 1
                    if retry_count < max_retries:
                        time.sleep(request_delay * (2 ** retry_count))  # Exponential backoff
                    continue

                page_results = []

                # Try date-section-based iteration first
                date_labels = html.css(".wf-label.mod-large")

                if date_labels:
                    for label in date_labels:
                        date_str = label.text().strip()
                        # Traverse to the next sibling .wf-card
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
                        items = card.css("a.wf-module-item")
                        for item in items:
                            try:
                                match_data = _parse_single_match(item, date_str, page)
                                if match_data is not None:
                                    page_results.append(match_data)
                            except Exception as e:
                                print(f"Warning: Failed to parse match item on page {page}: {str(e)}")
                                continue
                else:
                    # Fallback: flat iteration (no date labels found)
                    items = html.css("a.wf-module-item")
                    if not items:
                        print(f"Warning: No match items found on page {page}")
                        page_success = True
                        break
                    for item in items:
                        try:
                            match_data = _parse_single_match(item, "", page)
                            if match_data is not None:
                                page_results.append(match_data)
                        except Exception as e:
                            print(f"Warning: Failed to parse match item on page {page}: {str(e)}")
                            continue

                result.extend(page_results)
                print(f"Successfully scraped page {page}: {len(page_results)} matches")
                page_success = True

                # Rate limiting between successful requests
                if page < end_page:
                    time.sleep(request_delay)

            except requests.exceptions.Timeout:
                retry_count += 1
                print(f"Timeout error on page {page}, attempt {retry_count}/{max_retries}")
                if retry_count < max_retries:
                    backoff_time = request_delay * (2 ** retry_count)
                    print(f"Retrying page {page} in {backoff_time:.1f} seconds...")
                    time.sleep(backoff_time)

            except requests.exceptions.ConnectionError:
                retry_count += 1
                print(f"Connection error on page {page}, attempt {retry_count}/{max_retries}")
                if retry_count < max_retries:
                    backoff_time = request_delay * (2 ** retry_count)
                    print(f"Retrying page {page} in {backoff_time:.1f} seconds...")
                    time.sleep(backoff_time)

            except Exception as e:
                retry_count += 1
                print(f"Unexpected error on page {page}: {str(e)}")
                if retry_count < max_retries:
                    backoff_time = request_delay * (2 ** retry_count)
                    print(f"Retrying page {page} in {backoff_time:.1f} seconds...")
                    time.sleep(backoff_time)

        if not page_success:
            failed_pages.append(page)
            print(f"Failed to scrape page {page} after {max_retries} attempts")

    # Close the session
    session.close()

    # Report results
    total_matches = len(result)
    successful_pages = total_pages - len(failed_pages)

    print(f"\nScraping completed:")
    print(f"  Page range: {start_page}-{end_page}")
    print(f"  Total matches: {total_matches}")
    print(f"  Successful pages: {successful_pages}/{total_pages}")

    if failed_pages:
        print(f"  Failed pages: {failed_pages}")
        print(f"  Consider retrying failed pages or adjusting parameters")

    segments = {
        "status": status,
        "segments": result,
        "meta": {
            "page_range": f"{start_page}-{end_page}",
            "total_pages_requested": total_pages,
            "successful_pages": successful_pages,
            "failed_pages": failed_pages,
            "total_matches": total_matches
        }
    }
    data = {"data": segments}

    if not result:
        raise Exception(f"No data retrieved. Failed pages: {failed_pages}")

    return data


def vlr_match_results(num_pages=1, from_page=None, to_page=None, max_retries=3, request_delay=1.0, timeout=30):
    """
    Scrape match results with robust error handling for large page counts.
    
    Args:
        num_pages (int): Number of pages to scrape from page 1 (ignored if from_page/to_page specified)
        from_page (int, optional): Starting page number (1-based)
        to_page (int, optional): Ending page number (1-based, inclusive)
        max_retries (int): Maximum retry attempts per page
        request_delay (float): Delay between requests in seconds
        timeout (int): Request timeout in seconds
        
    Returns:
        dict: API response with match data
    """

    result = []
    status = 200
    failed_pages = []
    
    # Determine page range
    if from_page is not None and to_page is not None:
        if from_page < 1:
            raise ValueError("from_page must be >= 1")
        if to_page < from_page:
            raise ValueError("to_page must be >= from_page")
        start_page = from_page
        end_page = to_page
        total_pages = end_page - start_page + 1
    elif from_page is not None:
        if from_page < 1:
            raise ValueError("from_page must be >= 1")
        start_page = from_page
        end_page = from_page + num_pages - 1
        total_pages = num_pages
    elif to_page is not None:
        if to_page < 1:
            raise ValueError("to_page must be >= 1")
        start_page = max(1, to_page - num_pages + 1)
        end_page = to_page
        total_pages = end_page - start_page + 1
    else:
        # Default behavior: scrape from page 1
        start_page = 1
        end_page = num_pages
        total_pages = num_pages
    
    # Create a session for connection pooling and efficiency
    session = requests.Session()
    session.headers.update(headers)
    
    print(f"Starting to scrape pages {start_page}-{end_page} ({total_pages} pages) with {request_delay}s delay between requests...")
    
    for page in range(start_page, end_page + 1):
        page_success = False
        retry_count = 0
        
        while not page_success and retry_count < max_retries:
            try:
                if page == 1:
                    url = "https://www.vlr.gg/matches/results"
                else:
                    url = f"https://www.vlr.gg/matches/results/?page={page}"
                
                current_page_num = page - start_page + 1
                print(f"Scraping page {page} ({current_page_num}/{total_pages}) (attempt {retry_count + 1}/{max_retries})")
                
                # Add timeout and handle potential connection issues
                resp = session.get(url, timeout=timeout)
                html = HTMLParser(resp.text)
                current_status = resp.status_code
                
                if current_status != 200:
                    print(f"Warning: Page {page} returned status {current_status}")
                    retry_count += 1
                    if retry_count < max_retries:
                        time.sleep(request_delay * (2 ** retry_count))  # Exponential backoff
                    continue
                
                page_results = []
                items = html.css("a.wf-module-item")
                
                if not items:
                    print(f"Warning: No match items found on page {page}")
                    page_success = True  # Consider empty page as success
                    break
                
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
                                "page_number": page,  # Track which page this came from
                            }
                        )
                    except Exception as e:
                        print(f"Warning: Failed to parse match item on page {page}: {str(e)}")
                        continue
                
                result.extend(page_results)
                print(f"Successfully scraped page {page}: {len(page_results)} matches")
                page_success = True
                
                # Rate limiting between successful requests
                if page < end_page:
                    time.sleep(request_delay)
                
            except requests.exceptions.Timeout:
                retry_count += 1
                print(f"Timeout error on page {page}, attempt {retry_count}/{max_retries}")
                if retry_count < max_retries:
                    backoff_time = request_delay * (2 ** retry_count)
                    print(f"Retrying page {page} in {backoff_time:.1f} seconds...")
                    time.sleep(backoff_time)
                
            except requests.exceptions.ConnectionError:
                retry_count += 1
                print(f"Connection error on page {page}, attempt {retry_count}/{max_retries}")
                if retry_count < max_retries:
                    backoff_time = request_delay * (2 ** retry_count)
                    print(f"Retrying page {page} in {backoff_time:.1f} seconds...")
                    time.sleep(backoff_time)
                
            except Exception as e:
                retry_count += 1
                print(f"Unexpected error on page {page}: {str(e)}")
                if retry_count < max_retries:
                    backoff_time = request_delay * (2 ** retry_count)
                    print(f"Retrying page {page} in {backoff_time:.1f} seconds...")
                    time.sleep(backoff_time)
        
        if not page_success:
            failed_pages.append(page)
            print(f"Failed to scrape page {page} after {max_retries} attempts")
    
    # Close the session
    session.close()
    
    # Report results
    total_matches = len(result)
    successful_pages = total_pages - len(failed_pages)
    
    print(f"\nScraping completed:")
    print(f"  Page range: {start_page}-{end_page}")
    print(f"  Total matches: {total_matches}")
    print(f"  Successful pages: {successful_pages}/{total_pages}")
    
    if failed_pages:
        print(f"  Failed pages: {failed_pages}")
        print(f"  Consider retrying failed pages or adjusting parameters")
    
    segments = {
        "status": status, 
        "segments": result,
        "meta": {
            "page_range": f"{start_page}-{end_page}",
            "total_pages_requested": total_pages,
            "successful_pages": successful_pages,
            "failed_pages": failed_pages,
            "total_matches": total_matches
        }
    }
    data = {"data": segments}

    if not result:
        raise Exception(f"No data retrieved. Failed pages: {failed_pages}")
    
    return data