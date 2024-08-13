import re
from datetime import datetime, timezone

import requests
from selectolax.parser import HTMLParser

import utils.utils as res
from utils.utils import headers


class Vlr:
    def get_parse(self, url):
        """
        It takes a URL, makes a request to that URL, and returns a tuple of the HTMLParser object and the status code

        :param url: The URL of the page you want to parse
        :return: A tuple of the HTMLParser object and the status code.
        """
        resp = requests.get(url, headers=headers)
        html, status_code = resp.text, resp.status_code
        return HTMLParser(html), status_code

    def vlr_news(self):
        """
        This function is getting the news articles from the website and
        returning the data in a dictionary.
        :return: a dictionary with the key "data" and the value of the dictionary is another dictionary with the
        keys "status" and "segments".
        """
        url = "https://www.vlr.gg/news"
        html, status = self.get_parse(url)
        result = []
        for item in html.css("a.wf-module-item"):
            # This is getting the date and author of the article.
            date_author = item.css_first("div.ge-text-light").text()
            date, author = date_author.split("by")

            # Getting description of article via selecting second element in div
            desc = item.css_first("div").css_first("div:nth-child(2)").text().strip()

            # Getting the title of the news article by selecting the first element in div and then selecting the first
            # element after splitting
            title = item.css_first("div:nth-child(1)").text().strip().split("\n")[0]
            title = title.replace("\t", "")

            # Getting the url of the article.
            url = item.css_first("a.wf-module-item").attributes["href"]

            # This is appending the data to the result list.
            result.append(
                {
                    "title": title,
                    "description": desc,
                    "date": date.split("\u2022")[1].strip(),
                    "author": author.strip(),
                    "url_path": "https://vlr.gg" + url,
                }
            )
        # This is creating a dictionary with the key "data" and the value of the dictionary is another dictionary
        # with the keys "status" and "segments".
        data = {"data": {"status": status, "segments": result}}

        # This is checking if the status code is not 200, if it is not 200 then it will raise an exception.
        if status != 200:
            raise Exception("API response: {}".format(status))
        return data

    @staticmethod
    def vlr_rankings(region):
        url = "https://www.vlr.gg/rankings/" + res.region[str(region)]
        resp = requests.get(url, headers=headers)
        html = HTMLParser(resp.text)
        status = resp.status_code

        result = []
        for item in html.css("div.rank-item"):
            # get team ranking
            rank = item.css_first("div.rank-item-rank-num").text().strip()

            # get team name
            team = item.css_first("div.ge-text").text()
            team = team.split("#")[0]

            # get logo png url
            logo = item.css_first("a.rank-item-team").css_first("img").attributes["src"]
            logo = re.sub(r"\/img\/vlr\/tmp\/vlr.png", "", logo)

            # get team country
            country = item.css_first("div.rank-item-team-country").text()

            last_played = item.css_first("a.rank-item-last").text()
            last_played = last_played.replace("\n", "").replace("\t", "").split("v")[0]

            last_played_team = item.css_first("a.rank-item-last").text()
            last_played_team = (
                last_played_team.replace("\t", "").replace("\n", "").split("o")[1]
            )
            last_played_team = last_played_team.replace(".", ". ")

            last_played_team_logo = (
                item.css_first("a.rank-item-last").css_first("img").attributes["src"]
            )
            # last_played_team_name = item.css_first("a.rank-item-last").css_first("span:nth-child(3)").text()

            record = item.css_first("div.rank-item-record").text()
            record = record.replace("\t", "").replace("\n", "")

            earnings = item.css_first("div.rank-item-earnings").text()
            earnings = earnings.replace("\t", "").replace("\n", "")
            result.append(
                {
                    "rank": rank,
                    "team": team.strip(),
                    "country": country,
                    "last_played": last_played.strip(),
                    "last_played_team": last_played_team.strip(),
                    "last_played_team_logo": last_played_team_logo,
                    "record": record,
                    "earnings": earnings,
                    "logo": logo,
                }
            )

        data = {"status": status, "data": result}

        if status != 200:
            raise Exception("API response: {}".format(status))
        return data

    @staticmethod
    def vlr_match_results():
        url = "https://www.vlr.gg/matches/results"
        resp = requests.get(url, headers=headers)
        html = HTMLParser(resp.text)
        status = resp.status_code

        result = []
        for item in html.css("a.wf-module-item"):
            url_path = item.attributes["href"]

            eta = item.css_first("div.ml-eta").text() + " ago"

            rounds = item.css_first("div.match-item-event-series").text()
            rounds = rounds.replace("\u2013", "-")
            rounds = rounds.replace("\n", "").replace("\t", "")

            tourney = item.css_first("div.match-item-event").text()
            tourney = tourney.replace("\t", " ")
            tourney = tourney.strip().split("\n")[1]
            tourney = tourney.strip()

            tourney_icon_url = item.css_first("img").attributes["src"]
            tourney_icon_url = f"https:{tourney_icon_url}"

            try:
                team_array = (
                    item.css_first("div.match-item-vs")
                    .css_first("div:nth-child(2)")
                    .text()
                )
            except Exception:  # Replace bare except with except Exception
                team_array = "TBD"
            team_array = team_array.replace("\t", " ").replace("\n", " ")
            team_array = team_array.strip().split("                                  ")
            # 1st item in team_array is first team
            team1 = team_array[0]
            # 2nd item in team_array is first team score
            score1 = team_array[1].replace(" ", "").strip()
            # 3rd item in team_array is second team
            team2 = team_array[4].strip()
            # 4th item in team_array is second team score
            score2 = team_array[-1].replace(" ", "").strip()

            # Creating a list of the classes of the flag elements.
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

    @staticmethod
    def vlr_stats(region: str, timespan: int):
        url = (
            f"https://www.vlr.gg/stats/?event_group_id=all&event_id=all&region={region}&country=all&min_rounds=200"
            f"&min_rating=1550&agent=all&map_id=all&timespan={timespan}d"
        )

        resp = requests.get(url, headers=headers)
        html = HTMLParser(resp.text)
        status = resp.status_code

        result = []
        for item in html.css("tbody tr"):
            player = item.text().replace("\t", "").replace("\n", " ").strip()
            player = player.split()
            player_name = player[0]

            # get org name abbreviation via player variable
            try:
                org = player[1]
            except Exception:
                org = "N/A"

            # agents = [agents.css_first("img").attributes['src'] for agents in item.css("td.mod-agents")]

            # get all td items from mod-color-sq class
            color_sq = [stats.text() for stats in item.css("td.mod-color-sq")]
            rat = color_sq[0]
            acs = color_sq[1]
            kd = color_sq[2]
            kast = color_sq[3]
            adr = color_sq[4]
            kpr = color_sq[5]
            apr = color_sq[6]
            fkpr = color_sq[7]
            fdpr = color_sq[8]
            hs = color_sq[9]
            cl = color_sq[10]

            result.append(
                {
                    "player": player_name,
                    "org": org,
                    "rating": rat,
                    "average_combat_score": acs,
                    "kill_deaths": kd,
                    "kill_assists_survived_traded": kast,
                    "average_damage_per_round": adr,
                    "kills_per_round": kpr,
                    "assists_per_round": apr,
                    "first_kills_per_round": fkpr,
                    "first_deaths_per_round": fdpr,
                    "headshot_percentage": hs,
                    "clutch_success_percentage": cl,
                }
            )
        segments = {"status": status, "segments": result}

        data = {"data": segments}

        if status != 200:
            raise Exception("API response: {}".format(status))
        return data

    @staticmethod
    def vlr_upcoming_matches():
        url = "https://www.vlr.gg"
        resp = requests.get(url, headers=headers)
        html = HTMLParser(resp.text)
        status = resp.status_code

        result = []
        for item in html.css(".js-home-matches-upcoming a.wf-module-item"):
            # Check if the match is upcoming
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

    @staticmethod
    def vlr_live_score():
        url = "https://www.vlr.gg"
        resp = requests.get(url, headers=headers)
        html = HTMLParser(resp.text)
        status = resp.status_code

        matches = html.css(".js-home-matches-upcoming a.wf-module-item")
        result = []
        for match in matches:
            # Check if the match is live by looking for the mod-live class within h-match-eta div
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
                    # Extract round information if available
                    round_info_ct = team.css(".h-match-team-rounds .mod-ct")
                    round_info_t = team.css(".h-match-team-rounds .mod-t")
                    round_text_ct = (
                        round_info_ct[0].text().strip() if round_info_ct else "N/A"
                    )
                    round_text_t = (
                        round_info_t[0].text().strip() if round_info_t else "N/A"
                    )
                    round_texts.append({"ct": round_text_ct, "t": round_text_t})

                eta = "LIVE"
                match_event = match.css_first(".h-match-preview-event").text().strip()
                match_series = match.css_first(".h-match-preview-series").text().strip()
                timestamp = datetime.fromtimestamp(
                    int(
                        match.css_first(".moment-tz-convert").attributes["data-utc-ts"]
                    ),
                    tz=timezone.utc,
                ).strftime("%Y-%m-%d %H:%M:%S")
                url_path = "https://www.vlr.gg/" + match.attributes["href"]

                # Fetch additional details from the match page
                match_page = requests.get(url_path, headers=headers)
                match_html = HTMLParser(match_page.text)
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

                    # Extract the leading integer representing the map number in the series sequence
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


if __name__ == "__main__":
    print(Vlr.vlr_live_score(self=Vlr()))
