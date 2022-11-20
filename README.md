# vlrggapi

An Unofficial REST API for [vlr.gg](https://www.vlr.gg/), a site for Valorant Esports match and news coverage.

Built by [Andre Saddler](https://github.com/axsddlr/)

## Current Endpoints

All endpoints are relative to [https://vlrggapi.vercel.app](https://vlrggapi.vercel.app).

### `/news`

- Method: `GET`
- Cached Time: 300 seconds (5 Minutes)
- Response:
  ```python
  {
      "data": {
          "status": 200,
          'segments': [
              {
                  'title': str,
                  'description': str,
                  'date': str,
                  'author': str,
                  'url_path': str
              }
          ],
      }
  }
  ```

### `/matches/results`

- Method: `GET`
- Cached Time: 300 seconds (5 Minutes)
- Response:
  ```python
  {
      "data": {
          "status": 200,
          'segments': [
              {
                "team1": str,
                "team2": str,
                "score1": str,
                "score2": str,
                "time_completed": str,
                "round_info": str,
                "tournament_name": str,
                "match_page": str,
                "tournament_icon": str
              }
          ],
      }
  }
  ```

### `/rankings/<region>`

- Method: `GET`
- Region: `north-america`, `europe`, `asia-pacific`, `latin-america`, `oceania`, `korea`, `mena`
- Cached Time: 300 seconds (5 Minutes)
- Response:
  ```python
  {
      "data": {
          "status": 200,
          'segments': [
              {
                  'rank': str,
                  'team': str,
                  'country': str,
                  'streak': str,
                  'record': str,
                  'winnings': str,
                  'logo': str,
                  'url_path': str
              }
          ],
      }
  }
  ```

### `/stats/<region>`

- Method: `GET`
- Cached Time: 300 seconds (5 Minutes)
- Region: `na`, `eu`, `ap`, `sa`, `oce`, `mn`
- Response:
  ```python
  {
      "data": {
          "status": 200,
          'segments': [
              {
                'title': str,
                "player": str,
                "org": str,
                "average_combat_score": str,
                "kill_deaths": str,
                "average_damage_per_round": str,
                "kills_per_round": str,
                "assists_per_round": str,
                "first_kills_per_round": str,
                "first_deaths_per_round": str,
                "headshot_percentage": str,
                "clutch_success_percentage": str
              }
          ],
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
