"""Integration tests for the Connections API endpoints.

All tests run against a real PostgreSQL database via testcontainers.
"""

import uuid

import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.asyncio


# ── CRUD ─────────────────────────────────────────────────────────────


async def test_create_connection(client: AsyncClient) -> None:
    resp = await client.post("/api/connections", json={
        "name": "prod-db",
        "connection_type": "database",
        "host": "db.example.com",
        "port": 5432,
        "description": "Production database",
        "extra": {"ssl": True},
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "prod-db"
    assert body["connection_type"] == "database"
    assert body["host"] == "db.example.com"
    assert body["port"] == 5432
    assert body["extra"] == {"ssl": True}


async def test_list_connections_empty(client: AsyncClient) -> None:
    resp = await client.get("/api/connections")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


async def test_list_connections_filter_by_type(client: AsyncClient) -> None:
    await client.post("/api/connections", json={"name": "conn-db", "connection_type": "database"})
    await client.post("/api/connections", json={"name": "conn-sftp", "connection_type": "sftp"})

    resp = await client.get("/api/connections", params={"connection_type": "database"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["connection_type"] == "database"


async def test_get_connection(client: AsyncClient) -> None:
    create_resp = await client.post("/api/connections", json={
        "name": "conn-get",
        "connection_type": "rest_api",
        "host": "https://api.example.com",
    })
    conn_id = create_resp.json()["id"]

    resp = await client.get(f"/api/connections/{conn_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "conn-get"


async def test_update_connection(client: AsyncClient) -> None:
    create_resp = await client.post("/api/connections", json={
        "name": "conn-update",
        "connection_type": "sftp",
    })
    conn_id = create_resp.json()["id"]

    resp = await client.patch(f"/api/connections/{conn_id}", json={
        "host": "sftp.new.com",
        "port": 22,
    })
    assert resp.status_code == 200
    assert resp.json()["host"] == "sftp.new.com"
    assert resp.json()["port"] == 22


async def test_delete_connection(client: AsyncClient) -> None:
    create_resp = await client.post("/api/connections", json={
        "name": "conn-delete",
        "connection_type": "custom",
    })
    conn_id = create_resp.json()["id"]

    resp = await client.delete(f"/api/connections/{conn_id}")
    assert resp.status_code == 204

    get_resp = await client.get(f"/api/connections/{conn_id}")
    assert get_resp.status_code == 404


# ── Edge cases ───────────────────────────────────────────────────────


async def test_get_connection_not_found(client: AsyncClient) -> None:
    resp = await client.get(f"/api/connections/{uuid.uuid4()}")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Connection not found"


async def test_update_connection_not_found(client: AsyncClient) -> None:
    resp = await client.patch(f"/api/connections/{uuid.uuid4()}", json={"host": "x"})
    assert resp.status_code == 404


async def test_delete_connection_not_found(client: AsyncClient) -> None:
    resp = await client.delete(f"/api/connections/{uuid.uuid4()}")
    assert resp.status_code == 404


async def test_create_duplicate_connection_name(client: AsyncClient) -> None:
    await client.post("/api/connections", json={"name": "conn-dup", "connection_type": "database"})
    resp = await client.post("/api/connections", json={"name": "conn-dup", "connection_type": "sftp"})
    assert resp.status_code == 409


async def test_all_connection_types(client: AsyncClient) -> None:
    """Verify that all defined connection types can be created."""
    types = ["database", "rest_api", "sftp", "azure_blob", "azure_servicebus", "azure_eventhub", "custom"]
    for ct in types:
        resp = await client.post("/api/connections", json={
            "name": f"conn-type-{ct}",
            "connection_type": ct,
        })
        assert resp.status_code == 201, f"Failed to create connection_type={ct}"
