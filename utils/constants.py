"""
Configuration constants for VLR.GG API
"""

# Base URLs
VLR_BASE_URL = "https://www.vlr.gg"
VLR_EVENTS_URL = f"{VLR_BASE_URL}/events"
VLR_MATCHES_URL = f"{VLR_BASE_URL}/matches"
VLR_RANKINGS_URL = f"{VLR_BASE_URL}/rankings"
VLR_STATS_URL = f"{VLR_BASE_URL}/stats"
VLR_NEWS_URL = f"{VLR_BASE_URL}/news"

# Rate limiting
RATE_LIMIT = "600/minute"

# API Settings
API_TITLE = "vlrggapi"
API_DESCRIPTION = (
    "An Unofficial REST API for [vlr.gg](https://www.vlr.gg/), "
    "a site for Valorant Esports match and news coverage. "
    "Made by [axsddlr](https://github.com/axsddlr)"
)
API_PORT = 3001

# Pagination limits
MAX_PAGE_LIMIT = 100
MIN_PAGE_LIMIT = 1

# Request settings
DEFAULT_TIMEOUT = 30
DEFAULT_RETRIES = 3
DEFAULT_REQUEST_DELAY = 1.0

# Cache TTLs (seconds)
CACHE_TTL_LIVE = 30
CACHE_TTL_UPCOMING = 300
CACHE_TTL_RESULTS = 3600
CACHE_TTL_NEWS = 600
CACHE_TTL_STATS = 1800
CACHE_TTL_RANKINGS = 3600
CACHE_TTL_EVENTS = 1800
CACHE_MAX_SIZE = 1000

# Cache TTLs — new scraper endpoints
CACHE_TTL_MATCH_DETAIL = 300
CACHE_TTL_MATCH_DETAIL_LIVE = 30
CACHE_TTL_PLAYER = 1800
CACHE_TTL_PLAYER_MATCHES = 600
CACHE_TTL_TEAM = 1800
CACHE_TTL_TEAM_MATCHES = 600
CACHE_TTL_TEAM_TRANSACTIONS = 3600
CACHE_TTL_EVENT_MATCHES = 600
