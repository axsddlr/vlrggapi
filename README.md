# vlrggapi

## Important Notice

> **`https://vlrggapi.vercel.app/` is currently down because it exceeded free-tier limits.**
> Please self-host the API for now, or wait while I look into another solution.

An Unofficial REST API for [vlr.gg](https://www.vlr.gg/), a site for Valorant Esports match and news coverage.

Built by [Andre Saddler](https://github.com/axsddlr/)

## Support

If this API helps your projects, you can support ongoing maintenance and development on Ko-fi.

<a href='https://ko-fi.com/J3J1IR40C' target='_blank'><img height='36' style='border:0px;height:36px;' src='https://storage.ko-fi.com/cdn/kofi6.png?v=6' border='0' alt='Buy Me a Coffee at ko-fi.com' /></a>

## Quick Start

- **Public base URL:** `https://vlrggapi.vercel.app` — currently down, see the notice above
- **Local base URL:** `http://127.0.0.1:3001` (see [Installation](#installation))
- **Interactive docs:** `/`
- **Version info:** `/version`

```bash
curl "http://127.0.0.1:3001/v2/news"
curl "http://127.0.0.1:3001/v2/match?q=live_score"
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

- **Match details** — per-map player stats (K/D/A, ACS, rating), round-by-round data, kill matrix, economy breakdown, head-to-head history, map veto data
- **Player profiles** — agent stats (17 metrics), current/past teams, event placements, total winnings, match history
- **Team profiles** — roster with roles/captain status, VLR rating/rank, event placements, total winnings, match history, roster transactions
- **Event matches** — full match list for any event with scores and VOD links
- **Event detail** — event info with prize pool breakdown, participating team rosters, and group/stage standings tables
- **Search** — cross-entity search for teams, players, and events by name or keyword

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
| Input validation | HTTP 400 on most routes (`/match` and `/events` are looser) | HTTP 400 on invalid params |
| Caching | Shared in-memory TTL cache | Per-endpoint TTL cache |

Interactive Swagger docs are available at `/`.

## Operational Notes

- **Recommended base path** - use `/v2` for new integrations
- **Current version endpoint** - `GET /version` returns the current API version and default API
- **Rate limit** - tiered sliding-window limits, applied per client IP. `200/min` (`/health`, `/version`), `60/min` (`/news`, `/events`, `/event/{id}`, `/events/matches`, `/rankings`, `/search`, and `/match` with `q=upcoming` or `q=live_score`), `20/min` (`/match/details`, `/match/logs`, `/stats`, `/player`, `/team`, and `/match` with `q=results` or `q=upcoming_extended`). The `/v2` prefix shares each tier with its unversioned route. Exceeding a tier returns HTTP 429 with `Retry-After`, `X-RateLimit-Limit`, and `X-RateLimit-Remaining` headers. Limits are per worker process, so a multi-worker deployment enforces them independently in each worker.
- **Error handling** - V2 returns HTTP 400 for invalid input and propagates upstream failures with HTTP error codes
- **Deployment targets** - Vercel for the hosted API, Docker for containerized self-hosting

## V2 Endpoint Overview

| Route | Query Params | Cache |
|---|---|---|
| `GET /v2/news` | — | 10 min |
| `GET /v2/match` | `q` (upcoming/upcoming_extended/live_score/results); pagination params `num_pages`, `from_page`, `to_page` apply to `upcoming_extended`/`results` only; also `max_retries`, `request_delay`, `timeout` | 30s–5 min |
| `GET /v2/match/details` | `match_id` | 5 min |
| `GET /v2/match/{match_id}/details` | `light` | 5 min |
| `GET /v2/match/logs` | `match_id`, `game_id` (optional, defaults to the first played map) | 5 min |
| `GET /v2/match/{match_id}/logs` | `game_id` (optional, defaults to the first played map) | 5 min |
| `GET /v2/rankings` | `region` | 1 hr |
| `GET /v2/stats` | `region`, `timespan`, `event_id` | 30 min |
| `GET /v2/events` | `q` (upcoming/completed/live), `page` | 30 min |
| `GET /v2/event/{id}` | `event_id` (path), `stage` | 30 min |
| `GET /v2/events/matches` | `event_id` | 10 min |
| `GET /v2/search` | `q` | 5 min |
| `GET /v2/player` | `id`, `q` (profile/matches, deprecated), `timespan`, `page` | 30 min / 10 min |
| `GET /v2/player/{player_id}` | `timespan` | 30 min |
| `GET /v2/player/{player_id}/matches` | `page` | 10 min |
| `GET /v2/team` | `id`, `q` (profile/matches/transactions/stats/roster/schedule, deprecated), `page`, `date_start` | 30 min / 10 min / 1 hr / 10 min / 30 min / 5 min |
| `GET /v2/team/{team_id}` | — | 30 min |
| `GET /v2/team/{team_id}/matches` | `page` | 10 min |
| `GET /v2/team/{team_id}/transactions` | — | 1 hr |
| `GET /v2/team/{team_id}/stats` | `date_start` | 10 min |
| `GET /v2/team/{team_id}/roster` | — | 30 min |
| `GET /v2/team/{team_id}/schedule` | — | 5 min |
| `GET /v2/health` | — | none |

Every entity — a player, a team, a match's detail or replay — is addressable as its own path as well as through the older `q` parameter. Prefer the path forms: an unknown sub-resource is a `404` on a real route instead of a `400` from a query-string enum, and each one appears in the generated OpenAPI docs. `q` stays supported on `/v2/player` and `/v2/team` for existing clients and is marked deprecated; `/match`'s `q` is a collection filter (upcoming/live/results), not an entity selector, and is not deprecated.

Rate-limit tiers are assigned by path, so a sub-resource inherits its parent's tier — `/v2/team/{team_id}/roster` counts as expensive, exactly like `/v2/team`. The same rule is why there is no plural `/v2/matches` collection route: match lists stay on `/v2/match?q=...`, where the tier depends on the query.

See [API.md](API.md) for full descriptions and response examples.

### Narrowing large payloads

Three endpoints mirror a whole scraped page and return far more than most callers need — a match's per-map performance matrices and economy tables, the full round-by-round replay, or an event's standings. Each accepts `include`, a comma-separated allowlist of top-level fields:

```
GET /v2/match/{match_id}/details?include=maps,teams
```

| Endpoint | Fields you can ask for |
|---|---|
| `/v2/match/details`, `/v2/match/{match_id}/details` | `event`, `date`, `map_vetos`, `status`, `teams`, `streams`, `vods`, `maps`, `head_to_head`, `performance`, `economy`, `economy_by_map` |
| `/v2/match/logs`, `/v2/match/{match_id}/logs` | `map`, `teams`, `rounds` |
| `/v2/event/{event_id}` | `event`, `stages`, `prizes`, `teams`, `standings` |

Omit `include` and the full payload comes back, exactly as before — the parameter is opt-in. `match_id` — and `game_id` on the logs endpoints — are always kept, and an unknown name returns HTTP 400 listing the valid ones. On match detail, a fieldset naming none of `performance`, `economy` or `economy_by_map` also skips those per-game tab fetches upstream, so narrowing costs vlr.gg less work as well as less bandwidth. Trimming happens after the cache, so a narrow request never shrinks what a later full request receives.

## Worked Examples

A path-based call — Shopify Rebellion Gold's map stats:

```bash
curl "http://127.0.0.1:3001/v2/team/14278/stats"
```

```json
{"status":"success","data":{"status":200,"segments":[{"map":"Bind","games":22,"win_pct":"55%","wins":12,"losses":10,"atk_first":11,"def_first":11,"atk_rwin_pct":"44%","atk_rw":102,"atk_rl":131,"def_rwin_pct":"60%","def_rw":142,"def_rl":93}]}}
```

Narrow a match detail to its teams:

```bash
curl "http://127.0.0.1:3001/v2/match/773435/details?include=teams"
```

```json
{"status":"success","data":{"status":200,"segments":[{"match_id":"773435","teams":[{"id":"21093","name":"Gentle Mates GC","tag":"","logo":"https://owcdn.net/img/6670153fa9120.png","score":"2","is_winner":true}]}]}}
```

Revalidate a cached ranking with its `ETag`:

```http
GET /v2/rankings?region=na
If-None-Match: "c47e01e3fd911b030c65cc60acaa3e3d7a2e2a6960bb72715265bf79575b86a4"

HTTP/1.1 304 Not Modified
ETag: "c47e01e3fd911b030c65cc60acaa3e3d7a2e2a6960bb72715265bf79575b86a4"
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 58
```

## Endpoint Reference

Every route — request parameters, response shapes and worked examples — is documented in **[API.md](API.md)**.

| Section | Covers |
|---|---|
| [V2 endpoints](API.md#v2-endpoints) | all `/v2` routes with example calls and responses |
| [Original endpoints](API.md#original-endpoints) | unversioned routes kept for backwards compatibility |
| [Region codes](API.md#region-codes) | the region taxonomy |
| [Validation & error handling](API.md#validation--error-handling) | validation rules and HTTP 400 shapes |
| [Caching](API.md#caching) | per-endpoint TTLs, `ETag` and `304 Not Modified` |
| [Meta](API.md#meta) | version metadata |

## Installation

### Requirements

- Python `3.11` locally (from `.python-version`). CI tests `3.11`–`3.14`, and the Docker image runs Python `3.14`
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/)

```bash
git clone https://github.com/axsddlr/vlrggapi/
cd vlrggapi
uv sync
```

`uv sync` creates `.venv` and installs the exact versions pinned in `uv.lock`,
including the `dev` dependency group. Prefix commands with `uv run` to run them
inside that environment — there is nothing to activate by hand.

### Run locally

```bash
uv run python main.py
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
uv run pytest tests/ -v
```

## Built With

- [FastAPI](https://fastapi.tiangolo.com/)
- [httpx](https://www.python-httpx.org/)
- [Selectolax](https://github.com/rushter/selectolax)
- [cachetools](https://github.com/tkem/cachetools)
- [uvicorn](https://www.uvicorn.org/)

Rate limiting is implemented in-house (`api/utils/rate_limiter.py`) with no additional dependency.

## Contributing

Issues and pull requests are welcome.

`master` is the only long-lived branch, and it is always deployed. Work on a
short-lived branch and open a pull request against `master`:

1. `git switch master && git pull --ff-only`
2. `git switch -c fix/your-slug`
3. Run `uv sync` and verify the app starts locally.
4. Run `uv run pytest -q` and `uv run ruff check .`.
5. Rebase onto `origin/master`, push, and open a pull request against `master`.

Pull requests are squash-merged, so `master` gets one readable commit per change.
Do not push work in progress to `master` — use a draft PR if you want CI feedback
early. Branch protection, commit hygiene, and how to revert a bad change are
documented in [WORKFLOW.md](WORKFLOW.md).

Open a [pull request](https://github.com/axsddlr/vlrggapi/compare) or file an [issue](https://github.com/axsddlr/vlrggapi/issues/new).

## License

The MIT License (MIT)
