"""Integration tests for the Jobs API endpoints.

All tests run against a real PostgreSQL database via testcontainers.
Covers CRUD, trigger, runs, dependencies, edge cases.
"""

import uuid

import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.asyncio


def _job_payload(name: str = "test-job", **overrides) -> dict:
    base = {
        "name": name,
        "job_type": "shell",
        "command": "echo hello",
        "description": "A test job",
        "parameters": {"key": "value"},
        "max_retries": 2,
        "timeout_seconds": 600,
        "tags": {"team": "platform"},
    }
    base.update(overrides)
    return base


# ── CRUD ─────────────────────────────────────────────────────────────


async def test_create_job(client: AsyncClient) -> None:
    resp = await client.post("/api/jobs", json=_job_payload("job-create"))
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "job-create"
    assert body["job_type"] == "shell"
    assert body["command"] == "echo hello"
    assert body["status"] == "active"
    assert body["max_retries"] == 2
    assert body["timeout_seconds"] == 600
    assert body["tags"] == {"team": "platform"}
    assert "id" in body
    assert "created_at" in body


async def test_list_jobs_empty(client: AsyncClient) -> None:
    resp = await client.get("/api/jobs")
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert body["total"] == 0


async def test_list_jobs_with_data(client: AsyncClient) -> None:
    await client.post("/api/jobs", json=_job_payload("job-list-1"))
    await client.post("/api/jobs", json=_job_payload("job-list-2"))
    resp = await client.get("/api/jobs")
    assert resp.json()["total"] == 2


async def test_list_jobs_filter_by_status(client: AsyncClient) -> None:
    await client.post("/api/jobs", json=_job_payload("job-active"))
    create2 = await client.post("/api/jobs", json=_job_payload("job-paused"))
    job2_id = create2.json()["id"]
    await client.patch(f"/api/jobs/{job2_id}", json={"status": "paused"})

    resp = await client.get("/api/jobs", params={"status": "active"})
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["name"] == "job-active"


