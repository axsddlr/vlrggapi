# vlrggapi

An Unofficial REST API for [vlr.gg](https://www.vlr.gg/), a site for Valorant Esports match and news coverage.

Built by [Andre Saddler](https://github.com/axsddlr/)

## Support

If this API helps your projects, you can support ongoing maintenance and development on Ko-fi.

<a href='https://ko-fi.com/J3J1IR40C' target='_blank'><img height='36' style='border:0px;height:36px;' src='https://storage.ko-fi.com/cdn/kofi6.png?v=6' border='0' alt='Buy Me a Coffee at ko-fi.com' /></a>

## Quick Start

- **Public base URL:** `https://vlrggapi.vercel.app`
- **Local base URL:** `http://127.0.0.1:3001`
- **Interactive docs:** `/`
- **Version info:** `/version`

```bash
curl https://vlrggapi.vercel.app/v2/news
curl "https://vlrggapi.vercel.app/v2/match?q=live_score"
curl "http://127.0.0.1:3001/v2/player?id=9&timespan=all"
```

## Highlights

- **V2-first API** - consistent response envelopes, validation, and per-endpoint caching
- **Backwards compatibility** - original unversioned endpoints are still available
- **Deep match coverage** - detailed match, player, team, and event match endpoints
- **Operational guardrails** - async HTTP, rate limiting, and bounded expensive scrapes

## What's New

### Match Details, Player Profiles & Team Profiles

New endpoints provide deep coverage of individual matches, players, and teams:

- **Match details** — per-map player stats (K/D/A, ACS, rating), round-by-round data, kill matrix, economy breakdown, head-to-head history
- **Player profiles** — agent stats (17 metrics), current/past teams, event placements, total winnings, match history
- **Team profiles** — roster with roles/captain status, VLR rating/rank, event placements, total winnings, match history, roster transactions
- **Event matches** — full match list for any event with scores and VOD links

### V2 API

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

## Operational Notes

- **Recommended base path** - use `/v2` for new integrations
- **Current version endpoint** - `GET /version` returns the current API version and default API
- **Rate limit** - requests are limited to `600/minute`
- **Error handling** - V2 returns HTTP 400 for invalid input and propagates upstream failures with HTTP error codes
- **Deployment targets** - Vercel for the hosted API, Docker for containerized self-hosting

## V2 Endpoint Overview

| Area | Route | Purpose |
|---|---|---|
| News | `GET /v2/news` | Latest Valorant esports news |
| Matches | `GET /v2/match` | Upcoming, live, extended upcoming, and results feeds |
| Match detail | `GET /v2/match/details` | Per-map stats, rounds, performance, economy, streams |
| Rankings | `GET /v2/rankings` | Regional team rankings |
| Stats | `GET /v2/stats` | Regional player stats by timespan |
| Events | `GET /v2/events` | Upcoming and completed events |
| Event matches | `GET /v2/events/matches` | Match list for a specific event |
| Players | `GET /v2/player`, `GET /v2/player/matches` | Player profile and match history |
| Teams | `GET /v2/team`, `GET /v2/team/matches`, `GET /v2/team/transactions` | Team profile, match history, roster changes |
| Health | `GET /v2/health` | Runtime and upstream health status |

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

### `GET /v2/match/details`

Fetches detailed data for a specific match.

- **Params:**
  - `match_id` (required) — VLR.GG match ID
- **Cache:** 5 minutes (30s for live matches)

```
GET /v2/match/details?match_id=595657
```

```json
{
  "status": "success",
  "data": {
    "event": { "name": "Champions Tour 2024: Americas Stage 1", "series": "Regular Season: Week 3" },
    "teams": [
      { "name": "Sentinels", "score": 2, "logo": "//owcdn.net/img/..." },
      { "name": "Cloud9", "score": 1, "logo": "//owcdn.net/img/..." }
    ],
    "maps": [
      {
        "map_name": "Ascent",
        "picked_by": "Sentinels",
        "duration": "28:41",
        "score": { "team1": { "total": 13, "ct": 8, "t": 5 }, "team2": { "total": 9, "ct": 4, "t": 5 } },
        "players": [
          {
            "team": "Sentinels",
            "player": "TenZ",
            "agent": "Jett",
            "rating": "1.32",
            "acs": "267",
            "kills": "24",
            "deaths": "15",
            "assists": "3",
            "kast": "77%",
            "adr": "172.3",
            "hs_pct": "32%",
            "fk": "4",
            "fd": "2"
          }
        ]
      }
    ],
    "rounds": [
      { "round_number": 1, "team1_win": true, "team2_win": false, "team1_side": "ct", "team2_side": "t" }
    ],
    "head_to_head": [
      { "event": "VCT Americas", "match": "Sentinels vs Cloud9", "score": "2-1" }
    ],
    "streams": [{ "name": "English", "link": "https://twitch.tv/..." }],
    "performance": {
      "kill_matrix": [{ "player": "TenZ", "kills_against": { "opponent1": 5 } }],
      "advanced_stats": [{ "player": "TenZ", "2k": 3, "3k": 1, "4k": 0, "5k": 0, "clutch_1v1": 1 }]
    },
    "economy": [
      { "team": "Sentinels", "pistol": "50%", "eco": "33%", "semi_buy": "60%", "full_buy": "72%" }
    ]
  }
}
```

### `GET /v2/player`

Fetches a player profile.

- **Params:**
  - `id` (required) — VLR.GG player ID
  - `timespan` — `30d`, `60d`, `90d`, or `all` (default: `90d`)
- **Cache:** 30 minutes

```
GET /v2/player?id=9&timespan=all
```

```json
{
  "status": "success",
  "data": {
    "info": {
      "name": "TenZ",
      "real_name": "Tyson Ngo",
      "avatar": "https://owcdn.net/img/...",
      "country": "Canada",
      "socials": [{ "platform": "twitter", "url": "https://twitter.com/TenZOfficial" }]
    },
    "current_teams": [{ "name": "Sentinels", "tag": "SEN", "status": "Active" }],
    "past_teams": [{ "name": "Cloud9", "tag": "C9", "dates": "2020–2021" }],
    "agent_stats": [
      {
        "agent": "Jett",
        "use_count": 150,
        "use_pct": "42%",
        "rounds": 3200,
        "rating": "1.15",
        "acs": "245.3",
        "kd": "1.18",
        "adr": "162.1",
        "kast": "71%",
        "kpr": "0.82",
        "apr": "0.28",
        "fkpr": "0.20",
        "fdpr": "0.14",
        "kills": 2624,
        "deaths": 2224,
        "assists": 896,
        "fk": 640,
        "fd": 448
      }
    ],
    "event_placements": [
      { "event": "Champions 2024", "placement": "1st", "prize": "$100,000", "team": "Sentinels" }
    ],
    "total_winnings": "$177,650"
  }
}
```

### `GET /v2/player/matches`

Fetches paginated match history for a player.

- **Params:**
  - `id` (required) — VLR.GG player ID
  - `page` — page number (default: 1)
- **Cache:** 10 minutes

```
GET /v2/player/matches?id=9&page=1
```

```json
{
  "status": "success",
  "data": {
    "matches": [
      {
        "match_id": "595657",
        "event": "Champions Tour 2024: Americas Stage 1",
        "teams": { "team1": "Sentinels", "team2": "Cloud9" },
        "score": "2-1",
        "date": "Apr 24, 2024"
      }
    ],
    "page": 1
  }
}
```

### `GET /v2/team`

Fetches a team profile.

- **Params:**
  - `id` (required) — VLR.GG team ID
- **Cache:** 30 minutes

```
GET /v2/team?id=2
```

```json
{
  "status": "success",
  "data": {
    "info": {
      "name": "Sentinels",
      "tag": "SEN",
      "logo": "https://owcdn.net/img/...",
      "country": "United States",
      "socials": [{ "platform": "twitter", "url": "https://twitter.com/Sentinels" }]
    },
    "rating": { "vlr_rating": "1850", "rank": "1", "region": "na" },
    "roster": [
      {
        "alias": "TenZ",
        "real_name": "Tyson Ngo",
        "role": "Duelist",
        "is_captain": false,
        "avatar": "https://owcdn.net/img/..."
      }
    ],
    "event_placements": [
      { "event": "Champions 2024", "placement": "1st", "prize": "$100,000" }
    ],
    "total_winnings": "$1,194,000"
  }
}
```

### `GET /v2/team/matches`

Fetches paginated match history for a team.

- **Params:**
  - `id` (required) — VLR.GG team ID
  - `page` — page number (default: 1)
- **Cache:** 10 minutes

```
GET /v2/team/matches?id=2&page=1
```

```json
{
  "status": "success",
  "data": {
    "matches": [
      {
        "match_id": "595657",
        "event": "Champions Tour 2024: Americas Stage 1",
        "teams": { "team1": "Sentinels", "team2": "Cloud9" },
        "score": "2-1",
        "date": "Apr 24, 2024"
      }
    ],
    "page": 1
  }
}
```

### `GET /v2/team/transactions`

Fetches roster transaction history for a team.

- **Params:**
  - `id` (required) — VLR.GG team ID
- **Cache:** 1 hour

```
GET /v2/team/transactions?id=2
```

```json
{
  "status": "success",
  "data": {
    "transactions": [
      {
        "date": "Jan 15, 2024",
        "action": "join",
        "player": "TenZ",
        "position": "Duelist"
      }
    ]
  }
}
```

### `GET /v2/events/matches`

Fetches the match list for a specific event.

- **Params:**
  - `event_id` (required) — VLR.GG event ID
- **Cache:** 10 minutes

```
GET /v2/events/matches?event_id=2095
```

```json
{
  "status": "success",
  "data": {
    "matches": [
      {
        "match_id": "595657",
        "teams": [
          { "name": "Sentinels", "score": "2", "is_winner": true },
          { "name": "Cloud9", "score": "1", "is_winner": false }
        ],
        "event_series": "Grand Final",
        "vods": [{ "name": "VOD", "url": "https://youtube.com/..." }],
        "date": "Apr 24, 2024"
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

These endpoints are preserved for backwards compatibility. Most return `{"data": {"status": int, "segments": [...]}}`. The `/rankings` endpoint returns `{"status": int, "data": [...]}` instead.

| Route | Query Params |
|---|---|
| `GET /news` | — |
| `GET /match` | `q` (upcoming/upcoming_extended/live_score/results), pagination params |
| `GET /match/details` | `match_id` |
| `GET /stats` | `region`, `timespan` |
| `GET /rankings` | `region` |
| `GET /events` | `q` (upcoming/completed), `page` |
| `GET /events/matches` | `event_id` |
| `GET /player` | `id`, `timespan` |
| `GET /player/matches` | `id`, `page` |
| `GET /team` | `id` |
| `GET /team/matches` | `id`, `page` |
| `GET /team/transactions` | `id` |
| `GET /health` | — |

<details>
<summary><code>GET /news</code> — response example</summary>

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
      }
    ]
  }
}
```

</details>

<details>
<summary><code>GET /match?q=upcoming</code> — response example</summary>

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
        "match_page": "https://www.vlr.gg/..."
      }
    ]
  }
}
```

</details>

<details>
<summary><code>GET /match?q=live_score</code> — response example</summary>

```json
{
  "data": {
    "status": 200,
    "segments": [
      {
        "team1": "Team 1",
        "team2": "Team 2",
        "flag1": "flag_xx",
        "flag2": "flag_xx",
        "team1_logo": "https://...",
        "team2_logo": "https://...",
        "score1": "1",
        "score2": "0",
        "team1_round_ct": "7",
        "team1_round_t": "6",
        "team2_round_ct": "5",
        "team2_round_t": "4",
        "map_number": "1",
        "current_map": "Ascent",
        "time_until_match": "LIVE",
        "match_event": "Event name",
        "match_series": "Series name",
        "unix_timestamp": "1713996000",
        "match_page": "https://www.vlr.gg/..."
      }
    ]
  }
}
```

</details>

<details>
<summary><code>GET /match?q=results</code> — response example</summary>

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
        "match_page": "/318931/team-vitality-vs-gentle-mates-...",
        "tournament_icon": "https://owcdn.net/img/..."
      }
    ]
  }
}
```

