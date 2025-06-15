import re
import time
from datetime import datetime, timezone

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