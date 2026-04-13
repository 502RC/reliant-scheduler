"""Integration tests for API authentication middleware.

Tests the X-API-Key header validation in both dev mode (no key configured)
and production mode (key required).
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from reliant_scheduler.core.config import settings
from reliant_scheduler.core.database import get_db
from reliant_scheduler.main import app


pytestmark = pytest.mark.asyncio


# ── Dev mode (no API key configured) ────────────────────────────────


async def test_dev_mode_no_key_required(client: AsyncClient) -> None:
    """When api_key is empty, requests without a key should succeed."""
    assert settings.api_key == ""
    resp = await client.get("/api/jobs")
    assert resp.status_code == 200


async def test_dev_mode_any_key_accepted(client: AsyncClient) -> None:
    """In dev mode, even an arbitrary key header is accepted."""
    resp = await client.get("/api/jobs", headers={"X-API-Key": "anything"})
    assert resp.status_code == 200


# ── Production mode (API key configured) ─────────────────────────────


@pytest_asyncio.fixture
async def prod_client(db_session: AsyncSession):
    """Client with API key enforcement enabled."""
    original_key = settings.api_key
    settings.api_key = "test-secret-key-12345"

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
    settings.api_key = original_key
    app.dependency_overrides.clear()


async def test_prod_mode_valid_key(prod_client: AsyncClient) -> None:
    resp = await prod_client.get(
        "/api/jobs",
        headers={"X-API-Key": "test-secret-key-12345"},
    )
    assert resp.status_code == 200


async def test_prod_mode_missing_key(prod_client: AsyncClient) -> None:
    resp = await prod_client.get("/api/jobs")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid or missing API key"


async def test_prod_mode_invalid_key(prod_client: AsyncClient) -> None:
    resp = await prod_client.get(
        "/api/jobs",
        headers={"X-API-Key": "wrong-key"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid or missing API key"


async def test_health_endpoint_no_auth_required(prod_client: AsyncClient) -> None:
    """The /healthz endpoint is public and should not require auth."""
    resp = await prod_client.get("/healthz")
    # 200 (healthy) or 503 (unhealthy) are both acceptable — not 401
    assert resp.status_code in (200, 503)
    body = resp.json()
    assert "status" in body
    assert "checks" in body


async def test_auth_applies_to_all_protected_routes(prod_client: AsyncClient) -> None:
    """All API resource endpoints should reject unauthenticated requests."""
    endpoints = [
        "/api/jobs",
        "/api/schedules",
        "/api/connections",
        "/api/environments",
        "/api/agents",
    ]
    for endpoint in endpoints:
        resp = await prod_client.get(endpoint)
        assert resp.status_code == 401, f"{endpoint} did not require auth"
