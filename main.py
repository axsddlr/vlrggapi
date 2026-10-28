import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.utils.rate_limiter import RateLimitMiddleware
from routers.v2_router import router as v2_router
from routers.vlr_router import router as vlr_router
from utils.conditional import ConditionalGetMiddleware
from utils.constants import API_DESCRIPTION, API_PORT, API_TITLE, API_VERSION
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

# Starlette inserts each add_middleware() call at index 0 and builds the stack
# by wrapping in reverse, so the last one added is the outermost. Registration
# below is therefore innermost-first, giving (outermost -> innermost):
#   CORSMiddleware -> RateLimitMiddleware -> ConditionalGetMiddleware
# CORS must stay outermost so even a 429 is readable by browsers instead of
# surfacing as an opaque network error. ConditionalGet sits inside the rate
# limiter on purpose: a 304 still consumes rate-limit budget and still carries
# the X-RateLimit-* headers.
app.add_middleware(ConditionalGetMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Retry-After", "X-RateLimit-Limit", "X-RateLimit-Remaining"],
)

app.include_router(vlr_router)
app.include_router(v2_router)


@app.get("/version", tags=["Meta"])
def version():
    return {"version": API_VERSION, "default_api": "v2"}


if __name__ == "__main__":
    # Most PaaS hosts (Render, Railway, Heroku) inject the listen port at runtime;
    # fall back to the packaged default for local and Docker Compose use.
    port = int(os.environ.get("PORT", API_PORT))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
