import logging

import httpx

from utils.http_client import get_http_client
from utils.cache_manager import cache_manager
from utils.constants import CACHE_TTL_HEALTH_UPSTREAM

logger = logging.getLogger(__name__)


async def _check_upstream_sites(client: httpx.AsyncClient) -> dict:
    sites = ["https://vlrggapi.vercel.app", "https://vlr.gg"]
    results: dict[str, dict] = {}
    for site in sites:
        try:
            response = await client.get(site, timeout=5)
            results[site] = {
                "status": "Healthy" if response.status_code == 200 else "Unhealthy",
                "status_code": response.status_code,
            }
        except httpx.HTTPError:
            results[site] = {"status": "Unhealthy", "status_code": None}

    return results


async def check_health(include_upstream: bool = False):
    """
    Report local service readiness.

    Upstream checks are optional and cached to keep /health lightweight and
    suitable for container liveness probes.
    """
    client = get_http_client()
    results = {
        "service": {"status": "Healthy"},
        "http_client": {
            "status": "Healthy" if not client.is_closed else "Unhealthy",
            "status_code": None,
        },
    }

    if not include_upstream:
        return results

    cached = cache_manager.get(CACHE_TTL_HEALTH_UPSTREAM, "health_upstream")
    if cached is None:
        cached = await _check_upstream_sites(client)
        cache_manager.set(CACHE_TTL_HEALTH_UPSTREAM, cached, "health_upstream")
    results["upstream"] = cached

    return results
