import pytest
from httpx import ASGITransport, AsyncClient

from reliant_scheduler.main import app


@pytest.mark.asyncio
async def test_healthz() -> None:
    """Health endpoint returns structured response with dependency checks."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/healthz")
    # Without a test DB, PostgreSQL will be unhealthy (503), but structure is valid
    assert resp.status_code in (200, 503)
    body = resp.json()
    assert "status" in body
    assert "checks" in body
    assert "postgresql" in body["checks"]


@pytest.mark.asyncio
async def test_livez() -> None:
    """Liveness probe always returns 200."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/livez")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
