import requests

def check_health():
    sites = ["https://vlrggapi.vercel.app", "https://vlr.gg"]
    results = {}
    for site in sites:
        try:
            response = requests.get(site, timeout=5)
            results[site] = {
                "status": "Healthy" if response.status_code == 200 else "Unhealthy",
                "status_code": response.status_code,
            }
        except requests.RequestException:
            results[site] = {"status": "Unhealthy", "status_code": None}
    return results
