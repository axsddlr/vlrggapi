# Improvement Plan

Codebase: vlrggapi
Last verified against the code: 2026-10-03

Every open item below was re-derived from the source on that date. Earlier
revisions of this file pointed at `api/scrapers/match_detail.py` and
`api/scrapers/teams.py`, which no longer exist — both are packages now — so
their line references had become unusable. Treat the references here as
authoritative; re-check them before acting if the file has moved on.

## Closed

### 2026-03-20 plan — all 22 items verified closed
Critical, High, and Medium items are all done (paginated-scrape failure
surfacing, cache poisoning guard, shared retry/backoff, selector-based rankings
and stats parsing, per-game tab fetching, legacy-route validation parity, CI
gating before image publication, fixture-backed parser tests, live-detail
semaphore, pagination 400s for `upcoming`/`live_score`, news parser rewrite,
non-200 handling in team scrapers, cache coalescing, Docker workflow digest fix,
Python version alignment). Fix commits are in git history.

### Closed on 2026-10-03
- **Split the two oversized scrapers** — `api/scrapers/match_detail/`
  (`crawler.py` + `parsers.py`) and `api/scrapers/teams/`
  (`crawlers.py` + `parsers.py`) already replaced the 787/788-line modules.
- **Removed the unused `_iter_children_deep` helper** — gone repo-wide.
- **Fixed the stale `CLAUDE.md` claims** — "No test suite exists" and
  "models/ is untracked" are no longer present.
- **Dropped `Optional[X]` in favour of `X | None`** — no `Optional[` remains.
- **Raise before parsing on non-200** — done at `matches.py:50`,
  `rankings.py:109`, `stats.py:158`, and `events.py:122`.
- **Deduplicated the padding loops** — 11 ad-hoc `while len(x) < 2` loops now
  use `pad_to_length()` in `utils/html_parsers.py`.
- **Deduplicated the selector-fallback loops** — the three identical loops in
  `teams/crawlers.py` now use `find_elements_by_selectors()`.
- **Replaced player/team URL magic strings** — `VLR_PLAYER_URL` /
  `VLR_TEAM_URL` in `utils/constants.py`; 8 call sites migrated.
- **`/version` now has one runtime source of truth** — `API_VERSION` in
  `utils/constants.py`, with `tests/test_version_consistency.py` failing if it
  drifts from `pyproject.toml`.
- **Deleted the dead health upstream check** — `include_upstream`,
  `_check_upstream_sites`, and `CACHE_TTL_HEALTH_UPSTREAM` were unreachable:
  `shared_handlers.py` called `check_health()` with no arguments, so the probe
  that pinged `vlrggapi.vercel.app` could never run.
- **Consolidated the async test client fixture** — `tests/conftest.py` only.
- **Removed unused params** from `vlr_upcoming_matches` / `vlr_live_score`
  (they accepted `num_pages`/`from_page`/`to_page` and never read them; the 400
  guard lives in `routers/shared_handlers.py`).
- **Removed the unused `lxml` dependency** — declared since 2022, unused since
  the BeautifulSoup→selectolax port in Nov 2022.
- **Corrected the README's player/team `matches` and `transactions` response
  examples** — they documented a `{matches, page}` / `{transactions}` envelope
  that the API never returned; the real shape is
  `{status, segments}` with `meta.page`.

## Open

### 1. Parser-level test coverage (highest leverage)
The dominant maintenance risk remains untested parsing, not request plumbing.
Coverage from the 2026-10-03 run:

| Module | Cover |
|---|---|
| `api/scrapers/teams/parsers.py` | 9% |
| `api/scrapers/search.py` | 19% |
| `api/scrapers/teams/crawlers.py` | 29% |
| `api/scrapers/players.py` | 36% |
| `api/scrapers/event_detail.py` | 53% |

Note this is the area the 2026-10-03 refactors touched, so the shared helpers
(`pad_to_length`, `find_elements_by_selectors`) have unit tests but the parsers
that call them largely do not. Fixture-backed tests here would also make future
selector fixes safer.

### 2. `utils/pagination.py` bypasses the shared HTTP client
`utils/pagination.py:131` calls `client.get()` directly. Retry/backoff already
exists locally (lines 121-156) and exhaustion correctly raises 502 (lines
168-176), so the earlier note that pages "fail without backoff or retry" was
wrong. The real residual is duplication: this re-implements retry policy and
skips the circuit breaker in `utils/http_client.py`. Switching to
`fetch_with_retries` would unify both.

### 3. `CLAUDE.md` has two verified-false claims
- Gotchas: "Rate limit is per-IP: slowapi uses `get_remote_address`" — slowapi
  is not a dependency; the limiter is `api/utils/rate_limiter.py` (tiered
  sliding window, keyed on `X-Forwarded-For` with a `request.client.host`
  fallback).
- Gotchas: "`match_detail.py` and `teams.py` are large (~787/788 lines) …
  Splitting into sub-modules is tracked in `tasks/todo.md`" — both are packages
  now, and this file is not tracking that work.

### 4. Non-200 handling has three different contracts
Pick one and apply it. Currently:
- raise via `raise_for_upstream_status` — `matches.py:50`, `rankings.py:109`,
  `stats.py:158`
- return `upstream_error_payload` — `events.py:123`, `players.py:528`
- log then raise `HTTPException(status_code=status)` —
  `teams/crawlers.py:59,112,151,205,280,369`

The third also propagates upstream 4xx as 4xx, which is defensible, but the
inconsistency makes V2's `_wrap_v2` error path harder to reason about.

### 5. Repo hygiene
- Eight untracked `debug_*.py` scratch scripts in the repo root produce 33
  `ruff check .` errors (`E401`, `I001`, `F401`, `W293`, `F541`). CI is green
  only because they are untracked — delete them or add them to `.gitignore`.
- `tasks/` and `CLAUDE.md` are untracked, so this file is invisible to
  contributors and to CI. That is why it drifted out of date. Commit or drop.

## Considered and declined

- **"Deduplicate `_text()` with `extract_text_content()`"** — they are not
  duplicates. `_text` (`teams/parsers.py:23`) returns `element.text(strip=strip)`
  while `extract_text_content` (`utils/html_parsers.py:13`) additionally
  collapses internal whitespace. Same signature, different output, 33 `_text`
  and 15 `_attr` call sites (`_attr` has no counterpart at all). Swapping them
  would silently change parsed team data.
- **"Bare `except Exception` catches `KeyboardInterrupt`/`SystemExit`"** — it
  does not; both derive from `BaseException`. Over-broad catching is a style
  question, and several sites are deliberate soft fallbacks (for example
  `matches.py:164` returns `None` for one failed match-detail fetch so the rest
  of the request still succeeds).
- **"Inconsistent log levels"** — the levels are coherent. `warning` marks
  recoverable degradation, an expected fallback, a retryable attempt, or a
  client-caused upstream status that is propagated as-is (a 404 stays a 404);
  `error`/`exception` mark terminal server-side faults (`pagination.py:160` on
  exhausted retries, `utils/error_handling.py:62,66,69`). `pagination.py` is not
  inconsistent with `matches.py` — both log retryable attempts at `warning` and
  only escalate to `error` when retries are exhausted.
