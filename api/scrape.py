import requests
from bs4 import BeautifulSoup


class Vlr:
    @staticmethod
    def vlr_recent():
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Max-Age": "3600",
            "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:52.0) Gecko/20100101 Firefox/52.0",
        }
        URL = "https://www.vlr.gg/news"
        html = requests.get(URL, headers=headers).text
        response = requests.get(URL)
        soup = BeautifulSoup(html, "html.parser")
        status = response.status_code

        vlr_module = soup.find(id="wrapper").parent.find_all(
            "a", class_="wf-module-item"
        )

        result = []
        for module in vlr_module:

            # Titles of articles
            title = module.find(
                "div",
                attrs={"style": "font-weight: 700; font-size: 15px; line-height: 1.3;"},
            ).text.strip()

            # get descriptions of articles
            desc = module.find(
                "div",
                attrs={
                    "style": " font-size: 13px; padding: 5px 0; padding-bottom: 6px; line-height: 1.4;"
                },
            ).text.strip()

            # get date of articles
            date = module.find("div", class_="ge-text-light").get_text().strip()
            date = date.replace("\u2022", "").strip()
            date = date.strip().split("  ")[0]
            # date = datetime.strptime(date, "%b %d, %Y")
            # date = date.replace(tzinfo=date.tzinfo)
            # date = date.isoformat()

            # get author of articles
            author = module.find("div", class_="ge-text-light").get_text().strip()
            author = author.replace("\u2022", "").strip()
            author = author.strip().split("  ")[1]
            # remove "by" in author section
            author = author.strip().split(" ")[1]

            # get url_path of articles
            url = module["href"]
            result.append(
                {
                    "title": title,
                    "description": desc,
                    "date": date,
                    "author": author,
                    "url_path": url,
                }
            )

        segments = {"status": status, "segments": result}

        data = {"data": segments}

        if status != 200:
            raise Exception("API response: {}".format(status))
        return data

    @staticmethod
    def vlr_rankings(region: str = ""):
        region = region
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Max-Age": "3600",
            "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:52.0) Gecko/20100101 Firefox/52.0",
        }
        URL = f"https://www.vlr.gg/rankings/{region}"
        html = requests.get(URL, headers=headers).text
        response = requests.get(URL)
        soup = BeautifulSoup(html, "html.parser")
        status = response.status_code

        tbody = soup.find("tbody")
        containers = tbody.findAll("tr")
        result = []
        for container in containers:
            # column 1
            rank_container = container.find("td", {"class": "rank-item-rank"})
            rank = rank_container.a.text.strip()
            # .get_text().strip()

            # column 2 - team
            team_container = container.find("td", {"class": "rank-item-team"})
            team = team_container.a.text.strip()
            team = team.replace("\t", " ")
            team = team.strip().split("  ")[0]

            # column 2 - logo
            logo_container = container.find("td", {"class": "rank-item-team"})
            img = logo_container.find("a").find("img")
            logo = "https:" + img["src"]

            # column 2 - ctry
            ctry_container = container.find("td", {"class": "rank-item-team"})
            ctry = ctry_container.a.div.text.replace("\t", " ").strip()
            ctry = ctry.strip().split("        ")[1]

            # column 4 - last played
            streak_container = container.find(
                "td", {"class": "rank-item-streak mod-right"}
            )
            streak = streak_container.a.span.text.replace("\t", " ").strip()
            streak = streak.replace("", " ").strip()
            streak = streak.replace("W", "Wins")
            streak = streak.replace("L", "Loss(s)")

            # column 4 - last played
            record_container = container.find(
                "td", {"class": "rank-item-record mod-right"}
            )
            record = record_container.a.text.strip()
            record = record.replace("\u2013", "-")

            # column 5 - Winnings
            winnings_container = container.find(
                "td", {"class": "rank-item-earnings mod-right"}
            )
            winnings = winnings_container.a.text.strip()

            # link to team
            profile_container = container.find("td", {"class": "rank-item-team"})
            profile = profile_container.find("a")["href"]

            result.append(
                {
                    "rank": rank,
                    "team": team,
                    "country": ctry,
                    "streak": streak,
                    "record": record,
                    "winnings": winnings,
                    "logo": logo,
                    "url_path": profile,
                }
            )
        segments = {"status": status, "segments": result}

        data = {"data": segments}

        if status != 200:
            raise Exception("API response: {}".format(status))
        return data

    @staticmethod
    def vlr_score():
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Max-Age": "3600",
            "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:52.0) Gecko/20100101 Firefox/52.0",
        }
        URL = "https://www.vlr.gg/matches/results"
        html = requests.get(URL, headers=headers).text
        response = requests.get(URL)
        soup = BeautifulSoup(html, "html.parser")
        status = response.status_code

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

            # teams
            team_container = (
                module.find("div", {"class": "match-item-vs"}).get_text().strip()
            )

            # team1
            team1 = team_container.replace("\t", " ").replace("\n", " ")
            team1 = team1.strip().split("                                    ")[0]
            team1 = team1.strip().split("                                  ")[0]

            # team 2
            team2 = team_container.replace("\t", " ").replace("\n", " ")
            team2 = team2.strip().split("                                    ")[1]
            team2 = team2.strip().split("                                  ")[0]

            # score
            score_container = (
                module.find("div", {"class": "match-item-vs"}).get_text().strip()
            )

            # score 1
            score1 = score_container.replace("\t", " ").replace("\n", " ")
            score1 = score1.strip().split("                                    ")[0]
            score1 = score1.strip().split("                                  ")[1]

            # score 2
            score2 = score_container.replace("\t", " ").replace("\n", " ")
            score2 = score2.strip().split("                                    ")[1]
            score2 = score2.strip().split("                                  ")[1]

            result.append(
                {
                    "team1": team1,
                    "team2": team2,
                    "score1": score1,
                    "score2": score2,
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
    def vlr_stats(region: str = ""):
        region = region
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Max-Age": "3600",
            "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:52.0) Gecko/20100101 Firefox/52.0",
        }
        URL = f"https://www.vlr.gg/stats/?event_group_id=3&event_id=all&region={region}&country=all&min_rounds=300&agent=all&map_id=all&timespan=all"
        html = requests.get(URL, headers=headers).text
        response = requests.get(URL)
        soup = BeautifulSoup(html, "html.parser")
        status = response.status_code

        tbody = soup.find("tbody")
        containers = tbody.findAll("tr")

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
            adr = stats_container[2].div.text.strip()
            kpr = stats_container[3].div.text.strip()
            apr = stats_container[4].div.text.strip()
            fkpr = stats_container[5].div.text.strip()
            fdpr = stats_container[6].div.text.strip()
            hs = stats_container[7].div.text.strip()
            cl = stats_container[8].div.text.strip()

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
                    # "score2": score2,
                    # "time_completed": eta,
                    # "round_info": round,
                    # "tournament_name": tourney,
                    # "match_page": url_path,
                    # "tournament_icon": tourney_icon,
                }
            )
        segments = {"status": status, "segments": result}

        data = {"data": segments}

        if status != 200:
            raise Exception("API response: {}".format(status))
        return data
