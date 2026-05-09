import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from api.utils.rate_limiter import RateLimitMiddleware
from routers.v2_router import router as v2_router
from routers.vlr_router import router as vlr_router
from utils.constants import API_DESCRIPTION, API_PORT, API_TITLE
from utils.http_client import close_http_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting vlrggapi")
    yield
    logger.info("Shutting down — closing HTTP client")
    await close_http_client()


app = FastAPI(
    title=API_TITLE,
    description=API_DESCRIPTION,
    docs_url="/",
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(RateLimitMiddleware)

app.include_router(vlr_router)
app.include_router(v2_router)


@app.get("/version", tags=["Meta"])
def version():
    return {"version": "2.0.0", "default_api": "v2"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=API_PORT)
