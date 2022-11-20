import re

import requests
from bs4 import BeautifulSoup
from selectolax.parser import HTMLParser

import utils.utils as res
from utils.utils import headers


class Vlr:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.169 Safari/537.36",
        }

    def get_soup(self, URL):
        response = requests.get(URL, headers=self.headers)

        html, status_code = response.text, response.status_code
        return BeautifulSoup(html, "lxml"), status_code

    def get_parse(self, url):
        """
        It takes a URL, makes a request to that URL, and returns a tuple of the HTMLParser object and the status code

        :param url: The URL of the page you want to parse
        :return: A tuple of the HTMLParser object and the status code.
        """
        resp = requests.get(url, headers=self.headers)
        html, status_code = resp.text, resp.status_code
        return HTMLParser(html), status_code

    def vlr_recent(self):
        """
            This function is getting the news articles from the website and
            returning the data in a dictionary.
            :return: a dictionary with the key "data" and the value of the dictionary is another dictionary with the
            keys "status" and "segments".
            """
        url = "https://www.vlr.gg/news"
        html, status = self.get_parse(url)
        result = []
        for item in html.css('a.wf-module-item'):
            # This is getting the date and author of the article.
            date_author = item.css_first("div.ge-text-light").text()
            date, author = date_author.split('by')

            # Getting description of article via selecting second element in div
            desc = item.css_first("div").css_first("div:nth-child(2)").text().strip()

            # Getting the title of the news article by selecting the first element in div and then selecting the first
            # element after splitting
            title = item.css_first("div:nth-child(1)").text().strip().split('\n')[0]
            title = title.replace('\t', '')

            # Getting the url of the article.
            url = item.css_first("a.wf-module-item").attributes['href']

            # This is appending the data to the result list.
            result.append(
                {
                    "title": title,
                    "description": desc,
                    "date": date.split("\u2022")[1].strip(),
                    "author": author.strip(),
                    "url_path": url,
                }
            )
        # This is creating a dictionary with the key "data" and the value of the dictionary is another dictionary
        # with the keys "status" and "segments".
        data = {
            "data": {
                "status": status,
                "segments": result
            }
        }

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
            logo = item.css_first("a.rank-item-team").css_first("img").attributes['src']
            logo = re.sub(r'\/img\/vlr\/tmp\/vlr.png', '', logo)

            # get team country
            country = item.css_first("div.rank-item-team-country").text()

            last_played = item.css_first("a.rank-item-last").text()
            last_played = last_played.replace('\n', '').replace('\t', '').split('v')[0]

            last_played_team = item.css_first("a.rank-item-last").text()
            last_played_team = last_played_team.replace('\t', '').replace('\n', '').split('o')[1]
            last_played_team = last_played_team.replace('.', '. ')

            last_played_team_logo = item.css_first("a.rank-item-last").css_first("img").attributes['src']
            # last_played_team_name = item.css_first("a.rank-item-last").css_first("span:nth-child(3)").text()

            record = item.css_first("div.rank-item-record").text()
            record = record.replace('\t', '').replace('\n', '')

            earnings = item.css_first("div.rank-item-earnings").text()
            earnings = earnings.replace('\t', '').replace('\n', '')
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
    def vlr_score():
        url = "https://www.vlr.gg/matches/results"
        resp = requests.get(url, headers=headers)
        html = HTMLParser(resp.text)
        status = resp.status_code

        result = []
        for item in html.css("a.wf-module-item"):
            url_path = item.attributes['href']

            eta = item.css_first("div.ml-eta").text() + " ago"

            rounds = item.css_first("div.match-item-event-series").text()
            rounds = rounds.replace("\u2013", "-")
            rounds = rounds.replace("\n", " ").replace("\t", "")

            tourney = item.css_first("div.match-item-event").text()
            tourney = tourney.replace("\t", " ")
            tourney = tourney.strip().split("\n")[1]
            tourney = tourney.strip()

            tourney_icon_url = item.css_first("img").attributes['src']
            tourney_icon_url = f"https:{tourney_icon_url}"

            try:
                team_array = item.css_first("div.match-item-vs").css_first("div:nth-child(2)").text()
            except:
                team_array = "TBD"
            team_array = team_array.replace("\t", " ").replace("\n", " ")
            team_array = team_array.strip().split(
                "                                  "
            )
            # 1st item in team_array is first team
            team1 = team_array[0]
            # 2nd item in team_array is first team score
            score1 = team_array[1].replace(" ", "").strip()
            # 3rd item in team_array is second team
            team2 = team_array[4].strip()
            # 4th item in team_array is second team score
            score2 = team_array[-1].replace(" ", "").strip()

            # Creating a list of the classes of the flag elements.
            flag_list = [flag_parent.attributes["class"].replace(" mod-", "_") for flag_parent in item.css('.flag')]
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
        url = f"https://www.vlr.gg/stats/?event_group_id=all&event_id=all&region={region}&country=all&min_rounds=200" \
              f"&min_rating=1550&agent=all&map_id=all&timespan={timespan}d"

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
            except:
                org = "N/A"

            # agents = [agents.css_first("img").attributes['src'] for agents in item.css("td.mod-agents")]

            # get all td items from mod-color-sq class
            color_sq = [stats.text() for stats in item.css("td.mod-color-sq")]
            acs = color_sq[0]
            kd = color_sq[1]
            kast = color_sq[2]
            adr = color_sq[3]
            kpr = color_sq[4]
            apr = color_sq[5]
            fkpr = color_sq[6]
            fdpr = color_sq[7]
            hs = color_sq[8]
            cl = color_sq[9]

            result.append(
                {
                    "player": player_name,
                    "org": org,
                    "average_combat_score": acs,
                    "kill_deaths": kd,
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
    def vlr_upcoming():
        url = "https://www.vlr.gg/matches"
        resp = requests.get(url, headers=headers)
        html = HTMLParser(resp.text)
        status = resp.status_code

        result = []
        for item in html.css("a.wf-module-item"):

            url_path = item.attributes['href']
            eta = item.css_first(".match-item-eta").text().strip()
            eta = eta.replace("\t", " ").replace("\n", " ").split()

            try:
                if eta[0] == "ago":
                    eta = "Live"
                else:
                    eta = eta[1] + " " + eta[2] + " from now"
            except:
                eta = eta[0]

            rounds = item.css_first(".match-item-event-series").text().strip()

            tourney = item.css_first(".match-item-event").text().strip()
            tourney = tourney.replace("\t", " ")
            tourney = tourney.strip().split("\n")[1]
            tourney = tourney.strip()

            tourney_icon_url = item.css_first("img").attributes['src']
            tourney_icon_url = f"https:{tourney_icon_url}"

            flag_list = [flag_parent.attributes["class"].replace(" mod-", "_") for flag_parent in item.css('.flag')]
            flag1 = flag_list[0]
            flag2 = flag_list[1]

            try:
                team_array = item.css_first("div.match-item-vs").css_first("div:nth-child(2)").text()
            except:
                team_array = "TBD"
            team_array = team_array.replace("\t", " ").replace("\n", " ")
            team_array = team_array.strip().split(
                "                                  "
            )

            team1 = "TBD"
            team2 = "TBD"
            if team_array is not None and len(team_array) > 1:
                team1 = team_array[0]
                team2 = team_array[4].strip()

            score1 = "-"
            score2 = "-"
            if team_array is not None and len(team_array) > 1:
                score1 = team_array[1].replace(" ", "").strip()
                score2 = team_array[-1].replace(" ", "").strip()

            result.append(
                {
                    "team1": team1,
                    "team2": team2,
                    "flag1": flag1,
                    "flag2": flag2,
                    "score1": score1,
                    "score2": score2,
                    "time_until_match": eta,
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


if __name__ == '__main__':
    print(Vlr.vlr_upcoming())
