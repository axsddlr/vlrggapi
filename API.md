# API Reference

Complete reference for every route: request parameters, response shapes and worked examples.
The [README](README.md) covers what this service is, how to run it, and the short version of the
recent additions.

**Contents**

- [V2 endpoints](#v2-endpoints) — every `/v2` route, including the path-based sub-resources
- [Original endpoints](#original-endpoints) — the unversioned routes, kept for backwards compatibility
- [Meta](#meta) — version metadata
- [Region codes](#region-codes) — the region taxonomy
- [Validation & Error Handling](#validation--error-handling) — validation rules and error shapes
- [Caching](#caching) — per-endpoint TTLs, `ETag` and `304 Not Modified`

Every example below is a real response, captured from the running service.

## V2 Endpoints

All examples are collapsed — click to expand.

| Path form | Query form |
|---|---|
| `/v2/player/{player_id}` | `/v2/player?id=...&q=profile` |
| `/v2/player/{player_id}/matches` | `/v2/player?id=...&q=matches` |
| `/v2/team/{team_id}` | `/v2/team?id=...&q=profile` |
| `/v2/team/{team_id}/matches` | `/v2/team?id=...&q=matches` |
| `/v2/team/{team_id}/transactions` | `/v2/team?id=...&q=transactions` |
| `/v2/team/{team_id}/stats` | `/v2/team?id=...&q=stats` |
| `/v2/team/{team_id}/roster` | `/v2/team?id=...&q=roster` |
| `/v2/team/{team_id}/schedule` | `/v2/team?id=...&q=schedule` |
| `/v2/match/{match_id}/details` | `/v2/match/details?match_id=...` |
| `/v2/match/{match_id}/logs` | `/v2/match/logs?match_id=...` |

The `q` parameter is deprecated on `/v2/player` and `/v2/team` only; `/v2/match` uses `q` as a collection filter.

### `GET /v2/news`
**Params:** none | **Cache:** 10 min

```
GET /v2/news
```

<details><summary>Response</summary>

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
</details>

### `GET /v2/match`
**Params:** `q` (required: upcoming/upcoming_extended/live_score/results), `num_pages`, `from_page`, `to_page`, `max_retries`, `request_delay`, `timeout`
**Cache:** 30s (live_score), 5min (upcoming, upcoming_extended), 60s (results)

The pagination params (`num_pages`, `from_page`, `to_page`) apply to `upcoming_extended` and `results` only. Passing any of them with `q=upcoming` or `q=live_score` returns HTTP 400, since those read a single fixed page. For the paginated queries the page window is capped at 20 pages, `max_retries` at 3, and `timeout` at 45 seconds.

```
GET /v2/match?q=upcoming
```

<details><summary>Response (upcoming)</summary>

```json
{
  "status": "success",
  "data": {
    "status": 200,
    "segments": [
      {
        "team1": "G2 Esports", "team2": "Leviatán",
        "flag1": "flag_us", "flag2": "flag_cl",
        "time_until_match": "51m from now",
        "match_series": "Regular Season: Week 3",
        "match_event": "Champions Tour 2024: Americas Stage 1",
        "unix_timestamp": "2024-04-24 21:00:00",
        "match_page": "https://www.vlr.gg/...",
        "match_id": "312784"
      }
    ]
  }
}
```
</details>

### `GET /v2/rankings`
**Params:** `region` (required — see [Region Codes](#region-codes)) | **Cache:** 1 hr

```
GET /v2/rankings?region=na
```

<details><summary>Response</summary>

```json
{
  "status": "success",
  "data": {
    "status": 200,
    "segments": [
      {
        "rank": "1", "team": "Sentinels", "country": "United States",
        "last_played": "22h ago", "record": "7-3", "earnings": "$295,500",
        "logo": "//owcdn.net/img/..."
      }
    ]
  }
}
```
</details>

### `GET /v2/stats`
**Params:** `region` (required), `timespan` (required: 30/60/90/all), `event_id` (optional — numeric event ID, filters the stats to a single event) | **Cache:** 30 min

**Regions** (the `/stats` page taxonomy, distinct from `/rankings`): `all`, `americas`, `emea`, `pacific`, `china`, `intl`. Deprecated aliases are still accepted and normalized: `na`/`br` → `americas`, `eu` → `emea`, `ap`/`kr`/`jp`/`oce` → `pacific`, `cn` → `china`.

```
GET /v2/stats?region=americas&timespan=30
```

<details><summary>Response</summary>

```json
{
  "status": "success",
  "data": {
    "status": 200,
    "segments": [
      {
        "player": "player_name", "org": "ORG",
        "rating": "1.18", "average_combat_score": "235.2",
        "kill_deaths": "1.19", "kill_assists_survived_traded": "72%",
        "average_damage_per_round": "158.4", "kills_per_round": "0.81",
        "assists_per_round": "0.29", "first_kills_per_round": "0.19",
        "first_deaths_per_round": "0.13", "headshot_percentage": "26%",
        "clutch_success_percentage": "28%", "clutch_attempts": "9/57"
      }
    ]
  }
}
```
</details>

### `GET /v2/events`
Browse events — use to discover event IDs for detail/matches lookups.
**Params:** `q` (optional: upcoming/completed/live), `page` | **Cache:** 30 min

```
GET /v2/events?q=upcoming
GET /v2/events?q=live
```

<details><summary>Response</summary>

```json
{
  "status": "success",
  "data": {
    "status": 200,
    "segments": [
      {
        "title": "VCT 2026: Pacific Stage 2", "event_id": "2776", "status": "completed",
        "prize": "$250,000", "dates": "Jul 15—Sep 6", "region": "kr",
        "thumb": "https://owcdn.net/img/...",
        "url_path": "https://www.vlr.gg/event/2776/vct-2026-pacific-stage-2"
      }
    ]
  }
}
```
</details>

### `GET /v2/match/details`
**Params:** `match_id` (required), `light` (optional — skip the per-game performance/economy tabs), `include` (optional — comma-separated top-level fields) | **Cache:** 5 min (30s for live)

`include` accepts `event`, `date`, `map_vetos`, `status`, `teams`, `streams`, `vods`, `maps`, `head_to_head`, `performance`, `economy`, and `economy_by_map`; `match_id` is always kept. Omit it to get the full payload. A fieldset naming none of `performance`, `economy`, or `economy_by_map` also skips those upstream tab fetches. See the path-form section below for a worked example.

```
GET /v2/match/details?match_id=595657
```

<details><summary>Response</summary>

```json
{
  "status": "success",
  "data": {
    "match_id": "595657",
    "event": { "name": "Champions Tour 2024: Americas Stage 1", "series": "Regular Season: Week 3" },
    "map_vetos": "SEN ban Breeze; C9 ban Lotus; SEN pick Ascent; C9 pick Bind; Haven remains",
    "date": "April 23, 2024", "status": "completed",
    "teams": [
      { "id": "2", "name": "Sentinels", "score": 2, "logo": "//owcdn.net/img/..." },
      { "id": "188", "name": "Cloud9", "score": 1, "logo": "//owcdn.net/img/..." }
    ],
    "maps": [{
      "map_name": "Ascent", "picked_by": "Sentinels", "duration": "28:41",
      "score": { "team1": { "total": 13, "ct": 8, "t": 5 }, "team2": { "total": 9, "ct": 4, "t": 5 } },
      "players": { "team1": [{ "name": "TenZ", "agent": "Jett", "rating": "1.32", "acs": "267", "kills": "24", "deaths": "15", "assists": "3", "kd_diff": "+9", "kast": "77%", "adr": "172.3", "hs_pct": "32%", "fk": "4", "fd": "2", "fk_diff": "+2" }], "team2": [] },
      "rounds": [{ "round_num": 1, "winner": "team1", "side": "t" }]
    }],
    "head_to_head": [{ "event": "VCT Americas", "date": "2024/03/15", "score": "2-1", "url": "https://www.vlr.gg/..." }],
    "performance": {
      "kill_matrix": [{ "player": "TenZ", "kills_vs": { "opponent1": "5" } }],
      "advanced_stats": [{ "player": "TenZ", "2K": "3", "3K": "1" }]
    },
    "economy": [{
      "Team": "Sentinels", "Pistol": "1/2", "Conv.": "1/1", "Bonus": "0/1",
      "On Eco <10k: vs. Full": "0/2", "On Half buy 10–18k: vs. Full": "0/3",
      "On Full buy 18k+: vs. Eco": "2/2", "On Full buy 18k+: vs. Half": "1/1", "On Full buy 18k+: vs. Full": "4/8"
    }]
  }
}
```
</details>

### `GET /v2/match/{match_id}/details`
Match detail from vlr.gg's `/match/<id>` page, plus its per-game performance and economy tabs.
**Params:** `match_id` (path, required), `light` (optional), `include` (optional) | **Cache:** 5 min (30s for live)

```
GET /v2/match/773435/details?include=maps,teams
```

Equivalent to `GET /v2/match/details?match_id=...`; the query form remains supported.

<details><summary>Response — trimmed to one map, one player per team, two rounds and one head-to-head row</summary>

```json
{
  "status": "success",
  "data": {
    "status": 200,
    "segments": [
      {
        "match_id": "773435",
        "teams": [
          {
            "id": "21093",
            "name": "Gentle Mates GC",
            "tag": "",
            "logo": "https://owcdn.net/img/6670153fa9120.png",
            "score": "2",
            "is_winner": true
          },
          {
            "id": "14278",
            "name": "Shopify Rebellion Gold",
            "tag": "",
            "logo": "https://owcdn.net/img/679314e3d25f4.png",
            "score": "1",
            "is_winner": false
          }
        ],
        "maps": [
          {
            "map_name": "Split",
            "picked_by": "Gentle Mates GC",
            "duration": "1:06:04",
            "score": {
              "team1": 11,
              "team2": 13
            },
            "score_ct": {
              "team1": "2",
              "team2": "3"
            },
            "score_t": {
              "team1": "9",
              "team2": "10"
            },
            "score_ot": {
              "team1": "",
              "team2": ""
            },
            "players": {
              "team1": [
                {
                  "name": "Marti",
                  "agent": "",
                  "rating": "1.09",
                  "acs": "229",
                  "kills": "20",
                  "deaths": "17",
                  "assists": "4",
                  "kd_diff": "+3",
                  "kast": "83%",
                  "adr": "143",
                  "hs_pct": "45%",
                  "fk": "2",
                  "fd": "3",
                  "fk_diff": "-1"
                }
              ],
              "team2": [
                {
                  "name": "Noia",
                  "agent": "",
                  "rating": "1.39",
                  "acs": "262",
                  "kills": "22",
                  "deaths": "12",
                  "assists": "3",
                  "kd_diff": "+10",
                  "kast": "88%",
                  "adr": "177",
                  "hs_pct": "44%",
                  "fk": "1",
                  "fd": "2",
                  "fk_diff": "-1"
                }
              ]
            },
            "rounds": [
              {
                "round_num": 1,
                "winner": "team2",
                "side": "t",
                "win_type": "elim"
              },
              {
                "round_num": 2,
                "winner": "team2",
                "side": "t",
                "win_type": "elim"
              }
            ],
            "performance": {
              "kill_matrix": [],
              "advanced_stats": []
            },
            "economy": []
          }
        ]
      }
    ]
  }
}
```
</details>

`include` is a comma-separated allowlist of top-level fields: `event`, `date`, `map_vetos`, `status`, `teams`, `streams`, `vods`, `maps`, `head_to_head`, `performance`, `economy`, `economy_by_map`; `match_id` is always kept. Omitting it returns everything. The request above names no `performance`, `economy` or `economy_by_map`, so those upstream tab fetches are skipped and the nested map fields come back empty. An unknown name returns 400:

```
GET /v2/match/773435/details?include=bogus
```

<details><summary>Response (400)</summary>

```json
{
  "detail": "Invalid include 'bogus'. Valid fields: date, economy, economy_by_map, event, head_to_head, map_vetos, maps, match_id, performance, status, streams, teams, vods"
}
```
</details>

### `GET /v2/match/logs`
**Params:** `match_id` (required), `game_id` (optional — defaults to the match's first played map), `include` (optional — `map`, `teams`, `rounds`) | **Cache:** 5 min

`include` is an allowlist; `match_id` and `game_id` are always kept, and omitting it returns the full payload.

Per-round 2D replay of one map, from the `logs` tab on vlr.gg. Each round carries its score, winner, attacking side and end reason, every player's buy, and one event per kill, spike plant and spike defuse — each with the acting player, damage source, spike site, and the positions and health of every player at that moment. Positions are per-event snapshots, not continuous frames.

```
GET /v2/match/logs?match_id=766311&game_id=285688
```

<details><summary>Response — real output for Abyss (22 rounds), trimmed to the first 2 rounds, 2 of 10 buy rows, 2 of 8 events and 3 positions per event</summary>

```json
{
  "status": "success",
  "data": {
    "match_id": "766311", "game_id": "285688", "map": "abyss",
    "teams": {
      "team1": { "name": "Akave Esports GC", "tag": "AKV.GC" },
      "team2": { "name": "MIBR GC", "tag": "MIBR.GC" }
    },
    "rounds": [
      {
        "round": 1, "score": { "team1": 1, "team2": 0 }, "winner": "team1",
        "attacking_side": "team1", "end_reason": "Elimination",
        "economy": [
          { "player": "WIRE", "team": 1, "agent": "yoru", "credits": 50, "spent": 750, "weapon": "Ghost", "armor": "none" },
          { "player": "Ivy", "team": 1, "agent": "sage", "credits": 100, "spent": 700, "weapon": "Classic", "armor": "none" }
        ],
        "events": [
          {
            "t": "0:07", "type": "kill", "player": "Tastyy", "team": 1, "victim": "bstrdd", "victim_team": 2,
            "pos": { "x": 562.3, "y": 584.8 }, "from": { "x": 530.7, "y": 707.5 },
            "positions": [
              { "player": "conir", "team": 2, "x": 967.4, "y": 418.8, "hp": 112 },
              { "player": "waved", "team": 2, "x": 464.8, "y": 528.5, "hp": 150 },
              { "player": "WIRE", "team": 1, "x": 180.8, "y": 642.2, "hp": 198 }
            ],
            "source": "Headhunter"
          },
          {
            "t": "0:17", "type": "kill", "player": "waved", "team": 2, "victim": "Tastyy", "victim_team": 1,
            "pos": { "x": 240.7, "y": 751.8 }, "from": { "x": 337.2, "y": 608.7 },
            "positions": [
              { "player": "conir", "team": 2, "x": 845.4, "y": 280.8, "hp": 81 },
              { "player": "waved", "team": 2, "x": 337.2, "y": 608.7, "hp": 124 },
              { "player": "WIRE", "team": 1, "x": 38, "y": 361.2, "hp": 8 }
            ],
            "source": "Ghost"
          }
        ]
      },
      {
        "round": 2, "score": { "team1": 2, "team2": 0 }, "winner": "team1",
        "attacking_side": "team1", "end_reason": "Elimination",
        "economy": [
          { "player": "WIRE", "team": 1, "agent": "yoru", "credits": 100, "spent": 3650, "weapon": "Bulldog", "armor": "heavy" },
          { "player": "Ivy", "team": 1, "agent": "sage", "credits": 1900, "spent": 1500, "weapon": "Sheriff", "armor": "heavy" }
        ],
        "events": [
          {
            "t": "0:19", "type": "kill", "player": "waved", "team": 2, "victim": "waved", "victim_team": 2,
            "pos": { "x": 1149.6, "y": 749.2 },
            "positions": [
              { "player": "conir", "team": 2, "x": 1105.6, "y": 659.7, "hp": 4 },
              { "player": "WIRE", "team": 1, "x": 161.7, "y": 582.9, "hp": 220 },
              { "player": "Tura", "team": 1, "x": 712.2, "y": 846, "hp": 300 }
            ],
            "source": "Fall"
          }
        ]
      }
    ]
  }
}
```
</details>

Reading the payload:

- `armor` is one of `none`, `light`, `heavy`, `regen`. `credits` is what the player had left after the buy, `spent` a positive amount.
- `source` is vlr.gg's own label for the damage source: usually a weapon, but ability kills appear by ability name (`Headhunter`) and environmental deaths as `Fall` or `Spike`.
- A death to the environment is reported as a kill where `player` equals `victim` and `source` is `Fall`/`Spike` — 11 of Abyss's 140 kills here. Do not treat `player == victim` as a parsing bug.
- `positions` holds every player still in play at that event, with their health. `pos` is where the event happened; `from` is the shooter's position (kills only).
- Coordinates are vlr.gg's per-map replay pixels, not normalised: Abyss runs to `x = 1157.5` on a nominally 1024-unit map, so scale from the observed range per map rather than assuming 0–1024.
- A map that was never played returns `rounds: []`. A 22-round response is roughly 128 KB, dominated by `positions`.

### `GET /v2/match/{match_id}/logs`
Per-round 2D replay from the `logs` tab of vlr.gg's `/match/<id>` page.
**Params:** `match_id` (path, required), `game_id` (optional — defaults to the first played map), `include` (optional — `map`, `teams`, `rounds`) | **Cache:** 5 min

```
GET /v2/match/773435/logs
```

Equivalent to `GET /v2/match/logs?match_id=...`; the query form remains supported.

<details><summary>Response — 24 rounds, trimmed to the first round, 2 of 10 buy rows, 1 event and 3 positions</summary>

```json
{
  "status": "success",
  "data": {
    "status": 200,
    "segments": [
      {
        "match_id": "773435",
        "game_id": "286485",
        "map": "split",
        "teams": {
          "team1": {
            "name": "Gentle Mates GC",
            "tag": "M8GC"
          },
          "team2": {
            "name": "Shopify Rebellion Gold",
            "tag": "SRG"
          }
        },
        "rounds": [
          {
            "round": 1,
            "score": {
              "team1": 0,
              "team2": 1
            },
            "winner": "team2",
            "attacking_side": "team2",
            "end_reason": "Elimination",
            "economy": [
              {
                "player": "Marti",
                "team": 1,
                "agent": "yoru",
                "credits": 0,
                "spent": 800,
                "weapon": "Bandit",
                "armor": "none"
              },
              {
                "player": "berryx",
                "team": 1,
                "agent": "neon",
                "credits": 100,
                "spent": 700,
                "weapon": "Ghost",
                "armor": "none"
              }
            ],
            "events": [
              {
                "t": "0:16",
                "type": "kill",
                "player": "vanitas",
                "team": 2,
                "victim": "safiaa",
                "victim_team": 1,
                "pos": {
                  "x": 240.9,
                  "y": 365.6
                },
                "from": {
                  "x": 157.4,
                  "y": 319.4
                },
                "positions": [
                  {
                    "player": "glowstick",
                    "team": 2,
                    "x": 106.6,
                    "y": 521.6,
                    "hp": 296
                  },
                  {
                    "player": "Noia",
                    "team": 2,
                    "x": 106.2,
                    "y": 478.8,
                    "hp": 270
                  },
                  {
                    "player": "berryx",
                    "team": 1,
                    "x": 698.3,
                    "y": 174.7,
                    "hp": 142
                  }
                ],
                "source": "Ghost"
              }
            ]
          }
        ]
      }
    ]
  }
}
```

</details>

### `GET /v2/event/{event_id}`
Event detail: stages, prizes, team rosters, and standings tables.
**Params:** `event_id` (path, required — from `/v2/events`), `stage` (optional — a slug from `stages`), `include` (optional — `event`, `stages`, `prizes`, `teams`, `standings`) | **Cache:** 30 min

A multi-stage event page on vlr.gg shows one stage at a time, and its prize rows and standings are that stage's (a group-stage view lists only the placements decided there). Without `stage` you get vlr.gg's default view, usually the current stage; `stages` lists every stage with its `slug`, and `stage=<slug>` returns that stage's view. An unknown slug returns 404. `include` narrows the `segments` object; omit it for the full payload.

```
GET /v2/event/2124
GET /v2/event/2124?stage=playoffs
```

<details><summary>Response</summary>

```json
{
  "status": "success",
  "data": {
    "segments": {
      "event": {
        "name": "VCT 2026: Americas Stage 1", "series": "Valorant Champions Tour 2026",
        "dates": "Apr 15 - May 10, 2026", "prize": "$250,000 USD",
        "location": "Los Angeles, USA", "logo": "https://owcdn.net/img/..."
      },
      "stages": [
        { "name": "Playoffs", "slug": "playoffs", "dates": "May 2–10", "active": false },
        { "name": "Group Stage", "slug": "group-stage", "dates": "Apr 15–27", "active": true }
      ],
      "prizes": [
        { "placement": "1st", "amount": "$100,000", "team": { "id": "120", "name": "100 Thieves", "logo": "...", "region": "United States" } },
        { "placement": "2nd", "amount": "$60,000", "team": { "id": "2355", "name": "KRÜ Esports", "logo": "...", "region": "Chile" } }
      ],
      "teams": [{
        "id": "120", "name": "100 Thieves",
        "players": [{ "id": "9", "name": "Asuna", "flag": "mod-us" }],
        "qualification": "NA Circuit Points"
      }],
      "standings": [{
        "stage": "Group Stage", "group": "Group A", "columns": ["Team", "W", "L", "T", "MAP", "RND", "Δ"],
        "rows": [{ "Team": "100 Thieves", "W": "4", "L": "1", "T": "0", "MAP": "8/3", "RND": "135/102", "Δ": "+33" }]
      }]
    }
  }
}
```
</details>

### `GET /v2/search`
Cross-entity search for players, teams, and events.
**Params:** `q` (required) | **Cache:** 5 min

```
GET /v2/search?q=tenz
```

<details><summary>Response</summary>

```json
{
  "status": "success",
  "data": {
    "segments": {
      "query": "tenz",
      "results": {
        "players": [{ "id": "9", "name": "TenZ", "img": "https://owcdn.net/img/...", "description": "", "tag": "" }],
        "teams": [{ "id": "16647", "name": "TenZ and Friends", "img": "https://...", "description": "", "tag": "(inactive)" }],
        "events": []
      }
    }
  }
}
```
</details>

### `GET /v2/player`
**Params:** `id` (required), `q` (profile/matches, default: profile; deprecated — use the path forms below), `timespan` (30d/60d/90d/all, default: 90d), `page` (1-based, default: 1) | **Cache:** varies

```
GET /v2/player?id=9&q=profile&timespan=all
GET /v2/player?id=9&q=matches&page=1
```

<details><summary>Profile response</summary>

```json
{
  "status": "success",
  "data": {
    "info": { "name": "TenZ", "real_name": "Tyson Ngo", "avatar": "https://owcdn.net/img/...", "country": "Canada", "socials": [{ "platform": "twitter", "url": "..." }] },
    "current_teams": [{ "name": "Sentinels", "tag": "SEN", "status": "Active" }],
    "past_teams": [{ "name": "Cloud9", "tag": "C9", "dates": "2020–2021" }],
    "agent_stats": [{ "agent": "Jett", "use_count": 150, "use_pct": "42%", "rounds": 3200, "rating": "1.15", "acs": "245.3", "kd": "1.18", "adr": "162.1", "kast": "71%", "kpr": "0.82", "apr": "0.28", "fkpr": "0.20", "fdpr": "0.14", "kills": 2624, "deaths": 2224, "assists": 896, "fk": 640, "fd": 448 }],
    "event_placements": [{ "event": "Champions 2024", "placement": "1st", "prize": "$100,000", "team": "Sentinels" }],
    "total_winnings": "$177,650"
  }
}
```
</details>

<details><summary>Matches response</summary>

```json
{
  "status": "success",
  "data": {
    "status": 200,
    "segments": [{
      "match_id": "719455",
      "url": "https://www.vlr.gg/719455/...",
      "event": "Twitch Rivals 2026",
      "date": "2026/07/24 8:50 pm",
      "team1": { "name": "Team TenZ", "tag": "Team TenZ", "logo": "" },
      "team2": { "name": "Team s0m", "tag": "Team s0m", "logo": "" },
      "score": "2:0",
      "result": "win"
    }],
    "meta": { "page": 1 }
  }
}
```
</details>

### `GET /v2/player/{player_id}`
Player profile from vlr.gg's `/player/<id>` page.
**Params:** `player_id` (path, required), `timespan` (30d/60d/90d/all, default: 90d) | **Cache:** 30 min

```
GET /v2/player/30186?timespan=all
```

Equivalent to `GET /v2/player?id=...&q=profile`; the query form is deprecated.

<details><summary>Response — trimmed to one social link, one past team, one agent and one placement</summary>

```json
{
  "status": "success",
  "data": {
    "status": 200,
    "segments": [
      {
        "id": "30186",
        "name": "Nami",
        "real_name": "Iman Nagaaoui",
        "avatar": "https://owcdn.net/img/69794cf31dc03.png",
        "country": "fr",
        "social_links": [
          {
            "platform": "twitter",
            "url": "https://twitter.com/vlrdotgg"
          }
        ],
        "current_team": {
          "name": "Gentle Mates GC",
          "tag": "",
          "logo": "https://owcdn.net/img/6670153fa9120.png",
          "joined": "joined in January 2026"
        },
        "past_teams": [
          {
            "name": "GIANTX GC",
            "tag": "",
            "dates": "January 2025 – August 2025",
            "logo": "https://owcdn.net/img/657b2f3fcd199.png"
          }
        ],
        "agent_stats": [
          {
            "agent": "omen",
            "usage_count": "237",
            "usage_pct": "60%",
            "rounds": "4940",
            "rating": "1.03",
            "acs": "202.3",
            "kd": "1.05",
            "kast": "74%",
            "adr": "129.3",
            "kpr": "0.73",
            "apr": "0.39",
            "fk_fd": "0.99",
            "kills": "3583",
            "deaths": "3414",
            "assists": "1907",
            "fk": "412",
            "fd": "417"
          }
        ],
        "event_placements": [
          {
            "event": "Game Changers 2026: EMEA Stage 3",
            "series": "Playoffs",
            "placement": "2nd",
            "prize": "$1,760",
            "team": "Gentle Mates GC",
            "date": "2026",
            "url": "https://www.vlr.gg/event/3028/game-changers-2026-emea-stage-3"
          }
        ],
        "total_winnings": "$15,077"
      }
    ]
  }
}
```
</details>

### `GET /v2/player/{player_id}/matches`
Completed match history from the match-history tab of vlr.gg's `/player/<id>` page.
**Params:** `player_id` (path, required), `page` (1-based, default: 1) | **Cache:** 10 min

```
GET /v2/player/30186/matches
```

Equivalent to `GET /v2/player?id=...&q=matches`; the query form is deprecated.

<details><summary>Response — first match only</summary>

```json
{
  "status": "success",
  "data": {
    "status": 200,
    "segments": [
      {
        "match_id": "773435",
        "url": "https://www.vlr.gg/773435/gentle-mates-gc-vs-shopify-rebellion-gold-game-changers-2026-championship-s-o-paulo-ubf",
        "event": "GC 26: ChampionshipUBF",
        "date": "2026/10/302:00 pm",
        "team1": {
          "name": "Gentle Mates GC",
          "tag": "M8GC",
          "logo": ""
        },
        "team2": {
          "name": "Shopify Rebellion Gold",
          "tag": "SRG",
          "logo": ""
        },
        "score": "2:1",
        "result": "win"
      }
    ],
    "meta": {
      "page": 1
    }
  }
}
```
</details>

### `GET /v2/team`
**Params:** `id` (required), `q` (profile/matches/transactions/stats/roster/schedule, default: profile; deprecated — use the path forms below), `page` (1-based, default: 1) | **Cache:** 30 min (profile, roster), 10 min (matches, stats), 1 hr (transactions), 5 min (schedule)

```
GET /v2/team?id=2&q=profile
GET /v2/team?id=2&q=matches&page=1
GET /v2/team?id=2&q=transactions
GET /v2/team?id=2&q=stats
GET /v2/team?id=2&q=roster
GET /v2/team?id=2&q=schedule
```

<details><summary>Profile response</summary>

```json
{
  "status": "success",
  "data": {
    "info": { "name": "Sentinels", "tag": "SEN", "logo": "https://owcdn.net/img/...", "country": "United States", "socials": [{ "platform": "twitter", "url": "..." }] },
    "rating": { "vlr_rating": "1850", "rank": "1", "region": "na" },
    "roster": [{ "alias": "TenZ", "real_name": "Tyson Ngo", "role": "Duelist", "is_captain": false, "avatar": "..." }],
    "event_placements": [{ "event": "Champions 2024", "placement": "1st", "prize": "$100,000" }],
    "total_winnings": "$1,194,000"
  }
}
```
</details>

<details><summary>Matches response</summary>

```json
{
  "status": "success",
  "data": {
    "status": 200,
    "segments": [{
      "match_id": "729757",
      "url": "https://www.vlr.gg/729757/sentinels-vs-kr-esports-...",
      "event": "LR2",
      "date": "2026/08/22",
      "time": "7:10 pm",
      "team1": { "name": "Sentinels", "tag": "SEN", "logo": "https://owcdn.net/img/..." },
      "team2": { "name": "KRÜ Esports", "tag": "KRÜ", "logo": "https://owcdn.net/img/..." },
      "score": "0:2",
      "result": "loss"
    }],
    "meta": { "page": 1 }
  }
}
```

Unlike the player equivalent, each segment also carries a separate `time` field; the player `date` folds both together.
</details>

<details><summary>Transactions response</summary>

```json
{
  "status": "success",
  "data": {
    "status": 200,
    "segments": [{
      "date": "Gurjiwan Gill",
      "action": "inactive",
      "player": { "name": "Jerrwin", "id": "34057", "url": "https://www.vlr.gg/player/34057/gurjiwan-gill", "avatar": "", "country": "in" },
      "role": ""
    }]
  }
}
```

As with the roster's `transactions` list, `player` is a nested object and `date` carries a person's full name rather than a date — see the roster note above.
</details>

<details><summary>Stats response</summary>

```json
{
  "status": "success",
  "data": {
    "segments": [
      {
        "map": "Bind",
        "games": 86,
        "win_pct": "71%",
        "wins": 61,
        "losses": 25,
        "atk_first": 54,
        "def_first": 32,
        "atk_rwin_pct": "60%",
        "atk_rw": 575,
        "atk_rl": 383,
        "def_rwin_pct": "53%",
        "def_rw": 458,
        "def_rl": 408
      }
    ]
  }
}
```
</details>

<details><summary>Roster response</summary>

```json
{
  "status": "success",
  "data": {
    "status": 200,
    "segments": [{
      "active": [{
        "id": "1265", "url": "https://www.vlr.gg/player/1265/johnqt",
        "alias": "johnqt", "real_name": "Mohamed Amine Ouarid",
        "avatar": "https://owcdn.net/img/...", "country": "ma",
        "is_captain": true, "role": "", "is_staff": false
      }],
      "staff": [],
      "former": [],
      "benched": [],
      "transactions": [{
        "date": "Gurjiwan Gill", "action": "inactive",
        "player": { "name": "Jerrwin", "id": "34057", "url": "https://www.vlr.gg/player/34057/gurjiwan-gill", "avatar": "", "country": "in" },
        "role": ""
      }]
    }]
  }
}
```

`segments` holds a single object with the roster split into `active`, `staff`, `former`, and `benched`. `transactions` mirrors `q=transactions`, but note vlr.gg renders that table's columns as name and source link rather than a date, so `date` carries a person's full name and `role` carries a URL on `join`/`leave` entries.
</details>

<details><summary>Schedule response</summary>

```json
{
  "status": "success",
  "data": {
    "status": 200,
    "segments": [{
      "match_id": "729757",
      "url": "https://www.vlr.gg/729757/sentinels-vs-kr-esports-...",
      "event": "LR2",
      "date": "2026/08/22",
      "time": "7:10 pm",
      "eta": "",
      "team1": { "name": "Sentinels", "tag": "SEN", "logo": "https://owcdn.net/img/..." },
      "team2": { "name": "KRÜ Esports", "tag": "KRÜ", "logo": "https://owcdn.net/img/..." }
    }]
  }
}
```

`segments` is a flat list of upcoming matches. `eta` is a countdown string when vlr.gg renders one and `""` otherwise.
</details>

### `GET /v2/team/{team_id}`
Team profile from vlr.gg's `/team/<id>` page.
**Params:** `team_id` (path, required) | **Cache:** 30 min

```
GET /v2/team/14278
```

Equivalent to `GET /v2/team?id=...&q=profile`; the query form is deprecated.

<details><summary>Response — trimmed to one social link, one roster member and one event placement</summary>

```json
{
  "status": "success",
  "data": {
    "status": 200,
    "segments": [
      {
        "id": "14278",
        "name": "Shopify Rebellion Gold",
        "tag": "SRG",
        "successor": "",
        "logo": "https://owcdn.net/img/679314e3d25f4.png",
        "country": "ca",
        "country_name": "Canada",
        "description": "Shopify Rebellion GoldSRGshopifyrebellion.gg@SRVALCanada",
        "social_links": [
          {
            "platform": "other",
            "url": "https://shopifyrebellion.gg/"
          }
        ],
        "rating": {
          "rank": "172",
          "rating": "1446",
          "peak_rating": "",
          "streak": "81W60L"
        },
        "roster": [
          {
            "id": "9185",
            "url": "https://www.vlr.gg/player/9185/dodonut",
            "alias": "dodonut",
            "real_name": "Karnthida Chaisrakeo",
            "avatar": "https://owcdn.net/img/688da704e1eec.png",
            "country": "th",
            "is_captain": false,
            "role": "",
            "is_staff": false
          }
        ],
        "event_placements": [
          {
            "event": "FunhaverGG: Back to Basics 2.0 #1",
            "series": "Playoffs – 17th–32nd",
            "placement": "17th",
            "prize": "",
            "date": "2026",
            "url": "https://www.vlr.gg/event/3087/funhavergg-back-to-basics-2-0-1"
          }
        ],
        "total_winnings": "$608,997"
      }
    ]
  }
}
```
</details>

### `GET /v2/team/{team_id}/matches`
Completed match history from vlr.gg's `/team/matches/<id>` page.
**Params:** `team_id` (path, required), `page` (1-based, default: 1) | **Cache:** 10 min

```
GET /v2/team/14278/matches
```

Equivalent to `GET /v2/team?id=...&q=matches`; the query form is deprecated.

<details><summary>Response — first match only</summary>

```json
{
  "status": "success",
  "data": {
    "status": 200,
    "segments": [
      {
        "match_id": "773435",
        "url": "https://www.vlr.gg/773435/gentle-mates-gc-vs-shopify-rebellion-gold-game-changers-2026-championship-s-o-paulo-ubf",
        "event": "GC 26: ChampionshipUBF",
        "date": "2026/10/30",
        "time": "2:00 pm",
        "team1": {
          "name": "Shopify Rebellion Gold",
          "tag": "SRG",
          "logo": "https://owcdn.net/img/679314e3d25f4.png"
        },
        "team2": {
          "name": "Gentle Mates GC",
          "tag": "M8GC",
          "logo": "https://owcdn.net/img/6670153fa9120.png"
        },
        "score": "1:2",
        "result": "loss"
      }
    ],
    "meta": {
      "page": 1
    }
  }
}
```
</details>

### `GET /v2/team/{team_id}/transactions`
Roster transaction history from vlr.gg's `/team/transactions/<id>` page.
**Params:** `team_id` (path, required) | **Cache:** 1 hr

```
GET /v2/team/14278/transactions
```

Equivalent to `GET /v2/team?id=...&q=transactions`; the query form is deprecated.

<details><summary>Response — first transaction only</summary>

```json
{
  "status": "success",
  "data": {
    "status": 200,
    "segments": [
      {
        "date": "Ludovic Lefebvre",
        "action": "join",
        "player": {
          "name": "monSi",
          "id": "4385",
          "url": "https://www.vlr.gg/player/4385/ludovic-lefebvre",
          "avatar": "",
          "country": "ca"
        },
        "role": "https://x.com/SRVAL/status/2090484393194242277"
      }
    ]
  }
}
```
</details>

### `GET /v2/team/{team_id}/stats`
Per-map win/loss and round stats from vlr.gg's `/team/stats/<id>` page.
**Params:** `team_id` (path, required), `date_start` (optional — `YYYY-MM-DD`) | **Cache:** 10 min

```
GET /v2/team/14278/stats
```

Equivalent to `GET /v2/team?id=...&q=stats`; the query form is deprecated.

<details><summary>Response — first map only</summary>

```json
{
  "status": "success",
  "data": {
    "status": 200,
    "segments": [
      {
        "map": "Bind",
        "games": 22,
        "win_pct": "55%",
        "wins": 12,
        "losses": 10,
        "atk_first": 11,
        "def_first": 11,
        "atk_rwin_pct": "44%",
        "atk_rw": 102,
        "atk_rl": 131,
        "def_rwin_pct": "60%",
        "def_rw": 142,
        "def_rl": 93
      }
    ]
  }
}
```
</details>

### `GET /v2/team/{team_id}/roster`
Grouped roster from vlr.gg's `/team/roster/<id>` page.
**Params:** `team_id` (path, required) | **Cache:** 30 min

```
GET /v2/team/14278/roster
```

Equivalent to `GET /v2/team?id=...&q=roster`; the query form is deprecated.

<details><summary>Response — one active member and one transaction</summary>

```json
{
  "status": "success",
  "data": {
    "status": 200,
    "segments": [
      {
        "active": [
          {
            "id": "9185",
            "url": "https://www.vlr.gg/player/9185/dodonut",
            "alias": "dodonut",
            "real_name": "Karnthida Chaisrakeo",
            "avatar": "https://owcdn.net/img/688da704e1eec.png",
            "country": "th",
            "is_captain": false,
            "role": "",
            "is_staff": false
          }
        ],
        "staff": [],
        "former": [],
        "benched": [],
        "transactions": [
          {
            "date": "Ludovic Lefebvre",
            "action": "join",
            "player": {
              "name": "monSi",
              "id": "4385",
              "url": "https://www.vlr.gg/player/4385/ludovic-lefebvre",
              "avatar": "",
              "country": "ca"
            },
            "role": "https://x.com/SRVAL/status/2090484393194242277"
          }
        ]
      }
    ]
  }
}
```
</details>

### `GET /v2/team/{team_id}/schedule`
Upcoming schedule from the upcoming section of vlr.gg's `/team/matches/<id>` page.
**Params:** `team_id` (path, required) | **Cache:** 5 min

```
GET /v2/team/14278/schedule
```

Equivalent to `GET /v2/team?id=...&q=schedule`; the query form is deprecated.

<details><summary>Response — first match only</summary>

```json
{
  "status": "success",
  "data": {
    "status": 200,
    "segments": [
      {
        "match_id": "773444",
        "url": "https://www.vlr.gg/773444/shopify-rebellion-gold-vs-kr-blaze-game-changers-2026-championship-s-o-paulo-lbf",
        "event": "GC 26: ChampionshipLBF",
        "date": "2026/10/31",
        "time": "2:00 pm",
        "eta": "",
        "team1": {
          "name": "Shopify Rebellion Gold",
          "tag": "SRG",
          "logo": "https://owcdn.net/img/679314e3d25f4.png"
        },
        "team2": {
          "name": "KRÜ BLAZE",
          "tag": "KRUB",
          "logo": "https://owcdn.net/img/6704ad6a515a1.png"
        }
      }
    ]
  }
}
```
</details>

### `GET /v2/events/matches`
**Params:** `event_id` (required) | **Cache:** 10 min

```
GET /v2/events/matches?event_id=2095
```

<details><summary>Response</summary>

```json
{
  "status": "success",
  "data": {
    "status": 200,
    "segments": [{
      "match_id": "595657",
      "url": "https://www.vlr.gg/595657/...",
      "date": "Sun, April 24, 2024",
      "time": "3:00 PM",
      "unix_timestamp": "2024-04-24 19:00:00",
      "status": "Completed",
      "note": "",
      "stage": "Playoffs",
      "event_series": "Grand Final",
      "team1": { "name": "Sentinels", "score": "2", "is_winner": true },
      "team2": { "name": "Cloud9", "score": "1", "is_winner": false }
    }]
  }
}
```

`date` and `time` are as vlr.gg rendered them, in the timezone vlr.gg picked for the requesting server. `unix_timestamp` is UTC, derived from a minute-precision countdown on the same page; it is `""` when the page has none (e.g. an event whose every match is more than a day away or a day old).
</details>

### `GET /v2/health`
**Params:** none | **Cache:** none

Reports local service readiness — the app itself and its shared HTTP client. It does **not** call vlr.gg, so it is safe to use as a container liveness probe.

```
GET /v2/health
```

<details><summary>Response</summary>

```json
{
  "status": "success",
  "data": {
    "service": { "status": "Healthy" },
    "http_client": { "status": "Healthy", "status_code": null }
  },
  "meta": null,
  "message": null
}
```
</details>

## Original Endpoints

Preserved for backwards compatibility. Most return `{"data": {"status": int, "segments": [...]}}`, mirroring their V2 counterparts — see [V2 Endpoints](#v2-endpoints) for examples. Three differ:

- `/rankings` returns `{"status": int, "data": [...]}` — the segment list is unwrapped.
- `/health` returns the bare `{"service": {...}, "http_client": {...}}` object with no envelope.
- `/match/details` omits the `id` field from every entry in `teams`.

| Route | Query Params |
|---|---|
| `GET /news` | — |
| `GET /match` | `q` (upcoming/upcoming_extended/live_score/results); pagination params for `upcoming_extended`/`results` only |
| `GET /match/details` | `match_id` |
| `GET /match/logs` | `match_id`, `game_id` (optional) |
| `GET /stats` | `region`, `timespan`, `event_id` |
| `GET /rankings` | `region` |
| `GET /events` | `q` (upcoming/completed/live), `page` |
| `GET /events/matches` | `event_id` |
| `GET /player` | `id`, `timespan` |
| `GET /player/matches` | `id`, `page` |
| `GET /team` | `id` |
| `GET /team/matches` | `id`, `page` |
| `GET /team/transactions` | `id` |
| `GET /team/roster` | `id` |
| `GET /team/schedule` | `id` |
| `GET /health` | — |

### `GET /news`
Legacy equivalent of `/v2/news`; returns the unversioned envelope.

### `GET /match`
Legacy match list; `q` selects upcoming, upcoming_extended, live_score or results.

### `GET /match/details`
Legacy match detail; `teams` entries omit `id` as noted above.

### `GET /match/logs`
Legacy 2D replay; same shape as `/v2/match/logs`.

### `GET /stats`
Legacy player stats; same validators as `/v2/stats`.

### `GET /rankings`
Legacy rankings; returns `{"status": int, "data": [...]}`.

### `GET /events`
Legacy event list; an unknown `q` is ignored.

### `GET /events/matches`
Legacy event match list; same shape as `/v2/events/matches`.

### `GET /player`
Legacy player profile; `q=matches` switches to match history.

### `GET /player/matches`
Legacy player match history; same shape as `/v2/player/{player_id}/matches`.

### `GET /team`
Legacy team data; `q` selects profile, matches, transactions, stats, roster or schedule.

### `GET /team/matches`
Legacy team match history; same shape as `/v2/team/{team_id}/matches`.

### `GET /team/transactions`
Legacy roster transactions; same shape as `/v2/team/{team_id}/transactions`.

### `GET /team/roster`
Legacy grouped roster; same shape as `/v2/team/{team_id}/roster`.

### `GET /team/schedule`
Legacy upcoming schedule; same shape as `/v2/team/{team_id}/schedule`.

### `GET /health`
Bare health object without an envelope.

`/search` and `/event/{id}` exist only under `/v2` — there is no unversioned equivalent.

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
<summary><code>GET /stats?region=americas&timespan=30</code> — response example</summary>

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
        "clutch_success_percentage": "28%",
        "clutch_attempts": "9/57"
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
  "service": {
    "status": "Healthy"
  },
  "http_client": {
    "status": "Healthy",
    "status_code": null
  }
}
```

</details>

## Meta

### `GET /version`
Current API version and default API version.
**Params:** none | **Cache:** none

```
GET /version
```

<details><summary>Response</summary>

```json
{
  "version": "2.0.0",
  "default_api": "v2"
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

V2 endpoints validate input and return HTTP 400 with a `detail` message:

- **Invalid region** — `/rankings` accepts the 14 codes listed above. `/stats` uses its own taxonomy (`all`, `americas`, `emea`, `pacific`, `china`, `intl`) and normalizes the deprecated aliases instead of rejecting them
- **Invalid timespan** — must be `30`, `60`, `90`, or `all`
- **Invalid player timespan** — must be `30d`, `60d`, `90d`, or `all`
- **Invalid match query** — must be `upcoming`, `upcoming_extended`, `live_score`, or `results`
- **Invalid event query** — must be `upcoming`, `completed`, or `live`
- **Invalid player query** — must be `profile` or `matches`
- **Invalid team query** — must be `profile`, `matches`, `transactions`, `stats`, `roster`, or `schedule`
- **Invalid stage** — must be a vlr.gg slug such as `group-stage` (lowercase letters, digits, and hyphens)
- **Invalid ID** — `match_id`, `event_id`, player `id`, and team `id` must be numeric
- **Unsupported pagination** — `num_pages`, `from_page`, and `to_page` are rejected for `q=upcoming` and `q=live_score`
- **Excessive workload** — for the paginated match queries the page window is capped at 20 pages, `max_retries` at 3, and `timeout` at 45 seconds

```json
{
  "detail": "Invalid region 'xyz'. Valid regions: ap, br, cn, col, eu, gc, jp, kr, la, la-n, la-s, mn, na, oce"
}
```

`/stats` reports its own vocabulary in the same shape:

```json
{
  "detail": "Invalid region 'xyz'. Valid regions: all, americas, china, emea, intl, pacific"
}
```

The unversioned endpoints are not uniformly unvalidated — most (`/rankings`, `/stats`, `/player`, `/player/matches`, `/team`, `/team/matches`, `/team/transactions`, `/team/roster`, `/team/schedule`, `/match/details`, `/events/matches`) reuse these same validators and return the same HTTP 400. Two are deliberately looser for backwards compatibility: `/match` answers an unknown `q` with HTTP 200 and `{"error": "Invalid query parameter"}`, and `/events` ignores an unknown `q` and returns the unfiltered event list.

## Caching

V2 endpoints use an in-memory TTL cache to reduce load on vlr.gg. Cache durations per endpoint:

| Data | TTL |
|---|---|---|
| Live scores | 30 seconds |
| Match detail (live) | 30 seconds |
| Results | 60 seconds |
| Upcoming matches | 5 minutes |
| Match detail | 5 minutes |
| Search | 5 minutes |
| Team schedule | 5 minutes |
| News | 10 minutes |
| Player matches | 10 minutes |
| Team matches | 10 minutes |
| Team stats | 10 minutes |
| Event matches | 10 minutes |
| Stats | 30 minutes |
| Events | 30 minutes |
| Event detail | 30 minutes |
| Player profile | 30 minutes |
| Team profile | 30 minutes |
| Team roster | 30 minutes |
| Rankings | 1 hour |
| Team transactions | 1 hour |

Original endpoints share the same in-memory TTL cache as their V2 counterparts, so the same scrape is never repeated across the two versions. `/health` is the exception: it is never cached, since it only reports in-process state.

### Conditional requests

`/rankings`, `/stats` and the `/team` endpoints sit behind long TTLs and change slowly, so their successful JSON responses carry a strong `ETag` — the SHA-256 of the exact response body. Send that tag back in `If-None-Match` to skip the body. This pair was captured against a local instance:

```
GET /v2/rankings?region=na HTTP/1.1

HTTP/1.1 200 OK
Content-Type: application/json
Content-Length: 58744
ETag: "c47e01e3fd911b030c65cc60acaa3e3d7a2e2a6960bb72715265bf79575b86a4"
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 59
Vary: Origin
```

The 58,744-byte JSON body is omitted. Reusing the tag returns no body at all:

```
GET /v2/rankings?region=na HTTP/1.1
If-None-Match: "c47e01e3fd911b030c65cc60acaa3e3d7a2e2a6960bb72715265bf79575b86a4"

HTTP/1.1 304 Not Modified
ETag: "c47e01e3fd911b030c65cc60acaa3e3d7a2e2a6960bb72715265bf79575b86a4"
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 58
Vary: Origin
```

Weak (`W/"…"`) client tags, comma-separated lists and `*` are all accepted; a malformed tag is ignored rather than rejected. The check runs inside the rate limiter, so a `304` still consumes rate-limit budget and still carries `X-RateLimit-*` — revalidation is cheaper on the wire, not free. No `Cache-Control` header is added, so storing and revalidating is opt-in per client. Only these three endpoints participate; `/news`, `/events` and the rest are unaffected.
