"""Integration tests for the Schedules API endpoints.

All tests run against a real PostgreSQL database via testcontainers.
"""

import uuid

import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.asyncio


async def _create_job(client: AsyncClient, name: str) -> str:
    """Helper: create a job and return its ID."""
    resp = await client.post("/api/jobs", json={
        "name": name,
        "job_type": "shell",
        "command": "echo test",
    })
    assert resp.status_code == 201
    return resp.json()["id"]


# ── CRUD ─────────────────────────────────────────────────────────────


async def test_create_cron_schedule(client: AsyncClient) -> None:
    job_id = await _create_job(client, "sched-cron-job")
    resp = await client.post("/api/schedules", json={
        "job_id": job_id,
        "trigger_type": "cron",
        "cron_expression": "0 */6 * * *",
        "timezone": "America/New_York",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["trigger_type"] == "cron"
    assert body["cron_expression"] == "0 */6 * * *"
    assert body["timezone"] == "America/New_York"
    assert body["enabled"] is True
    assert body["next_run_at"] is not None


async def test_create_event_schedule(client: AsyncClient) -> None:
    job_id = await _create_job(client, "sched-event-job")
    resp = await client.post("/api/schedules", json={
        "job_id": job_id,
        "trigger_type": "event",
        "event_source": "blob_storage",
        "event_filter": {"container": "uploads"},
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["trigger_type"] == "event"
    assert body["event_source"] == "blob_storage"
    assert body["event_filter"] == {"container": "uploads"}


async def test_create_manual_schedule(client: AsyncClient) -> None:
    job_id = await _create_job(client, "sched-manual-job")
    resp = await client.post("/api/schedules", json={
        "job_id": job_id,
        "trigger_type": "manual",
    })
    assert resp.status_code == 201
    assert resp.json()["trigger_type"] == "manual"


async def test_list_schedules_empty(client: AsyncClient) -> None:
    resp = await client.get("/api/schedules")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


async def test_list_schedules_filter_by_trigger_type(client: AsyncClient) -> None:
    job1_id = await _create_job(client, "sched-filter-1")
    job2_id = await _create_job(client, "sched-filter-2")
    await client.post("/api/schedules", json={
        "job_id": job1_id, "trigger_type": "cron", "cron_expression": "0 0 * * *",
    })
    await client.post("/api/schedules", json={
        "job_id": job2_id, "trigger_type": "event", "event_source": "test",
    })

    resp = await client.get("/api/schedules", params={"trigger_type": "cron"})
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["trigger_type"] == "cron"


async def test_list_schedules_filter_by_enabled(client: AsyncClient) -> None:
    job_id = await _create_job(client, "sched-enabled-filter")
    create_resp = await client.post("/api/schedules", json={
        "job_id": job_id, "trigger_type": "manual", "enabled": False,
    })
    assert create_resp.status_code == 201

    resp = await client.get("/api/schedules", params={"enabled": "false"})
    assert resp.json()["total"] == 1

    resp = await client.get("/api/schedules", params={"enabled": "true"})
    assert resp.json()["total"] == 0


async def test_get_schedule(client: AsyncClient) -> None:
    job_id = await _create_job(client, "sched-get-job")
    create_resp = await client.post("/api/schedules", json={
        "job_id": job_id, "trigger_type": "manual",
    })
    sched_id = create_resp.json()["id"]

    resp = await client.get(f"/api/schedules/{sched_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == sched_id


async def test_update_schedule(client: AsyncClient) -> None:
    job_id = await _create_job(client, "sched-update-job")
    create_resp = await client.post("/api/schedules", json={
        "job_id": job_id, "trigger_type": "manual",
    })
    sched_id = create_resp.json()["id"]

    resp = await client.patch(f"/api/schedules/{sched_id}", json={
        "enabled": False,
    })
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False


async def test_delete_schedule(client: AsyncClient) -> None:
    job_id = await _create_job(client, "sched-delete-job")
    create_resp = await client.post("/api/schedules", json={
        "job_id": job_id, "trigger_type": "manual",
    })
    sched_id = create_resp.json()["id"]

    resp = await client.delete(f"/api/schedules/{sched_id}")
    assert resp.status_code == 204

    get_resp = await client.get(f"/api/schedules/{sched_id}")
    assert get_resp.status_code == 404


# ── Edge cases ───────────────────────────────────────────────────────


async def test_get_schedule_not_found(client: AsyncClient) -> None:
    resp = await client.get(f"/api/schedules/{uuid.uuid4()}")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Schedule not found"


async def test_update_schedule_not_found(client: AsyncClient) -> None:
    resp = await client.patch(f"/api/schedules/{uuid.uuid4()}", json={"enabled": False})
    assert resp.status_code == 404


async def test_delete_schedule_not_found(client: AsyncClient) -> None:
    resp = await client.delete(f"/api/schedules/{uuid.uuid4()}")
    assert resp.status_code == 404


async def test_create_cron_schedule_invalid_expression(client: AsyncClient) -> None:
    job_id = await _create_job(client, "sched-bad-cron")
    resp = await client.post("/api/schedules", json={
        "job_id": job_id,
        "trigger_type": "cron",
        "cron_expression": "not a cron",
    })
    assert resp.status_code == 422


async def test_create_cron_schedule_missing_expression(client: AsyncClient) -> None:
    job_id = await _create_job(client, "sched-no-cron")
    resp = await client.post("/api/schedules", json={
        "job_id": job_id,
        "trigger_type": "cron",
    })
    assert resp.status_code == 422


async def test_duplicate_schedule_for_same_job(client: AsyncClient) -> None:
    """A job can only have one schedule (unique constraint on job_id)."""
    job_id = await _create_job(client, "sched-dup-job")
    resp1 = await client.post("/api/schedules", json={
        "job_id": job_id, "trigger_type": "manual",
    })
    assert resp1.status_code == 201

    resp2 = await client.post("/api/schedules", json={
        "job_id": job_id, "trigger_type": "event", "event_source": "test",
    })
    assert resp2.status_code == 409