</details>

<details>
<summary><code>GET /stats?region=na&timespan=30</code> — response example</summary>

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
      }
    ]
  }
}
```

</details>

<details>
<summary><code>GET /rankings?region=na</code> — response example</summary>

Note: `/rankings` uses a different response shape than other endpoints.

```json
{
  "status": 200,
  "data": [
    {
      "rank": "1",
      "team": "Sentinels",
      "country": "United States",
      "last_played": "22h ago",
      "last_played_team": "vs. Evil Geniuses",
      "last_played_team_logo": "//owcdn.net/img/...",
      "record": "7-3",
      "earnings": "$295,500",
      "logo": "//owcdn.net/img/..."
    }
  ]
}
```

</details>

<details>
<summary><code>GET /events?q=upcoming</code> — response example</summary>

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
        "thumb": "https://owcdn.net/img/...",
        "url_path": "https://www.vlr.gg/event/..."
      }
    ]
  }
}
```

</details>

<details>
<summary><code>GET /health</code> — response example</summary>

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

</details>

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
- **Invalid player timespan** — must be `30d`, `60d`, `90d`, or `all`
- **Invalid match query** — must be `upcoming`, `upcoming_extended`, `live_score`, or `results`
- **Invalid event query** — must be `upcoming` or `completed`
- **Invalid ID** — `match_id`, `event_id`, player `id`, and team `id` must be positive integers

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
| Match detail (live) | 30 seconds |
| Upcoming matches | 5 minutes |
| Match detail | 5 minutes |
| News | 10 minutes |
| Player matches | 10 minutes |
| Team matches | 10 minutes |
| Event matches | 10 minutes |
| Stats | 30 minutes |
| Events | 30 minutes |
| Player profile | 30 minutes |
| Team profile | 30 minutes |
| Rankings | 1 hour |
| Results | 1 hour |
| Team transactions | 1 hour |

Original endpoints are not cached.

## Installation

### Requirements

- Python `3.11` (matches `.python-version`, CI, and the Docker image)
- `pip`

```bash
git clone https://github.com/axsddlr/vlrggapi/
cd vlrggapi
python -m venv .venv
```

Activate the virtual environment:

```bash
# macOS / Linux
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
pip install -r requirements.txt
```

### Run locally

```bash
python main.py
```

The API will be available at `http://127.0.0.1:3001` and the interactive docs will be at `http://127.0.0.1:3001/`.

### Smoke check

```bash
curl http://127.0.0.1:3001/version
curl "http://127.0.0.1:3001/v2/health"
```

### Docker

```bash
docker compose up --build
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
- [slowapi](https://github.com/laurentS/slowapi)
- [uvicorn](https://www.uvicorn.org/)

## Contributing

Issues and pull requests are welcome.

Recommended workflow:

1. Branch from `master`.
2. Install dependencies and verify the app starts locally.
3. Run `python -m pytest tests/ -v`.
4. Open a pull request against `master`.

Open a [pull request](https://github.com/axsddlr/vlrggapi/pull/new/master) or file an [issue](https://github.com/axsddlr/vlrggapi/issues/new).

## License

The MIT License (MIT)
