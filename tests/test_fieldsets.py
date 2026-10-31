"""The `include=` fieldset parameter on the fat V2 payloads.

Trimming happens in the router, after the (cached) scraper call, so these tests
drive the routes with fake handlers: the handler owns the untrimmed payload and
the router is responsible for narrowing it.
"""
import pytest

from main import app

# ---------------------------------------------------------------------------
# Fixtures and payloads
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolated_rate_limiter():
    """Keep the shared in-memory limiter out of these tests.

    These routes sit in the expensive tier (20 requests/min) and this module
    makes far more requests than that, so without isolation the later tests
    would assert 429 instead of the fieldset behaviour under test. Same
    pattern as tests/test_v2_subresources.py.
    """
    from api.utils.rate_limiter import get_rate_limiter

    stores = get_rate_limiter()._stores
    stores.clear()
    yield
    stores.clear()


MATCH_DETAIL_KEYS = [
    "match_id",
    "event",
    "date",
    "map_vetos",
    "status",
    "teams",
    "streams",
    "vods",
    "maps",
    "head_to_head",
    "performance",
    "economy",
    "economy_by_map",
]

EVENT_DETAIL_KEYS = ["event", "stages", "prizes", "teams", "standings"]


def _detail_segment() -> dict:
    return {
        "match_id": "123",
        "event": {"name": "Champions 2026"},
        "date": "2026-01-01",
        "map_vetos": [{"team": "A", "map": "Ascent", "type": "ban"}],
        "status": "completed",
        "teams": [{"id": "1", "name": "A"}, {"id": "2", "name": "B"}],
        "streams": [{"name": "Twitch", "url": "https://twitch.tv/x"}],
        "vods": [{"name": "YouTube", "url": "https://youtu.be/x"}],
        "maps": [{"map": "Ascent", "score": "13-7"}],
        "head_to_head": [{"match_id": "100", "winner": "A"}],
        "performance": {"A": {"player": "x", "rating": 1.2}},
        "economy": {"A": {"pistol": 1}},
        "economy_by_map": {"Ascent": {"A": {"pistol": 1}}},
    }


def _detail_payload() -> dict:
    return {"data": {"status": 200, "segments": [_detail_segment()]}}


def _logs_payload() -> dict:
    return {
        "data": {
            "status": 200,
            "segments": [
                {
                    "match_id": "123",
                    "game_id": "456",
                    "map": {"name": "Ascent", "score": "13-7"},
                    "teams": [{"name": "A"}, {"name": "B"}],
                    "rounds": [{"round": 1, "winner": "A"}],
                }
            ],
        }
    }


def _event_payload() -> dict:
    return {
        "data": {
            "status": 200,
            "segments": {
                "event": {"name": "Champions 2026"},
                "stages": [{"slug": "playoffs", "active": True}],
                "prizes": [{"place": "1st", "prize": "$500,000"}],
                "teams": [{"name": "A"}],
                "standings": [{"stage": "Playoffs", "rows": []}],
            },
        }
    }


def _patch_detail(monkeypatch, factory=_detail_payload, *, copy_result=True):
    """Install a fake match-detail handler and return its call log."""
    calls = []

    async def fake_detail(match_id, light=False):
        calls.append({"match_id": match_id, "light": light})
        payload = factory()
        if not copy_result:
            return payload
        return _copy(payload)

    monkeypatch.setattr("routers.v2_router.get_match_detail_data", fake_detail)
    return calls


def _patch_logs(monkeypatch, factory=_logs_payload):
    calls = []

    async def fake_logs(match_id, game_id=None):
        calls.append({"match_id": match_id, "game_id": game_id})
        return _copy(factory())

    monkeypatch.setattr("routers.v2_router.get_match_logs_data", fake_logs)
    return calls


def _patch_event(monkeypatch, factory=_event_payload):
    calls = []

    async def fake_event(event_id, stage=None):
        calls.append({"event_id": event_id, "stage": stage})
        return _copy(factory())

    monkeypatch.setattr("routers.v2_router.get_event_detail_data", fake_event)
    return calls


