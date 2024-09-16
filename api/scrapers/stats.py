import requests
from selectolax.parser import HTMLParser

from utils.utils import headers


def vlr_stats(region: str, timespan: str):
    base_url = f"https://www.vlr.gg/stats/?event_group_id=all&event_id=all&region={region}&country=all&min_rounds=200&min_rating=1550&agent=all&map_id=all"
    url = (
        f"{base_url}&timespan=all"
        if timespan.lower() == "all"
        else f"{base_url}&timespan={timespan}d"
    )

    resp = requests.get(url, headers=headers)
    html = HTMLParser(resp.text)
    status = resp.status_code

    result = []
    for item in html.css("tbody tr"):
        player = item.text().replace("\t", "").replace("\n", " ").strip().split()
        player_name = player[0]
        org = player[1] if len(player) > 1 else "N/A"

        agents = [
            agents.attributes["src"].split("/")[-1].split(".")[0]
            for agents in item.css("td.mod-agents img")
        ]
        color_sq = [stats.text() for stats in item.css("td.mod-color-sq")]
        rnd = item.css_first("td.mod-rnd").text()

        result.append(
            {
                "player": player_name,
                "org": org,
                "agents": agents,
                "rounds_played": rnd,
                "rating": color_sq[0],
                "average_combat_score": color_sq[1],
                "kill_deaths": color_sq[2],
                "kill_assists_survived_traded": color_sq[3],
                "average_damage_per_round": color_sq[4],
                "kills_per_round": color_sq[5],
                "assists_per_round": color_sq[6],
                "first_kills_per_round": color_sq[7],
                "first_deaths_per_round": color_sq[8],
                "headshot_percentage": color_sq[9],
                "clutch_success_percentage": color_sq[10],
            }
        )

    segments = {"status": status, "segments": result}
    data = {"data": segments}

    if status != 200:
        raise Exception("API response: {}".format(status))
    return data
