# vlrggapi

An Unofficial REST API for [vlr.gg](https://www.vlr.gg/), a site for Valorant Esports match and news coverage.

Built by [Andre Saddler](https://github.com/axsddlr/)

## What's New in V2

- **Standardized responses** — all V2 endpoints return `{"status": "success", "data": {...}}`
- **Input validation** — invalid parameters return HTTP 400 with clear error messages
- **Per-endpoint caching** — in-memory TTL cache reduces load on vlr.gg
- **Async HTTP** — scrapers use `httpx` for non-blocking I/O

## API Versions

Both the original and V2 endpoints coexist. The original endpoints (`/news`, `/match`, etc.) are preserved unchanged for backwards compatibility. V2 endpoints (`/v2/news`, `/v2/match`, etc.) are the recommended API going forward.

| Feature | Original | V2 |
|---|---|---|
| Response shape | Varies per endpoint | Consistent `{"status": "success", "data": {...}}` |
| Input validation | None | HTTP 400 on invalid params |
| Caching | None | Per-endpoint TTL cache |

Interactive Swagger docs are available at `/`.

## V2 Endpoints

### `GET /v2/news`

Fetches the latest Valorant esports news.

- **Params:** none
- **Cache:** 10 minutes

```
GET /v2/news
```

```json
{
  "status": "success",
  "data": {
    "status": 200,
    "segments": [
      {
        "title": "Article title",
        "description": "Article summary",
        "date": "April 23, 2024",
        "author": "author_name",
        "url_path": "https://vlr.gg/..."
      }
    ]
  }
}
```

### `GET /v2/match`

Fetches match data by type.

- **Params:**
  - `q` (required) — `upcoming`, `upcoming_extended`, `live_score`, or `results`
  - `num_pages` — pages to scrape (default: 1)
  - `from_page` / `to_page` — page range (overrides `num_pages`)
  - `max_retries` — retry attempts per page (default: 3)
  - `request_delay` — delay between requests in seconds (default: 1.0)
  - `timeout` — request timeout in seconds (default: 30)
- **Cache:** 30s (live_score), 5min (upcoming), 1hr (results)

```
GET /v2/match?q=upcoming
```

```json
{
  "status": "success",
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
        "match_page": "https://www.vlr.gg/..."
      }
    ]
  }
}
```

### `GET /v2/rankings`

Fetches team rankings for a region.

- **Params:**
  - `region` (required) — see [Region Codes](#region-codes)
- **Cache:** 1 hour

```
GET /v2/rankings?region=na
```

```json
{
  "status": "success",
  "data": {
    "status": 200,
    "segments": [
      {
        "rank": "1",
        "team": "Sentinels",
        "country": "United States",
        "last_played": "22h ago",
        "record": "7-3",
        "earnings": "$295,500",
        "logo": "//owcdn.net/img/..."
      }
    ]
  }
}
```

### `GET /v2/stats`

Fetches player statistics for a region and timespan.

- **Params:**
  - `region` (required) — see [Region Codes](#region-codes)
  - `timespan` (required) — `30`, `60`, `90`, or `all`
- **Cache:** 30 minutes

```
GET /v2/stats?region=na&timespan=30
```

```json
{
  "status": "success",
  "data": {
    "status": 200,
    "segments": [
      {
        "player": "player_name",
        "org": "ORG",
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
      }
    ]
  }
}
```

### `GET /v2/events`

Fetches Valorant events.

- **Params:**
  - `q` (optional) — `upcoming` or `completed` (omit for both)
  - `page` (optional) — page number for completed events (default: 1)
- **Cache:** 30 minutes

```
GET /v2/events?q=upcoming
```

```json
{
  "status": "success",
  "data": {
    "status": 200,
    "segments": [
      {
        "title": "VCT 2025: Pacific Stage 2",
        "status": "ongoing",
        "prize": "$250,000",
        "dates": "Jul 15—Aug 31",
        "region": "kr",
        "url_path": "https://www.vlr.gg/event/..."
      }
    ]
  }
}
```

### `GET /v2/health`

Returns health status of the API and vlr.gg.

- **Params:** none
- **Cache:** none

```
GET /v2/health
```

```json
{
  "status": "success",
  "data": {
    "https://vlrggapi.vercel.app": {
      "status": "Healthy",
      "status_code": 200
    },
    "https://vlr.gg": {
      "status": "Healthy",
      "status_code": 200
    }
  }
}
```

## Original Endpoints

These endpoints are preserved for backwards compatibility. See the Swagger docs at `/` for full details.

| Route | Query Params | Notes |
|---|---|---|
| `GET /news` | — | |
| `GET /match` | `q` (upcoming/upcoming_extended/live_score/results), pagination params | |
| `GET /stats` | `region`, `timespan` | |
| `GET /rankings` | `region` | Returns `{"status": int, "data": [...]}` (different shape) |
| `GET /events` | `q` (upcoming/completed), `page` | |
| `GET /health` | — | |

Most original endpoints return `{"data": {"status": int, "segments": [...]}}`. The `/rankings` endpoint returns `{"status": int, "data": [...]}` instead.

## Region Codes

| Code | Region |
|---|---|
| `na` | North America |
| `eu` | Europe |
| `ap` | Asia Pacific |
| `la` | Latin America |
| `la-s` | Latin America South |
| `la-n` | Latin America North |
| `oce` | Oceania |
| `kr` | Korea |
| `mn` | MENA |
| `gc` | Game Changers |
| `br` | Brazil |
| `cn` | China |
| `jp` | Japan |
| `col` | Collegiate |

## Validation & Error Handling

V2 endpoints validate input and return HTTP 400 with descriptive error messages:

- **Invalid region** — must be one of the codes listed above
- **Invalid timespan** — must be `30`, `60`, `90`, or `all`
- **Invalid match query** — must be `upcoming`, `upcoming_extended`, `live_score`, or `results`
- **Invalid event query** — must be `upcoming` or `completed`

```json
{
  "detail": "Invalid region 'xyz'. Valid regions: ap, br, cn, col, eu, gc, jp, kr, la, la-n, la-s, mn, na, oce"
}
```

Original endpoints do not validate input (preserved for backwards compatibility).

## Caching

V2 endpoints use an in-memory TTL cache to reduce load on vlr.gg. Cache durations per endpoint:

| Data | TTL |
|---|---|
| Live scores | 30 seconds |
| Upcoming matches | 5 minutes |
| News | 10 minutes |
| Stats | 30 minutes |
| Events | 30 minutes |
| Rankings | 1 hour |
| Results | 1 hour |

Original endpoints are not cached.

## Installation

```bash
git clone https://github.com/axsddlr/vlrggapi/
cd vlrggapi
pip install -r requirements.txt
```

### Run locally

```bash
python main.py
```

Serves on `http://0.0.0.0:3001`.

### Docker

```bash
docker-compose up --build
```

### Testing

```bash
python -m pytest tests/ -v
```

## Built With

- [FastAPI](https://fastapi.tiangolo.com/)
- [httpx](https://www.python-httpx.org/)
- [Selectolax](https://github.com/rushter/selectolax)
- [cachetools](https://github.com/tkem/cachetools)
- [uvicorn](https://www.uvicorn.org/)

## Contributing

Feel free to submit a [pull request](https://github.com/axsddlr/vlrggapi/pull/new/master) or an [issue](https://github.com/axsddlr/vlrggapi/issues/new)!

## License

The MIT License (MIT)
