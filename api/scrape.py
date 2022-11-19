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
        # for item in html.css('div.rank-'):
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
        URL = "https://www.vlr.gg/matches/results"
        html = requests.get(URL, headers=headers)
        soup = BeautifulSoup(html.content, "lxml")
        status = html.status_code

        base = soup.find(id="wrapper")

        vlr_module = base.find_all(
            "a",
            {"class": "wf-module-item"},
        )

        result = []
        for module in vlr_module:
            # link to match info
            url_path = module["href"]

            # Match completed time
            eta_container = module.find("div", {"class": "match-item-eta"})
            eta = (
                      eta_container.find("div", {"class": "ml-eta mod-completed"})
                      .get_text()
                      .strip()
                  ) + " ago"

            # round of tounranment
            round_container = module.find("div", {"class": "match-item-event text-of"})
            round = (
                round_container.find(
                    "div", {"class": "match-item-event-series text-of"}
                )
                .get_text()
                .strip()
            )
            round = round.replace("\u2013", "-")

            # tournament name
            tourney = (
                module.find("div", {"class": "match-item-event text-of"})
                .get_text()
                .strip()
            )
            tourney = tourney.replace("\t", " ")
            tourney = tourney.strip().split("\n")[1]
            tourney = tourney.strip()

            # tournament icon
            tourney_icon = module.find("img")["src"]
            tourney_icon = f"https:{tourney_icon}"

            # flags
            flags_container = module.findAll("div", {"class": "text-of"})
            flag1 = flags_container[0].span.get("class")[1]
            flag1 = flag1.replace("-", " ")
            flag1 = "flag_" + flag1.strip().split(" ")[1]

            flag2 = flags_container[1].span.get("class")[1]
            flag2 = flag2.replace("-", " ")
            flag2 = "flag_" + flag2.strip().split(" ")[1]

            # match items
            match_container = (
                module.find("div", {"class": "match-item-vs"}).get_text().strip()
            )

            match_array = match_container.replace("\t", " ").replace("\n", " ")
            match_array = match_array.strip().split(
                "                                  "
            )
            # 1st item in match_array is first team
            team1 = match_array[0]
            # 2nd item in match_array is first team score
            score1 = match_array[1]
            # 3rd item in match_array is second team                            ")[1]
            team2 = match_array[2].strip()
            # 4th item in match_array is second team score
            score2 = match_array[-1]

            result.append(
                {
                    "team1": team1,
                    "team2": team2,
                    "score1": score1,
                    "score2": score2,
                    "flag1": flag1,
                    "flag2": flag2,
                    "time_completed": eta,
                    "round_info": round,
                    "tournament_name": tourney,
                    "match_page": url_path,
                    "tournament_icon": tourney_icon,
                }
            )
        segments = {"status": status, "segments": result}

        data = {"data": segments}

        if status != 200:
            raise Exception("API response: {}".format(status))
        return data

    @staticmethod
    def vlr_stats(region: str, timespan: int):
        URL = f"https://www.vlr.gg/stats/?event_group_id=all&event_id=all&region={region}&country=all&min_rounds=200" \
              f"&min_rating=1550&agent=all&map_id=all&timespan={timespan}d"

        html = requests.get(URL, headers=headers)
        soup = BeautifulSoup(html.content, "lxml")
        status = html.status_code

        tbody = soup.find("tbody")
        containers = tbody.find_all("tr")

        result = []
        for container in containers:
            # name of player
            player_container = container.find("td", {"class": "mod-player mod-a"})
            player = player_container.a.div.text.replace("\n", " ").strip()
            player = player.split(" ")[0]

            # org name for player
            org_container = container.find("td", {"class": "mod-player mod-a"})
            org = org_container.a.div.text.replace("\n", " ").strip()
            org = org.split(" ")[-1]

            # stats for player
            stats_container = container.findAll("td", {"class": "mod-color-sq"})
            acs = stats_container[0].div.text.strip()
            kd = stats_container[1].div.text.strip()
            adr = stats_container[3].div.text.strip()
            kpr = stats_container[4].div.text.strip()
            apr = stats_container[5].div.text.strip()
            fkpr = stats_container[6].div.text.strip()
            fdpr = stats_container[7].div.text.strip()
            hs = stats_container[8].div.text.strip()
            cl = stats_container[9].div.text.strip()

            result.append(
                {
                    "player": player,
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
        URL = "https://www.vlr.gg/matches"
        html = requests.get(URL, headers=headers)
        soup = BeautifulSoup(html.content, "lxml")
        status = html.status_code

        base = soup.find(id="wrapper")

        vlr_module = base.find_all(
            "a",
            {"class": "wf-module-item"},
        )

        result = []
        for module in vlr_module:
            # link to match info
            url_path = module["href"]

            # Match completed time
            eta_container = module.find("div", {"class": "match-item-eta"})
            eta = "TBD"
            eta_time = eta_container.find("div", {"class": "ml-eta"})
            if eta_time is not None:
                eta = (
                          eta_time
                          .get_text()
                          .strip()
                      ) + " from now"

            # round of tournament
            round_container = module.find("div", {"class": "match-item-event text-of"})
            round = (
                round_container.find(
                    "div", {"class": "match-item-event-series text-of"}
                )
                .get_text()
                .strip()
            )
            round = round.replace("\u2013", "-")

            # tournament name
            tourney = (
                module.find("div", {"class": "match-item-event text-of"})
                .get_text()
                .strip()
            )
            tourney = tourney.replace("\t", " ")
            tourney = tourney.strip().split("\n")[1]
            tourney = tourney.strip()

            # tournament icon
            tourney_icon = module.find("img")["src"]
            tourney_icon = f"https:{tourney_icon}"

            # flags
            flags_container = module.findAll("div", {"class": "text-of"})
            flag1 = flags_container[0].span.get("class")[1]
            flag1 = flag1.replace("-", " ")
            flag1 = "flag_" + flag1.strip().split(" ")[1]

            flag2 = flags_container[1].span.get("class")[1]
            flag2 = flag2.replace("-", " ")
            flag2 = "flag_" + flag2.strip().split(" ")[1]

            # match items
            match_container = (
                module.find("div", {"class": "match-item-vs"}).get_text().strip()
            )

            match_array = match_container.replace("\t", " ").replace("\n", " ")
            match_array = match_array.strip().split(
                "                                  "
            )
            team1 = "TBD"
            team2 = "TBD"
            if match_array is not None and len(match_array) > 1:
                team1 = match_array[0]
                team2 = match_array[2].strip()
            result.append(
                {
                    "team1": team1,
                    "team2": team2,
                    "flag1": flag1,
                    "flag2": flag2,
                    "time_until_match": eta,
                    "round_info": round,
                    "tournament_name": tourney,
                    "match_page": url_path,
                    "tournament_icon": tourney_icon,
                }
            )
        segments = {"status": status, "segments": result}

        data = {"data": segments}

        if status != 200:
            raise Exception("API response: {}".format(status))
        return data


if __name__ == '__main__':
    print(Vlr.vlr_rankings("na"))