def _copy(payload: dict) -> dict:
    """Copy a fake payload the way a cache hit would hand it over: by value."""
    import copy

    return copy.deepcopy(payload)


def _segments(resp) -> list:
    body = resp.json()
    assert body["status"] == "success"
    return body["data"]["segments"]


# ---------------------------------------------------------------------------
# /v2/match/details — both route forms
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_match_detail_path_include_keeps_only_named_fields(
    async_client, monkeypatch
):
    _patch_detail(monkeypatch)

    resp = await async_client.get(
        "/v2/match/123/details", params={"include": "maps,teams"}
    )

    assert resp.status_code == 200
    segments = _segments(resp)
    assert len(segments) == 1
    assert set(segments[0]) == {"match_id", "maps", "teams"}


@pytest.mark.anyio
async def test_match_detail_query_include_keeps_only_named_fields(
    async_client, monkeypatch
):
    _patch_detail(monkeypatch)

    resp = await async_client.get(
        "/v2/match/details", params={"match_id": "123", "include": "maps,teams"}
    )

    assert resp.status_code == 200
    assert set(_segments(resp)[0]) == {"match_id", "maps", "teams"}


@pytest.mark.anyio
async def test_match_detail_without_include_returns_every_field(
    async_client, monkeypatch
):
    _patch_detail(monkeypatch)

    resp = await async_client.get("/v2/match/123/details")

    assert resp.status_code == 200
    segment = _segments(resp)[0]
    assert set(segment) == set(MATCH_DETAIL_KEYS)
    assert len(segment) == 13


@pytest.mark.anyio
@pytest.mark.parametrize("include", ["", "   ", ",", " , "])
async def test_match_detail_blank_include_returns_every_field(
    async_client, monkeypatch, include
):
    _patch_detail(monkeypatch)

    resp = await async_client.get(
        "/v2/match/123/details", params={"include": include}
    )

    assert resp.status_code == 200
    assert set(_segments(resp)[0]) == set(MATCH_DETAIL_KEYS)


@pytest.mark.anyio
async def test_match_detail_include_is_case_and_space_tolerant(
    async_client, monkeypatch
):
    _patch_detail(monkeypatch)

    resp = await async_client.get(
        "/v2/match/123/details", params={"include": " Maps , Teams "}
    )

    assert resp.status_code == 200
    assert set(_segments(resp)[0]) == {"match_id", "maps", "teams"}


@pytest.mark.anyio
async def test_match_detail_include_may_name_the_always_kept_id(
    async_client, monkeypatch
):
    _patch_detail(monkeypatch)

    resp = await async_client.get(
        "/v2/match/123/details", params={"include": "match_id,maps"}
    )

    assert resp.status_code == 200
    keys = list(_segments(resp)[0])
    assert set(keys) == {"match_id", "maps"}
    assert keys.count("match_id") == 1


# ---------------------------------------------------------------------------
# /v2/match/details — the include decides whether upstream tabs are worth it
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_match_detail_include_tab_field_fetches_tabs(
    async_client, monkeypatch
):
    calls = _patch_detail(monkeypatch)

    resp = await async_client.get(
        "/v2/match/123/details", params={"include": "performance"}
    )

    assert resp.status_code == 200
    assert calls[0]["light"] is False


@pytest.mark.anyio
async def test_match_detail_include_without_tab_fields_skips_tabs(
    async_client, monkeypatch
):
    calls = _patch_detail(monkeypatch)

    resp = await async_client.get("/v2/match/123/details", params={"include": "maps"})

    assert resp.status_code == 200
    assert calls[0]["light"] is True


@pytest.mark.anyio
async def test_match_detail_economy_fields_keep_tabs(async_client, monkeypatch):
    calls = _patch_detail(monkeypatch)

    resp = await async_client.get(
        "/v2/match/123/details", params={"include": "economy_by_map"}
    )

    assert resp.status_code == 200
    assert calls[0]["light"] is False


@pytest.mark.anyio
async def test_match_detail_without_include_fetches_tabs(async_client, monkeypatch):
    calls = _patch_detail(monkeypatch)

    resp = await async_client.get("/v2/match/123/details")

    assert resp.status_code == 200
    assert calls[0]["light"] is False


