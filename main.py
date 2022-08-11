import uvicorn
from fastapi import FastAPI

from api.scrape import Vlr
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

# It's creating an instance of the Limiter class.
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="vlrggapi",
    description="An Unofficial REST API for [vlr.gg](https://www.vlr.gg/), a site for Valorant Esports match and news "
                "coverage. Made by [Rehkloos](https://github.com/Rehkloos)",
    version="1.0.5",
    docs_url="/",
    redoc_url=None,
)
vlr = Vlr()

TEN_MINUTES = 600

# It's setting the rate limit for the API.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.get("/news")
@limiter.limit("250/minute")
async def VLR_news():
    return vlr.vlr_recent()


@app.get("/match/results")
@limiter.limit("250/minute")
async def VLR_scores():
    return vlr.vlr_score()


@app.get("/stats/{region}/{timespan}")
@limiter.limit("250/minute")
async def VLR_stats(region, timespan):
    """
    region shortnames:
        "na" -> "north-america",
        "eu" -> "europe",
        "ap" -> "asia-pacific",
        "sa" -> "latin-america",
        "jp" -> "japan",
        "oce" -> "oceania",
        "mn" -> "mena",

    timespan:
        "30" -> 30 days,
        "60" -> 60 days,
        "90" -> 90 days,
    """
    return vlr.vlr_stats(region, timespan)


@app.get("/rankings/{region}")
@limiter.limit("250/minute")
async def VLR_ranks(region):
    """
    region shortnames:
        "na" -> "north-america",
        "eu" -> "europe",
        "ap" -> "asia-pacific",
        "la" -> "latin-america",
        "la-s" -> "la-s",
        "la-n" -> "la-n",
        "oce" -> "oceania",
        "kr" -> "korea",
        "mn" -> "mena",
        "gc" -> "game-changers",
        "br" -> "Brazil",
        "ch" -> "china",
    """
    return vlr.vlr_rankings(region)


@app.get("/match/upcoming")
@limiter.limit("250/minute")
async def VLR_upcoming():
    return vlr.vlr_upcoming()


@app.get('/health')
def health():
    return "Healthy: OK"


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=3001)
