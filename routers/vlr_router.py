"""
Redirect router — unversioned routes redirect to /v2/*.
"""
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

router = APIRouter(tags=["Redirects"], include_in_schema=False)


@router.get("/news")
async def redirect_news(request: Request):
    return RedirectResponse(url="/v2/news", status_code=301)


@router.get("/stats")
async def redirect_stats(request: Request):
    url = f"/v2/stats?{request.query_params}" if request.query_params else "/v2/stats"
    return RedirectResponse(url=url, status_code=301)


@router.get("/rankings")
async def redirect_rankings(request: Request):
    url = f"/v2/rankings?{request.query_params}" if request.query_params else "/v2/rankings"
    return RedirectResponse(url=url, status_code=301)


@router.get("/match")
async def redirect_match(request: Request):
    url = f"/v2/match?{request.query_params}" if request.query_params else "/v2/match"
    return RedirectResponse(url=url, status_code=301)


@router.get("/events")
async def redirect_events(request: Request):
    url = f"/v2/events?{request.query_params}" if request.query_params else "/v2/events"
    return RedirectResponse(url=url, status_code=301)


@router.get("/health")
async def redirect_health(request: Request):
    return RedirectResponse(url="/v2/health", status_code=301)
