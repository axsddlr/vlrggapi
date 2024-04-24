# vlrggapi

An Unofficial REST API for [vlr.gg](https://www.vlr.gg/), a site for Valorant Esports match and news coverage.

Built by [Andre Saddler](https://github.com/axsddlr/)

## Current Endpoints

All endpoints are relative to [https://vlrggapi.vercel.app](https://vlrggapi.vercel.app).

### `/news`

- Method: `GET`
- Description: Fetches the latest news articles related to Valorant Esports.
- Response Example:

```json
{
  "data": {
    "status": 200,
    "segments": [
      {
        "title": "Riot introduces changes to Premier, adds new Invite Division",
        "description": "Riot looks to streamline Premier promotions and Challengers qualification with upcoming changes.",
        "date": "April 23, 2024",
        "author": "thothgow",
        "url_path": "https://vlr.gg/336099/riot-introduces-changes-to-premier-adds-new-invite-division"
      },
      {
        "title": "jakee announces competitive retirement",
        "description": "From Collegiate to the Tier 1 stage, the Controller main had seen it all.",
        "date": "April 21, 2024",
        "author": "ChickenJoe",
        "url_path": "https://vlr.gg/334341/jakee-announces-competitive-retirement"
      }
    ]
  }
}
```

### `/stats/{region}/{timespan}`

- Method: `GET`
- Description: Fetches player statistics for a specific region and timespan.
- Parameters:
  - `region`: Region shortnames (e.g., "na" for North America).
  - `timespan`: Time span in days (e.g., "30" for the last 30 days).

- Response Example:

```json
{
  "data": {
    "status": 200,
    "segments": [
      {
        "player": "corey",
        "org": "TTR",
        "rating": "1.18",
        "average_combat_score": "235.2",
        "kill_deaths": "1.19",
        "kill_assists_survived_traded": "72%",
        "average_damage_per_round": "158.4",
        "kills_per_round": "0.81",
        "assists_per_round": "0.29",
        "first_kills_per_round": "0.19",
        "first_deaths_per_round": "0.13",
        "headshot_percentage": "26%",
        "clutch_success_percentage": "28%"
      },
      {
        "player": "wedid",
        "org": "TTR",
        "rating": "1.15",
        "average_combat_score": "216.1",
        "kill_deaths": "1.11",
        "kill_assists_survived_traded": "72%",
        "average_damage_per_round": "141.0",
        "kills_per_round": "0.76",
        "assists_per_round": "0.39",
        "first_kills_per_round": "0.07",
        "first_deaths_per_round": "0.10",
        "headshot_percentage": "32%",
        "clutch_success_percentage": "19%"
      }
    ]
  }
}
```

### `/rankings/{region}`

- Method: `GET`
- Description: Fetches rankings for a specific region.
- Parameters:
  - `region`: Region shortnames (e.g., "na" for North America).
- Response Example:

```json
{
  "status": 200,
  "data": [
    {
      "rank": "1",
      "team": "M80",
      "country": "Canada",
      "last_played": "4d ago",
      "last_played_team": "vs. Turtle Tr",
      "last_played_team_logo": "//owcdn.net/img/63d552c5dd028.png",
      "record": "4-1",
      "earnings": "$104,850",
      "logo": "//owcdn.net/img/63d91e60a84bc.png"
    },
    {
      "rank": "2",
      "team": "Sentinels",
      "country": "United States",
      "last_played": "22h ago",
      "last_played_team": "vs. Evil Geniuses",
      "last_played_team_logo": "//owcdn.net/img/62a409ad29351.png",
      "record": "7-3",
      "earnings": "$295,500",
      "logo": "//owcdn.net/img/62875027c8e06.png"
    }
  ]
}
```

### `/match`

- Method: `GET`
- Description: Fetches matches based on the query parameter provided.
- Query Parameters:
  - `q`: Type of matches to fetch ("upcoming", "live_score", "results").
- Response Example for `q=upcoming`:

```json
{
  "data": {
    "status": 200,
    "segments": [
      {
        "team1": "G2 Esports",
        "team2": "Leviatán",
        "flag1": "flag_us",
        "flag2": "flag_cl",
        "time_until_match": "51m from now",
        "match_series": "Regular Season: Week 3",
        "match_event": "Champions Tour 2024: Americas Stage 1",
        "unix_timestamp": "2024-04-24 21:00:00",
        "match_page": "https://www.vlr.gg/314642/g2-esports-vs-leviat-n-champions-tour-2024-americas-stage-1-w3"
      }
    ]
  }
}
```

- Response Example for `q=live_score`:

```json
{
  "data": {
    "status": 200,
    "segments": [
      {
        "team1": "Team 1 Name",
        "team2": "Team 2 Name",
        "flag1": "Country Flag of Team 1",
        "flag2": "Country Flag of Team 2",
        "score1": "Team 1 Score",
        "score2": "Team 2 Score",
        "team1_round_ct": "Team 1 CT-side rounds",
        "team1_round_t": "Team 1 T-side rounds",
        "team2_round_ct": "Team 2 CT-side rounds",
        "team2_round_t": "Team 2 T-side rounds",
        "map_number": "Current map number in the series",
        "current_map": "Current map being played",
        "time_until_match": "LIVE",
        "match_event": "Event name",
        "match_series": "Match series",
        "unix_timestamp": "Match start time in UNIX timestamp",
        "match_page": "URL to the match page"
      }
    ]
  }
}
```

- Response Example for `q=results`:

```json
{
  "data": {
    "status": 200,
    "segments": [
      {
        "team1": "Team Vitality",
        "team2": "Gentle Mates",
        "score1": "0",
        "score2": "2",
        "flag1": "flag_eu",
        "flag2": "flag_fr",
        "time_completed": "2h 44m ago",
        "round_info": "Regular Season-Week 4",
        "tournament_name": "Champions Tour 2024: EMEA Stage 1",
        "match_page": "/318931/team-vitality-vs-gentle-mates-champions-tour-2024-emea-stage-1-w4",
        "tournament_icon": "https://owcdn.net/img/65ab59620a233.png"
      }
    ]
  }
}
```

### `/health`

- Method: `GET`
- Description: Returns the health status of the API.
- Response: `Healthy: OK`

## Installation

### Source

```python

git clone https://github.com/axsddlr/vlrggapi/
cd vlrggapi
pip3 install -r requirements.txt

```

### Usage

```markdown

python3 main.py

```

## Built With

- [FastAPI](https://fastapi.tiangolo.com/)
- [Requests](https://requests.readthedocs.io/en/master/)
- [Selectolax](https://github.com/rushter/selectolax)
- [uvicorn](https://www.uvicorn.org/)

## Contributing

Feel free to submit a [pull request](https://github.com/axsddlr/vlrggapi/pull/new/master) or an [issue](https://github.com/axsddlr/vlrggapi/issues/new)!

## License

The MIT License (MIT)
