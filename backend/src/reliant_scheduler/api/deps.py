"""Shared API dependencies."""

from fastapi import Header, HTTPException, status

from reliant_scheduler.core.config import settings

API_KEY_HEADER = "X-API-Key"


async def verify_api_key(x_api_key: str = Header(alias=API_KEY_HEADER, default="")) -> str:
    """API key authentication. In dev mode (no key configured), all requests pass."""
    if not settings.api_key:
        return "dev"
    if x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
    return x_api_key
