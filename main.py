from fastapi import FastAPI
import uvicorn
from api.scrape import Vlr
from ratelimit import limits


app = FastAPI()
vlr = Vlr()

TEN_MINUTES = 600


@app.get("/")
async def root():
    return {"message": "Hello World"}


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
    return vlr.vlr_rankings(region)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=3001)
