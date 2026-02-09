import logging

import httpx

from utils.http_client import get_http_client

logger = logging.getLogger(__name__)


async def check_health():
    sites = ["https://vlrggapi.vercel.app", "https://vlr.gg"]
    results = {}
    client = get_http_client()
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
