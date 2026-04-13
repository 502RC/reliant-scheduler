"""Integration tests for the Environments API endpoints.

All tests run against a real PostgreSQL database via testcontainers.
"""

import uuid

import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.asyncio


# ── CRUD ─────────────────────────────────────────────────────────────


async def test_create_environment(client: AsyncClient) -> None:
    resp = await client.post("/api/environments", json={
        "name": "staging",
        "description": "Staging environment",
        "variables": {"REGION": "eastus2"},
        "is_production": False,
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "staging"
    assert body["variables"] == {"REGION": "eastus2"}
    assert body["is_production"] is False
    assert "id" in body
    assert "created_at" in body


async def test_list_environments_empty(client: AsyncClient) -> None:
    resp = await client.get("/api/environments")
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert body["total"] == 0
    assert body["page"] == 1


async def test_list_environments_with_data(client: AsyncClient) -> None:
    await client.post("/api/environments", json={"name": "env-list-1"})
    await client.post("/api/environments", json={"name": "env-list-2", "is_production": True})
    resp = await client.get("/api/environments")
    assert resp.status_code == 200
    assert resp.json()["total"] == 2


async def test_list_environments_filter_is_production(client: AsyncClient) -> None:
    await client.post("/api/environments", json={"name": "env-prod", "is_production": True})
    await client.post("/api/environments", json={"name": "env-dev", "is_production": False})

    resp = await client.get("/api/environments", params={"is_production": "true"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "env-prod"


async def test_get_environment(client: AsyncClient) -> None:
    create_resp = await client.post("/api/environments", json={"name": "env-get-test"})
    env_id = create_resp.json()["id"]

    resp = await client.get(f"/api/environments/{env_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "env-get-test"


async def test_update_environment(client: AsyncClient) -> None:
    create_resp = await client.post("/api/environments", json={"name": "env-update"})
    env_id = create_resp.json()["id"]

    resp = await client.patch(f"/api/environments/{env_id}", json={
        "description": "Updated description",
        "is_production": True,
    })
    assert resp.status_code == 200
    assert resp.json()["description"] == "Updated description"
    assert resp.json()["is_production"] is True


async def test_delete_environment(client: AsyncClient) -> None:
    create_resp = await client.post("/api/environments", json={"name": "env-delete"})
    env_id = create_resp.json()["id"]

    resp = await client.delete(f"/api/environments/{env_id}")
    assert resp.status_code == 204

    get_resp = await client.get(f"/api/environments/{env_id}")
    assert get_resp.status_code == 404


# ── Edge cases ───────────────────────────────────────────────────────


async def test_get_environment_not_found(client: AsyncClient) -> None:
    resp = await client.get(f"/api/environments/{uuid.uuid4()}")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Environment not found"


async def test_update_environment_not_found(client: AsyncClient) -> None:
    resp = await client.patch(f"/api/environments/{uuid.uuid4()}", json={"name": "x"})
    assert resp.status_code == 404


async def test_delete_environment_not_found(client: AsyncClient) -> None:
    resp = await client.delete(f"/api/environments/{uuid.uuid4()}")
    assert resp.status_code == 404


async def test_create_duplicate_environment_name(client: AsyncClient) -> None:
    await client.post("/api/environments", json={"name": "env-dup"})
    resp = await client.post("/api/environments", json={"name": "env-dup"})
    assert resp.status_code == 409


async def test_pagination(client: AsyncClient) -> None:
    for i in range(5):
        await client.post("/api/environments", json={"name": f"env-page-{i}"})

    resp = await client.get("/api/environments", params={"page": 1, "page_size": 2})
    body = resp.json()
    assert len(body["items"]) == 2
    assert body["total"] == 5
    assert body["pages"] == 3
