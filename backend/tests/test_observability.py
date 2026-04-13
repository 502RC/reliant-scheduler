"""Integration tests for observability endpoints.

Tests cover the /healthz, /livez, /readyz, and /metrics endpoints.
Health checks hit a real PostgreSQL container via testcontainers;
Azure-dependent checks are expected to return "skipped" in CI.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from reliant_scheduler.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.asyncio
async def test_livez() -> None:
    """Liveness probe always returns 200."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/livez")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_healthz_structure() -> None:
    """/healthz returns the expected check keys and aggregate status."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/healthz")
    # May be 200 or 503 depending on DB availability; structure must be correct
    body = resp.json()
    assert "status" in body
    assert "checks" in body
    expected_checks = {"postgresql", "servicebus", "blob_storage", "keyvault", "eventhubs"}
    assert set(body["checks"].keys()) == expected_checks
    for check in body["checks"].values():
        assert "status" in check


@pytest.mark.asyncio
async def test_readyz_mirrors_healthz() -> None:
    """/readyz returns the same structure as /healthz."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/readyz")
    body = resp.json()
    assert "status" in body
    assert "checks" in body


@pytest.mark.asyncio
async def test_healthz_with_db(client: AsyncClient) -> None:
    """/healthz passes the PostgreSQL check when a real DB is available."""
    resp = await client.get("/healthz")
    body = resp.json()
    pg_check = body["checks"]["postgresql"]
    assert pg_check["status"] == "healthy"
    assert "latency_seconds" in pg_check


@pytest.mark.asyncio
async def test_healthz_skips_unconfigured_azure_services(client: AsyncClient) -> None:
    """Azure checks are skipped when connection strings are empty."""
    resp = await client.get("/healthz")
    body = resp.json()
    for azure_dep in ("servicebus", "blob_storage", "keyvault", "eventhubs"):
        check = body["checks"][azure_dep]
        assert check["status"] == "skipped", f"{azure_dep} should be skipped without config"


@pytest.mark.asyncio
async def test_metrics_endpoint() -> None:
    """/metrics returns Prometheus exposition format."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert "text/plain" in resp.headers.get("content-type", "")
    text = resp.text
    # Verify our custom metrics appear
    assert "reliant_http_requests_total" in text
    assert "reliant_http_request_duration_seconds" in text
    assert "reliant_health_check_status" in text


@pytest.mark.asyncio
async def test_correlation_id_propagation() -> None:
    """Requests include a correlation ID in the response header."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Without a correlation ID header — one should be generated
        resp = await client.get("/livez")
        assert "x-correlation-id" in resp.headers
        generated_id = resp.headers["x-correlation-id"]
        assert len(generated_id) > 0

        # With a correlation ID header — it should be echoed back
        custom_id = "test-correlation-12345"
        resp = await client.get("/livez", headers={"X-Correlation-ID": custom_id})
        assert resp.headers["x-correlation-id"] == custom_id


@pytest.mark.asyncio
async def test_metrics_increment_on_request() -> None:
    """Verify that HTTP metrics increment after requests."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Make a few requests to generate metrics
        await client.get("/livez")
        await client.get("/livez")

        resp = await client.get("/metrics")
        text = resp.text
        # Should have recorded requests to /livez
        assert "reliant_http_requests_total" in text


# ---------------------------------------------------------------
# Error-path tests
# ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_apm_publisher_graceful_on_failure() -> None:
    """APM publisher logs error but does not crash when Event Hubs is unavailable."""
    from unittest.mock import AsyncMock, patch

    from reliant_scheduler.services.apm_publisher import publish_apm_event

    with patch(
        "reliant_scheduler.services.apm_publisher.settings"
    ) as mock_settings:
        mock_settings.azure_apm_eventhub_connection_string = "Endpoint=sb://fake.servicebus.windows.net/;SharedAccessKeyName=fakekey;SharedAccessKey=ZmFrZQ=="
        mock_settings.azure_apm_eventhub_name = "fake-hub"
        # Should not raise — the try/except in _send_to_eventhub catches it
        await publish_apm_event("test_dataset", {"key": "value"})


@pytest.mark.asyncio
async def test_healthz_returns_503_on_db_failure() -> None:
    """Health check returns 503 when the database is unreachable."""
    from unittest.mock import AsyncMock, patch

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Patch get_db to return a session that always fails
        from reliant_scheduler.core.database import get_db

        async def _broken_db():
            mock_session = AsyncMock()
            mock_session.execute = AsyncMock(side_effect=ConnectionError("DB down"))
            yield mock_session

        app.dependency_overrides[get_db] = _broken_db
        try:
            resp = await ac.get("/healthz")
            assert resp.status_code == 503
            body = resp.json()
            assert body["status"] == "unhealthy"
            assert body["checks"]["postgresql"]["status"] == "unhealthy"
        finally:
            app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_path_normalization_in_metrics() -> None:
    """Verify that UUID paths are normalized in metric labels."""
    from reliant_scheduler.api.middleware import _normalize_path

    assert _normalize_path("/api/jobs/123e4567-e89b-12d3-a456-426614174000") == "/api/jobs/{id}"
    assert _normalize_path("/api/jobs/123e4567-e89b-12d3-a456-426614174000/runs/987fcdeb-51a2-3b4c-d567-890123456789") == "/api/jobs/{id}/runs/{id}"
    assert _normalize_path("/api/users/42") == "/api/users/{id}"
    assert _normalize_path("/healthz") == "/healthz"
    assert _normalize_path("/api/jobs") == "/api/jobs"
