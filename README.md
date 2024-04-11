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
          "title": "Article Title",
          "description": "Brief description of the article",
          "date": "Publication Date",
          "author": "Author Name",
          "url_path": "/path/to/full/article"
        }
      ]
    }
  }
  ```

### `/match/results`
- Method: `GET`
- Description: Fetches recent match results.
- Response Example:
  ```json
  {
    "data": {
      "status": 200,
      "segments": [
        {
          "team1": "Team 1 Name",
          "team2": "Team 2 Name",
          "score1": "Team 1 Score",
          "score2": "Team 2 Score",
          "flag1": "Team 1 Country Flag",
          "flag2": "Team 2 Country Flag",
          "time_completed": "Match Completion Time",
          "round_info": "Round Information",
          "tournament_name": "Tournament Name",
          "match_page": "/path/to/match",
          "tournament_icon": "URL to Tournament Icon"
        }
      ]
    }
  }
  ```

### `/rankings/{region}`
- Method: `GET`
- Description: Fetches rankings for a specific region.
- Response Example:
  ```json
  {
    "data": {
      "status": 200,
      "segments": [
        {
          "rank": "Team Rank",
          "team": "Team Name",
          "country": "Country",
          "last_played": "Last Played Match",
          "last_played_team": "Opponent Team Name",
          "last_played_team_logo": "URL to Opponent Team Logo",
          "record": "Win-Loss Record",
          "earnings": "Total Earnings",
          "logo": "URL to Team Logo"
        }
      ]
    }
  }
  ```

### `/stats/{region}/{timespan}`
- Method: `GET`
- Description: Fetches player statistics for a specific region and timespan.
- Response Example:
  ```json
  {
    "data": {
      "status": 200,
      "segments": [
        {
          "player": "Player Name",
          "org": "Organization Name",
          "average_combat_score": "Average Combat Score",
          "kill_deaths": "Kill/Death Ratio",
          "average_damage_per_round": "Average Damage Per Round",
          "kills_per_round": "Kills Per Round",
          "assists_per_round": "Assists Per Round",
          "first_kills_per_round": "First Kills Per Round",
          "first_deaths_per_round": "First Deaths Per Round",
          "headshot_percentage": "Headshot Percentage",
          "clutch_success_percentage": "Clutch Success Percentage"
        }
      ]
    }
  }
  ```

### `/match/upcoming`
- Method: `GET`
- Description: Fetches upcoming matches.
- Response Example:
  ```json
  {
    "data": {
      "status": 200,
      "segments": [
        {
          "team1": "Team 1 Name",
          "team2": "Team 2 Name",
          "flag1": "Team 1 Country Flag",
          "flag2": "Team 2 Country Flag",
          "score1": "-",
          "score2": "-",
          "time_until_match": "Time Until Match",
          "round_info": "Round Information",
          "tournament_name": "Tournament Name",
          "match_page": "/path/to/match",
          "tournament_icon": "URL to Tournament Icon"
        }
      ]
    }
  }
  ```

### `/match/live_score`
- Method: `GET`
- Description: Fetches live scores for ongoing matches.
- Response Example:
  ```json
  {
    "data": {
      "status": 200,
      "segments": [
        {
          "team1": "Team 1 Name",
          "team2": "Team 2 Name",
          "flag1": "Team 1 Country Flag",
          "flag2": "Team 2 Country Flag",
          "score1": "Team 1 Current Score",
          "score2": "Team 2 Current Score",
          "team1_round_ct": "Team 1 CT Rounds",
          "team1_round_t": "Team 1 T Rounds",
          "team2_round_ct": "Team 2 CT Rounds",
          "team2_round_t": "Team 2 T Rounds",
          "time_until_match": "LIVE",
          "round_info": "Round Information",
          "tournament_name": "Tournament Name",
          "unix_timestamp": "Match Start Time",
          "match_page": "/path/to/match"
        }
      ]
    }
  }
  ```

## Installation

### Source

```
$ git clone https://github.com/axsddlr/vlrggapi/
$ cd vlrggapi
$ pip3 install -r requirements.txt
```

### Usage

```
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
