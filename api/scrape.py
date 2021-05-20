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
    def vlr_rankings():
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Max-Age": "3600",
            "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:52.0) Gecko/20100101 Firefox/52.0",
        }
        URL = "https://www.vlr.gg/rankings/north-america"
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
