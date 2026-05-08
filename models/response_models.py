"""
Pydantic response models used by active API routes.
"""
from typing import Any

from pydantic import BaseModel


class V2Response(BaseModel):
    """Standard response envelope for all /v2 endpoints."""
    status: str = "success"
    data: Any = None
    meta: dict | None = None
    message: str | None = None
