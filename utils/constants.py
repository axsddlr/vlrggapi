"""
Configuration constants for VLR.GG API
"""

# Base URLs
VLR_BASE_URL = "https://www.vlr.gg"
VLR_EVENTS_URL = f"{VLR_BASE_URL}/events"

# Rate limiting
RATE_LIMIT = "600/minute"

# API Settings
API_TITLE = "vlrggapi"
API_DESCRIPTION = "An Unofficial REST API for [vlr.gg](https://www.vlr.gg/), a site for Valorant Esports match and news coverage. Made by [axsddlr](https://github.com/axsddlr)"
API_PORT = 3001

# Pagination limits
MAX_PAGE_LIMIT = 100
MIN_PAGE_LIMIT = 1

# Request settings
DEFAULT_TIMEOUT = 30
DEFAULT_RETRIES = 3
DEFAULT_REQUEST_DELAY = 1.0