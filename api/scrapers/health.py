from utils.http_client import get_http_client


async def check_health() -> dict:
    """
    Report local service readiness.

    Only in-process state is inspected, so this stays cheap enough to serve as a
    container liveness probe.
    """
    client = get_http_client()
    return {
        "service": {"status": "Healthy"},
        "http_client": {
            "status": "Healthy" if not client.is_closed else "Unhealthy",
            "status_code": None,
        },
    }
