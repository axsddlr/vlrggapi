import re
from datetime import datetime, timezone

import requests
from selectolax.parser import HTMLParser

from utils.utils import headers


def vlr_upcoming_matches():
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


def vlr_live_score():
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


def vlr_match_results(page):
    url = f"https://www.vlr.gg/matches/results/?page={page}"
    resp = requests.get(url, headers=headers)
    html = HTMLParser(resp.text)
    status = resp.status_code

    result = []
    for item in html.css("a.wf-module-item"):
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
        flag1 = flag_list[0]
        flag2 = flag_list[1]

        result.append(
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
            }
        )
    segments = {"status": status, "segments": result}
    data = {"data": segments}
    if status != 200:
        raise Exception("API response: {}".format(status))
    return data