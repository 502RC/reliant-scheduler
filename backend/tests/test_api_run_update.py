"""Integration tests for PATCH /api/jobs/{job_id}/runs/{run_id} endpoint.

Uses real PostgreSQL via testcontainers — no mocks.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from reliant_scheduler.models.job import Job
from reliant_scheduler.models.job_run import JobRun, RunStatus


async def _seed_job_and_run(
    session: AsyncSession,
    *,
    run_status: RunStatus = RunStatus.RUNNING,
    max_retries: int = 0,
) -> tuple[Job, JobRun]:
    """Insert a job and a run for testing."""
    job = Job(
        name=f"api-test-{uuid.uuid4().hex[:8]}",
        job_type="shell",
        command='echo "test"',
        max_retries=max_retries,
        timeout_seconds=60,
    )
    session.add(job)
    await session.flush()

    run = JobRun(
        job_id=job.id,
        status=run_status,
        triggered_by="manual",
        attempt_number=1,
    )
    session.add(run)
    await session.flush()
    await session.commit()
    return job, run


@pytest.mark.asyncio
async def test_update_run_success(client: AsyncClient, db_session: AsyncSession) -> None:
    """PATCH should update run status and fields."""
    job, run = await _seed_job_and_run(db_session)

    resp = await client.patch(
        f"/api/jobs/{job.id}/runs/{run.id}",
        json={
            "status": "success",
            "exit_code": 0,
            "log_url": "file:///tmp/test.log",
            "metrics": {"duration_seconds": 1.5},
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["exit_code"] == 0
    assert data["log_url"] == "file:///tmp/test.log"
    assert data["finished_at"] is not None
    assert data["metrics"]["duration_seconds"] == 1.5


@pytest.mark.asyncio
async def test_update_run_failed_triggers_retry(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """PATCH to failed status should trigger retry when max_retries > 0."""
    job, run = await _seed_job_and_run(db_session, max_retries=2)

    resp = await client.patch(
        f"/api/jobs/{job.id}/runs/{run.id}",
        json={
            "status": "failed",
            "exit_code": 1,
            "error_message": "segfault",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "failed"

    # Check retry run was created
    list_resp = await client.get(f"/api/jobs/{job.id}/runs")
    assert list_resp.status_code == 200
    runs = list_resp.json()["items"]
    assert len(runs) == 2
    retry = [r for r in runs if r["attempt_number"] == 2]
    assert len(retry) == 1
    assert retry[0]["status"] == "pending"
    assert retry[0]["triggered_by"] == "retry"


@pytest.mark.asyncio
async def test_update_run_not_found(client: AsyncClient, db_session: AsyncSession) -> None:
    """PATCH with non-existent IDs should return 404."""
    fake_id = uuid.uuid4()
    resp = await client.patch(
        f"/api/jobs/{fake_id}/runs/{fake_id}",
        json={"status": "success"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_run_invalid_status(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """PATCH with invalid status should return 422."""
    job, run = await _seed_job_and_run(db_session)

    resp = await client.patch(
        f"/api/jobs/{job.id}/runs/{run.id}",
        json={"status": "invalid_status"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_run_sets_finished_at_on_terminal(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """finished_at should be auto-populated for terminal statuses."""
    job, run = await _seed_job_and_run(db_session)

    resp = await client.patch(
        f"/api/jobs/{job.id}/runs/{run.id}",
        json={"status": "timed_out", "error_message": "Timed out after 60s"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["finished_at"] is not None
    assert data["status"] == "timed_out"


@pytest.mark.asyncio
async def test_update_run_partial_update(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """PATCH should allow partial updates (only specified fields change)."""
    job, run = await _seed_job_and_run(db_session)

    resp = await client.patch(
        f"/api/jobs/{job.id}/runs/{run.id}",
        json={"status": "running"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "running"
    # Fields not in the payload should remain unchanged
    assert data["exit_code"] is None
    assert data["log_url"] is None