@pytest.mark.anyio
async def test_match_detail_explicit_light_is_preserved_with_include(
    async_client, monkeypatch
):
    calls = _patch_detail(monkeypatch)

    resp = await async_client.get(
        "/v2/match/123/details", params={"include": "maps", "light": "true"}
    )

    assert resp.status_code == 200
    assert calls[0]["light"] is True


@pytest.mark.anyio
async def test_match_detail_query_form_also_gates_tabs(async_client, monkeypatch):
    calls = _patch_detail(monkeypatch)

    resp = await async_client.get(
        "/v2/match/details", params={"match_id": "123", "include": "maps"}
    )

    assert resp.status_code == 200
    assert calls[0]["light"] is True


# ---------------------------------------------------------------------------
# /v2/match/details — unknown names
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_match_detail_rejects_unknown_include(async_client, monkeypatch):
    calls = _patch_detail(monkeypatch)

    resp = await async_client.get("/v2/match/123/details", params={"include": "foo"})

    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert "foo" in detail
    assert detail.startswith("Invalid include")
    assert "Valid fields:" in detail
    for name in MATCH_DETAIL_KEYS[1:]:
        assert name in detail
    # Rejected before spending an upstream fetch.
    assert calls == []


@pytest.mark.anyio
async def test_match_detail_rejects_unknown_include_in_query_form(
    async_client, monkeypatch
):
    _patch_detail(monkeypatch)

    resp = await async_client.get(
        "/v2/match/details", params={"match_id": "123", "include": "maps,nope"}
    )

    assert resp.status_code == 400
    assert "nope" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# /v2/match/logs — both route forms
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_match_logs_include_rounds_keeps_ids(async_client, monkeypatch):
    _patch_logs(monkeypatch)

    resp = await async_client.get(
        "/v2/match/123/logs", params={"include": "rounds"}
    )

    assert resp.status_code == 200
    assert set(_segments(resp)[0]) == {"match_id", "game_id", "rounds"}


@pytest.mark.anyio
async def test_match_logs_include_map_keeps_ids(async_client, monkeypatch):
    _patch_logs(monkeypatch)

    resp = await async_client.get(
        "/v2/match/logs", params={"match_id": "123", "include": "map"}
    )

    assert resp.status_code == 200
    assert set(_segments(resp)[0]) == {"match_id", "game_id", "map"}


@pytest.mark.anyio
async def test_match_logs_without_include_returns_every_field(
    async_client, monkeypatch
):
    _patch_logs(monkeypatch)

    resp = await async_client.get("/v2/match/123/logs")

    assert resp.status_code == 200
    assert set(_segments(resp)[0]) == {
        "match_id",
        "game_id",
        "map",
        "teams",
        "rounds",
    }


@pytest.mark.anyio
async def test_match_logs_rejects_unknown_include(async_client, monkeypatch):
    _patch_logs(monkeypatch)

    resp = await async_client.get(
        "/v2/match/123/logs", params={"include": "positions"}
    )

    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert "positions" in detail
    for name in ("map", "teams", "rounds"):
        assert name in detail


# ---------------------------------------------------------------------------
# /v2/event/{event_id} — segments is a dict, not a list
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_event_detail_include_trims_the_segments_dict(
    async_client, monkeypatch
):
    _patch_event(monkeypatch)

    resp = await async_client.get("/v2/event/123", params={"include": "standings"})

    assert resp.status_code == 200
    segments = _segments(resp)
    assert isinstance(segments, dict)
    assert set(segments) == {"standings"}


@pytest.mark.anyio
async def test_event_detail_without_include_returns_every_field(
    async_client, monkeypatch
):
    _patch_event(monkeypatch)

    resp = await async_client.get("/v2/event/123")

    assert resp.status_code == 200
    assert set(_segments(resp)) == set(EVENT_DETAIL_KEYS)


