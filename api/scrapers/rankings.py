import re

import requests
from selectolax.parser import HTMLParser

from utils.utils import headers, region


def vlr_rankings(region_key):
    url = "https://www.vlr.gg/rankings/" + region[str(region_key)]
    resp = requests.get(url, headers=headers)
    html = HTMLParser(resp.text)
    status = resp.status_code

    result = []
    for item in html.css("div.rank-item"):
        rank = item.css_first("div.rank-item-rank-num").text().strip()
        team = item.css_first("div.ge-text").text().split("#")[0]
        logo = item.css_first("a.rank-item-team").css_first("img").attributes["src"]
        logo = re.sub(r"\/img\/vlr\/tmp\/vlr.png", "", logo)
        country = item.css_first("div.rank-item-team-country").text()
        last_played = (
            item.css_first("a.rank-item-last")
            .text()
            .replace("\n", "")
            .replace("\t", "")
            .split("v")[0]
        )
        last_played_team = (
            item.css_first("a.rank-item-last")
            .text()
            .replace("\t", "")
            .replace("\n", "")
            .split("o")[1]
            .replace(".", ". ")
        )
        last_played_team_logo = (
            item.css_first("a.rank-item-last").css_first("img").attributes["src"]
        )
        record = (
            item.css_first("div.rank-item-record")
            .text()
            .replace("\t", "")
            .replace("\n", "")
        )
        earnings = (
            item.css_first("div.rank-item-earnings")
            .text()
            .replace("\t", "")
            .replace("\n", "")
        )

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