async def test_get_job(client: AsyncClient) -> None:
    create_resp = await client.post("/api/jobs", json=_job_payload("job-get"))
    job_id = create_resp.json()["id"]

    resp = await client.get(f"/api/jobs/{job_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "job-get"


async def test_update_job(client: AsyncClient) -> None:
    create_resp = await client.post("/api/jobs", json=_job_payload("job-update"))
    job_id = create_resp.json()["id"]

    resp = await client.patch(f"/api/jobs/{job_id}", json={
        "description": "Updated",
        "max_retries": 5,
        "status": "paused",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["description"] == "Updated"
    assert body["max_retries"] == 5
    assert body["status"] == "paused"


async def test_delete_job(client: AsyncClient) -> None:
    create_resp = await client.post("/api/jobs", json=_job_payload("job-delete"))
    job_id = create_resp.json()["id"]

    resp = await client.delete(f"/api/jobs/{job_id}")
    assert resp.status_code == 204

    get_resp = await client.get(f"/api/jobs/{job_id}")
    assert get_resp.status_code == 404


# ── Trigger & Runs ───────────────────────────────────────────────────


async def test_trigger_job_creates_pending_run(client: AsyncClient) -> None:
    create_resp = await client.post("/api/jobs", json=_job_payload("job-trigger"))
    job_id = create_resp.json()["id"]

    trigger_resp = await client.post(f"/api/jobs/{job_id}/trigger", json={
        "parameters": {"env": "test"},
    })
    assert trigger_resp.status_code == 201
    run = trigger_resp.json()
    assert run["job_id"] == job_id
    assert run["status"] == "pending"
    assert run["triggered_by"] == "manual"
    assert run["parameters"] == {"env": "test"}


async def test_list_job_runs(client: AsyncClient) -> None:
    create_resp = await client.post("/api/jobs", json=_job_payload("job-runs-list"))
    job_id = create_resp.json()["id"]

    await client.post(f"/api/jobs/{job_id}/trigger", json={})
    await client.post(f"/api/jobs/{job_id}/trigger", json={})

    resp = await client.get(f"/api/jobs/{job_id}/runs")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2


async def test_trigger_nonexistent_job(client: AsyncClient) -> None:
    resp = await client.post(f"/api/jobs/{uuid.uuid4()}/trigger", json={})
    assert resp.status_code == 404


# ── Dependencies ─────────────────────────────────────────────────────


async def test_add_and_list_dependency(client: AsyncClient) -> None:
    job_a = (await client.post("/api/jobs", json=_job_payload("dep-parent"))).json()
    job_b = (await client.post("/api/jobs", json=_job_payload("dep-child"))).json()

    resp = await client.post(f"/api/jobs/{job_b['id']}/dependencies", json={
        "depends_on_job_id": job_a["id"],
    })
    assert resp.status_code == 201
    dep = resp.json()
    assert dep["dependent_job_id"] == job_b["id"]
    assert dep["depends_on_job_id"] == job_a["id"]

    list_resp = await client.get(f"/api/jobs/{job_b['id']}/dependencies")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1


async def test_remove_dependency(client: AsyncClient) -> None:
    job_a = (await client.post("/api/jobs", json=_job_payload("dep-rm-a"))).json()
    job_b = (await client.post("/api/jobs", json=_job_payload("dep-rm-b"))).json()

    dep_resp = await client.post(f"/api/jobs/{job_b['id']}/dependencies", json={
        "depends_on_job_id": job_a["id"],
    })
    dep_id = dep_resp.json()["id"]

    del_resp = await client.delete(f"/api/jobs/{job_b['id']}/dependencies/{dep_id}")
    assert del_resp.status_code == 204

    list_resp = await client.get(f"/api/jobs/{job_b['id']}/dependencies")
    assert len(list_resp.json()) == 0


async def test_self_dependency_rejected(client: AsyncClient) -> None:
    job = (await client.post("/api/jobs", json=_job_payload("dep-self"))).json()
    resp = await client.post(f"/api/jobs/{job['id']}/dependencies", json={
        "depends_on_job_id": job["id"],
    })
    assert resp.status_code == 400
    assert "cannot depend on itself" in resp.json()["detail"]


async def test_circular_dependency_rejected(client: AsyncClient) -> None:
    job_a = (await client.post("/api/jobs", json=_job_payload("circ-a"))).json()
    job_b = (await client.post("/api/jobs", json=_job_payload("circ-b"))).json()

    # A depends on B
    resp1 = await client.post(f"/api/jobs/{job_a['id']}/dependencies", json={
        "depends_on_job_id": job_b["id"],
    })
    assert resp1.status_code == 201

    # B depends on A → circular
    resp2 = await client.post(f"/api/jobs/{job_b['id']}/dependencies", json={
        "depends_on_job_id": job_a["id"],
    })
    assert resp2.status_code == 400


async def test_dependency_with_nonexistent_job(client: AsyncClient) -> None:
    job = (await client.post("/api/jobs", json=_job_payload("dep-missing"))).json()
    resp = await client.post(f"/api/jobs/{job['id']}/dependencies", json={
        "depends_on_job_id": str(uuid.uuid4()),
    })
    assert resp.status_code == 404


# ── Edge cases ───────────────────────────────────────────────────────


async def test_get_job_not_found(client: AsyncClient) -> None:
    resp = await client.get(f"/api/jobs/{uuid.uuid4()}")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Job not found"


async def test_update_job_not_found(client: AsyncClient) -> None:
    resp = await client.patch(f"/api/jobs/{uuid.uuid4()}", json={"name": "x"})
    assert resp.status_code == 404


async def test_delete_job_not_found(client: AsyncClient) -> None:
    resp = await client.delete(f"/api/jobs/{uuid.uuid4()}")
    assert resp.status_code == 404


async def test_create_duplicate_job_name(client: AsyncClient) -> None:
    await client.post("/api/jobs", json=_job_payload("job-dup"))
    resp = await client.post("/api/jobs", json=_job_payload("job-dup"))
    assert resp.status_code == 409


async def test_pagination(client: AsyncClient) -> None:
    for i in range(5):
        await client.post("/api/jobs", json=_job_payload(f"job-page-{i}"))

    resp = await client.get("/api/jobs", params={"page": 2, "page_size": 2})
    body = resp.json()
    assert len(body["items"]) == 2
    assert body["total"] == 5
    assert body["pages"] == 3
    assert body["page"] == 2


async def test_create_job_with_environment(client: AsyncClient) -> None:
    env_resp = await client.post("/api/environments", json={"name": "job-env-test"})
    env_id = env_resp.json()["id"]

    resp = await client.post("/api/jobs", json=_job_payload("job-with-env", environment_id=env_id))
    assert resp.status_code == 201
    assert resp.json()["environment_id"] == env_id
