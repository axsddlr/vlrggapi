import uvicorn
from fastapi import FastAPI

from api.scrape import Vlr
from ratelimit import limits

app = FastAPI(
    title="vlrggapi",
    description="An Unofficial REST API for [vlr.gg](https://www.vlr.gg/), a site for Valorant Esports match and news "
                "coverage. Made by [Rehkloos](https://github.com/Rehkloos)",
    version="1.0.3",
    docs_url="/",
    redoc_url=None,
)
vlr = Vlr()

TEN_MINUTES = 600


@limits(calls=50, period=TEN_MINUTES)
@app.get("/news")
async def VLR_news():
    return vlr.vlr_recent()


@limits(calls=50, period=TEN_MINUTES)
@app.get("/match/results")
async def VLR_scores():
    return vlr.vlr_score()


@limits(calls=50, period=TEN_MINUTES)
@app.get("/stats/{region}")
async def VLR_stats(region):
    return vlr.vlr_stats(region)


@limits(calls=50, period=TEN_MINUTES)
@app.get("/rankings/{region}")
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


@limits(calls=50, period=TEN_MINUTES)
@app.get("/match/upcoming")
async def VLR_upcoming():
    return vlr.vlr_upcoming()


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=3001)
