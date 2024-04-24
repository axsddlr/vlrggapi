from fastapi import APIRouter, Request
from api.scrape import Vlr
from slowapi import Limiter
from slowapi.util import get_remote_address

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
vlr = Vlr()


@router.get("/news")
@limiter.limit("250/minute")
async def VLR_news(request: Request):
    return vlr.vlr_news()


@router.get("/match/results")
@limiter.limit("250/minute")
async def VLR_scores(request: Request):
    return vlr.vlr_match_results()


@router.get("/stats/{region}/{timespan}")
@limiter.limit("250/minute")
async def VLR_stats(region, timespan, request: Request):
    return vlr.vlr_stats(region, timespan)


@router.get("/rankings/{region}")
@limiter.limit("250/minute")
async def VLR_ranks(region, request: Request):
    return vlr.vlr_rankings(region)


@router.get("/match/upcoming")
@limiter.limit("250/minute")
async def VLR_upcoming(request: Request):
    return vlr.vlr_upcoming_matches()


@router.get("/match/live_score")
@limiter.limit("250/minute")
async def VLR_live_score(request: Request):
    return vlr.vlr_live_score()


@router.get("/health")
def health():
    return "Healthy: OK"
