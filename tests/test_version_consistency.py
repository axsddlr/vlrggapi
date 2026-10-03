"""The reported API version must not drift from the packaged version."""
import tomllib
from pathlib import Path

import pytest

from utils.constants import API_VERSION

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


def test_api_version_matches_pyproject():
    declared = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]["version"]

    assert API_VERSION == declared


@pytest.mark.anyio
async def test_version_endpoint_reports_the_api_version(async_client):
    resp = await async_client.get("/version")

    assert resp.json()["version"] == API_VERSION
