"""Integration tests for the Agents API endpoints.

All tests run against a real PostgreSQL database via testcontainers.
"""

import uuid

import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.asyncio


# ── Registration & CRUD ──────────────────────────────────────────────


async def test_register_agent(client: AsyncClient) -> None:
    resp = await client.post("/api/agents/register", json={
        "hostname": "worker-01",
        "labels": {"zone": "eastus2"},
        "max_concurrent_jobs": 8,
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["hostname"] == "worker-01"
    assert body["status"] == "online"
    assert body["labels"] == {"zone": "eastus2"}
    assert body["max_concurrent_jobs"] == 8
    assert body["last_heartbeat_at"] is not None


async def test_register_agent_idempotent(client: AsyncClient) -> None:
    """Re-registering with the same hostname updates the existing agent."""
    resp1 = await client.post("/api/agents/register", json={
        "hostname": "worker-idem",
        "max_concurrent_jobs": 4,
    })
    agent_id = resp1.json()["id"]

    resp2 = await client.post("/api/agents/register", json={
        "hostname": "worker-idem",
        "max_concurrent_jobs": 16,
    })
    assert resp2.status_code == 201
    assert resp2.json()["id"] == agent_id
    assert resp2.json()["max_concurrent_jobs"] == 16


async def test_list_agents_empty(client: AsyncClient) -> None:
    resp = await client.get("/api/agents")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


async def test_list_agents_filter_by_status(client: AsyncClient) -> None:
    await client.post("/api/agents/register", json={"hostname": "worker-online"})

    resp = await client.get("/api/agents", params={"status": "online"})
    assert resp.status_code == 200
    assert resp.json()["total"] == 1

    resp = await client.get("/api/agents", params={"status": "offline"})
    assert resp.json()["total"] == 0


async def test_get_agent(client: AsyncClient) -> None:
    create_resp = await client.post("/api/agents/register", json={"hostname": "worker-get"})
    agent_id = create_resp.json()["id"]

    resp = await client.get(f"/api/agents/{agent_id}")
    assert resp.status_code == 200
    assert resp.json()["hostname"] == "worker-get"


async def test_get_agent_not_found(client: AsyncClient) -> None:
    resp = await client.get(f"/api/agents/{uuid.uuid4()}")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Agent not found"


# ── Heartbeat ────────────────────────────────────────────────────────


async def test_heartbeat(client: AsyncClient) -> None:
    create_resp = await client.post("/api/agents/register", json={"hostname": "worker-hb"})
    agent_id = create_resp.json()["id"]

    resp = await client.post(f"/api/agents/{agent_id}/heartbeat")
    assert resp.status_code == 204

    get_resp = await client.get(f"/api/agents/{agent_id}")
    assert get_resp.json()["status"] == "online"
