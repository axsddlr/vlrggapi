import requests
from utils.constants import VLR_BASE_URL, API_BASEURL


def check_health():
    results = {}
    for site in [VLR_BASE_URL, API_BASEURL]:
        try:
            response = requests.get(site, timeout=5)
            results[site] = {
                "status": "Healthy" if response.status_code == 200 else "Unhealthy",
                "status_code": response.status_code,
            }
        except requests.RequestException:
            results[site] = {"status": "Unhealthy", "status_code": None}
    return results