@pytest.mark.anyio
async def test_event_detail_rejects_unknown_include(async_client, monkeypatch):
    _patch_event(monkeypatch)

    resp = await async_client.get("/v2/event/123", params={"include": "brackets"})

    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert "brackets" in detail
    for name in EVENT_DETAIL_KEYS:
        assert name in detail


# ---------------------------------------------------------------------------
# Rule 4: odd payload shapes are passed through, never raised on
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_payload_without_segments_is_untouched(async_client, monkeypatch):
    _patch_detail(
        monkeypatch,
        factory=lambda: {"data": {"status": 200}},
        copy_result=False,
    )

    resp = await async_client.get("/v2/match/123/details", params={"include": "maps"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert body["data"] == {"status": 200}


@pytest.mark.anyio
async def test_non_list_segments_is_untouched(async_client, monkeypatch):
    _patch_detail(
        monkeypatch,
        factory=lambda: {"data": {"status": 200, "segments": "not-a-list"}},
        copy_result=False,
    )

    resp = await async_client.get("/v2/match/123/details", params={"include": "maps"})

    assert resp.status_code == 200
    assert resp.json()["data"]["segments"] == "not-a-list"


@pytest.mark.anyio
async def test_segments_none_is_untouched(async_client, monkeypatch):
    _patch_detail(
        monkeypatch,
        factory=lambda: {"data": {"status": 200, "segments": None}},
        copy_result=False,
    )

    resp = await async_client.get("/v2/match/123/details", params={"include": "maps"})

    assert resp.status_code == 200
    assert resp.json()["data"]["segments"] is None


# ---------------------------------------------------------------------------
# Cache safety: trim after the handler, never in place
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_trimming_never_mutates_the_shared_payload(async_client, monkeypatch):
    """The scraper caches one payload for every include combination.

    A trimmed request must not write the trimmed shape back into that object,
    otherwise the next (untrimmed) caller would receive the narrowed payload.
    """
    shared = _detail_payload()
    _patch_detail(monkeypatch, factory=lambda: shared, copy_result=False)

    first = await async_client.get("/v2/match/123/details", params={"include": "maps"})
    assert set(_segments(first)[0]) == {"match_id", "maps"}
    # The payload the handler handed back (cache-owned) is still complete.
    assert set(shared["data"]["segments"][0]) == set(MATCH_DETAIL_KEYS)

    second = await async_client.get("/v2/match/123/details")
    assert second.status_code == 200
    assert set(_segments(second)[0]) == set(MATCH_DETAIL_KEYS)


# ---------------------------------------------------------------------------
# The legacy unversioned routes ignore include entirely
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_legacy_match_details_ignores_include(async_client, monkeypatch):
    async def fake_detail(match_id, light=False):
        return _detail_payload()

    monkeypatch.setattr("routers.vlr_router.get_match_detail_data", fake_detail)

    resp = await async_client.get(
        "/match/details", params={"match_id": "123", "include": "maps"}
    )

    assert resp.status_code == 200
    segment = resp.json()["data"]["segments"][0]
    assert set(segment) == set(MATCH_DETAIL_KEYS)


# ---------------------------------------------------------------------------
# Documented contract: the parameter and its valid names are in the schema
# ---------------------------------------------------------------------------


def _query_param(schema: dict, path: str, name: str) -> dict:
    operation = schema["paths"][path]["get"]
    return next(p for p in operation["parameters"] if p["name"] == name)


@pytest.mark.parametrize(
    ("path", "names"),
    [
        ("/v2/match/details", MATCH_DETAIL_KEYS[1:]),
        ("/v2/match/{match_id}/details", MATCH_DETAIL_KEYS[1:]),
        ("/v2/match/logs", ["map", "teams", "rounds"]),
        ("/v2/match/{match_id}/logs", ["map", "teams", "rounds"]),
        ("/v2/event/{event_id}", EVENT_DETAIL_KEYS),
    ],
)
def test_include_is_documented_with_its_valid_fields(path, names):
    param = _query_param(app.openapi(), path, "include")

    assert param["required"] is False
    description = param["description"]
    assert "omitting it returns everything" in description.lower()
    for name in names:
        assert name in description
