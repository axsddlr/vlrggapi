"""
V1 API router — backwards-compatible endpoints (deprecated).
"""
from fastapi import APIRouter, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from api.scrapers import (
    vlr_events,
    vlr_live_score,
    vlr_match_results,
    vlr_news,
    vlr_rankings,
    vlr_stats,
    vlr_upcoming_matches,
    vlr_upcoming_matches_extended,
    check_health,
)
from utils.constants import RATE_LIMIT

router = APIRouter(prefix="/v1", tags=["v1 (Deprecated)"])
limiter = Limiter(key_func=get_remote_address)


@router.get("/news")
@limiter.limit(RATE_LIMIT)
async def VLR_news(request: Request):
    """[Deprecated] Use /v2/news instead."""
    return await vlr_news()


@router.get("/stats")
@limiter.limit(RATE_LIMIT)
async def VLR_stats(
    request: Request,
    region: str = Query(..., description="Region shortname"),
    timespan: str = Query(..., description="Timespan (30, 60, 90, or all)"),
):
    """[Deprecated] Use /v2/stats instead."""
    return await vlr_stats(region, timespan)


@router.get("/rankings")
@limiter.limit(RATE_LIMIT)
async def VLR_ranks(
    request: Request, region: str = Query(..., description="Region shortname"),
):
    """[Deprecated] Use /v2/rankings instead. Returns old response shape for backwards compat."""
    data = await vlr_rankings(region)
    # Reshape to old format: {"status": int, "data": [...]}
    if "data" in data and "segments" in data["data"]:
        return {
            "status": data["data"]["status"],
            "data": data["data"]["segments"],
        }
    return data


@router.get("/match")
@limiter.limit(RATE_LIMIT)
async def VLR_match(
    request: Request,
    q: str,
    num_pages: int = Query(1, ge=1, le=600),
    from_page: int = Query(None, ge=1, le=600),
    to_page: int = Query(None, ge=1, le=600),
    max_retries: int = Query(3, ge=1, le=5),
    request_delay: float = Query(1.0, ge=0.5, le=5.0),
    timeout: int = Query(30, ge=10, le=120),
):
    """[Deprecated] Use /v2/match instead."""
    if q == "upcoming":
        return await vlr_upcoming_matches(num_pages, from_page, to_page)
    elif q == "upcoming_extended":
        return await vlr_upcoming_matches_extended(num_pages, from_page, to_page, max_retries, request_delay, timeout)
    elif q == "live_score":
        return await vlr_live_score(num_pages, from_page, to_page)
    elif q == "results":
        return await vlr_match_results(num_pages, from_page, to_page, max_retries, request_delay, timeout)
    else:
        return {"error": "Invalid query parameter"}


@router.get("/events")
@limiter.limit(RATE_LIMIT)
async def VLR_events(
    request: Request,
    q: str = Query(None, enum=["upcoming", "completed"]),
    page: int = Query(1, ge=1, le=100),
):
    """[Deprecated] Use /v2/events instead."""
    if q == "upcoming":
        return await vlr_events(upcoming=True, completed=False, page=page)
    elif q == "completed":
        return await vlr_events(upcoming=False, completed=True, page=page)
    else:
        return await vlr_events(upcoming=True, completed=True, page=page)


@router.get("/health")
async def health():
    """[Deprecated] Use /v2/health instead."""
    return await check_health()
