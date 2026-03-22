import pytest

from fastapi import HTTPException

from api.scrapers.teams import vlr_team, vlr_team_matches, vlr_team_transactions


class FakeResponse:
    def __init__(self, status_code: int, text: str = "<html></html>"):
        self.status_code = status_code
        self.text = text


class FakeAsyncClient:
    def __init__(self, response: FakeResponse):
        self.response = response
        self.calls: list[tuple[str, int | None]] = []

    async def get(self, url: str, timeout=None):
        self.calls.append((url, timeout))
        return self.response


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("scraper", "args", "expected_status", "expected_detail"),
    [
        (vlr_team, ("77",), 404, "VLR.GG returned status 404 for team 77"),
        (
            vlr_team_matches,
            ("77", 3),
            503,
            "VLR.GG returned status 503 for team matches 77 page 3",
        ),
        (
            vlr_team_transactions,
            ("77",),
            429,
            "VLR.GG returned status 429 for team transactions 77",
        ),
    ],
)
async def test_team_scrapers_raise_http_errors_for_upstream_failures(
    monkeypatch, scraper, args, expected_status, expected_detail
):
    client = FakeAsyncClient(FakeResponse(expected_status))

    monkeypatch.setattr("api.scrapers.teams.get_http_client", lambda: client)

    with pytest.raises(HTTPException) as exc_info:
        await scraper(*args)

    assert exc_info.value.status_code == expected_status
    assert exc_info.value.detail == expected_detail
