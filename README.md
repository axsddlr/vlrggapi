# vlrggapi

An Unofficial REST API for [vlr.gg](https://www.vlr.gg/), a site for Valorant Esports match and news coverage.

Built by [Andre Saddler](https://github.com/axsddlr/)

## Current Endpoints

All endpoints are relative to [https://vlrggapi.vercel.app](https://vlrggapi.vercel.app).

### `/news`

- Method: `GET`
- Description: Fetches the latest news articles related to Valorant Esports.
- Example: `GET https://vlrggapi.vercel.app/news`
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

### `/stats`

- Method: `GET`
- Description: Fetches player statistics for a specific region and timespan.
- Query Parameters:
  - `region`: Region shortname (e.g., "na" for North America).
  - `timespan`: Time span in days (e.g., "30" for the last 30 days, or "all" for all time).
- Example: `GET https://vlrggapi.vercel.app/stats?region=na&timespan=30`

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

### `/rankings`

- Method: `GET`
- Description: Fetches rankings for a specific region.
- Query Parameters:
  - `region`: Region shortname (e.g., "na" for North America).
- Example: `GET https://vlrggapi.vercel.app/rankings?region=na`
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
- Examples:
  - Upcoming matches: `GET https://vlrggapi.vercel.app/match?q=upcoming`
  - Live scores: `GET https://vlrggapi.vercel.app/match?q=live_score`
  - Match results: `GET https://vlrggapi.vercel.app/match?q=results`
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
        "team1_logo": "URL to Team 1 logo",
        "team2_logo": "URL to Team 2 logo",
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

### `/events`

- Method: `GET`
- Description: Fetches Valorant events from vlr.gg with filtering and pagination options.
- Query Parameters:
  - `q`: Event type filter (optional)
    - `"upcoming"`: Show only upcoming events
    - `"completed"`: Show only completed events
    - No parameter or other values: Show both upcoming and completed events
  - `page`: Page number for pagination (optional, default: 1, applies to completed events only)
- Examples:
  - All events: `GET https://vlrggapi.vercel.app/events`
  - Upcoming only: `GET https://vlrggapi.vercel.app/events?q=upcoming`
  - Completed only: `GET https://vlrggapi.vercel.app/events?q=completed`
  - Completed events page 2: `GET https://vlrggapi.vercel.app/events?q=completed&page=2`
- Response Example:

```json
{
  "data": {
    "status": 200,
    "segments": [
      {
        "title": "VCT 2025: Pacific Stage 2",
        "status": "ongoing",
        "prize": "$250,000",
        "dates": "Jul 15—Aug 31",
        "region": "kr",
        "thumb": "https://owcdn.net/img/640f5ae002674.png",
        "url_path": "https://www.vlr.gg/event/2500/vct-2025-pacific-stage-2"
      },
      {
        "title": "VCT 2025: China Stage 2",
        "status": "ongoing",
        "prize": "TBD",
        "dates": "Jul 3—Aug 24",
        "region": "cn",
        "thumb": "https://owcdn.net/img/65dd97cea9a25.png",
        "url_path": "https://www.vlr.gg/event/2499/vct-2025-china-stage-2"
      }
    ]
  }
}
```

### `/health`

- Method: `GET`
- Description: Returns the health status of the API and vlr.gg website.
- Example: `GET https://vlrggapi.vercel.app/health`
- Response Example:

```json
{
  "https://vlrggapi.vercel.app": {
    "status": "Healthy",
    "status_code": 200
  },
  "https://vlr.gg": {
    "status": "Healthy",
    "status_code": 200
  }
}
```

The response includes the status ("Healthy" or "Unhealthy") and the HTTP status code for both the API and the vlr.gg website. If a site is unreachable, the status will be "Unhealthy" and the status_code will be null.

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
