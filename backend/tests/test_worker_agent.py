"""Integration tests for the worker agent runtime.

Uses real PostgreSQL via testcontainers — no mocks.
Tests the end-to-end flow: create job → create run → worker processes
message → run status updated → logs stored.
"""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reliant_scheduler.models.agent import Agent, AgentStatus
from reliant_scheduler.models.job import Job
from reliant_scheduler.models.job_run import JobRun, RunStatus
from reliant_scheduler.services.job_queue import JobMessage
from reliant_scheduler.workers.agent import WorkerAgent


async def _create_job(
    session: AsyncSession,
    *,
    name: str = "test-job",
    command: str = 'echo "hello"',
    max_retries: int = 0,
    timeout_seconds: int = 30,
) -> Job:
    """Helper to insert a job."""
    job = Job(
        name=name,
        job_type="shell",
        command=command,
        max_retries=max_retries,
        timeout_seconds=timeout_seconds,
    )
    session.add(job)
    await session.flush()
    return job


async def _create_run(
    session: AsyncSession,
    job: Job,
    *,
    status: RunStatus = RunStatus.QUEUED,
    attempt_number: int = 1,
) -> JobRun:
    """Helper to insert a run."""
    run = JobRun(
        job_id=job.id,
        status=status,
        triggered_by="manual",
        attempt_number=attempt_number,
    )
    session.add(run)
    await session.flush()
    return run


@pytest.mark.asyncio
async def test_worker_registers_agent(db_session: AsyncSession) -> None:
    """WorkerAgent._register creates an ONLINE agent record."""
    worker = WorkerAgent(hostname="test-host-register")
    agent_id = await worker._register(db_session)
    await db_session.commit()

    result = await db_session.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one()
    assert agent.status == AgentStatus.ONLINE
    assert agent.hostname == "test-host-register"
    assert agent.last_heartbeat_at is not None


@pytest.mark.asyncio
async def test_worker_re_registers_existing_agent(db_session: AsyncSession) -> None:
    """Re-registering an existing hostname should update, not duplicate."""
    worker = WorkerAgent(hostname="test-host-reregister", max_concurrent_jobs=2)

    id1 = await worker._register(db_session)
    await db_session.commit()

    worker2 = WorkerAgent(hostname="test-host-reregister", max_concurrent_jobs=8)
    id2 = await worker2._register(db_session)
    await db_session.commit()

    assert id1 == id2
    result = await db_session.execute(select(Agent).where(Agent.id == id1))
    agent = result.scalar_one()
    assert agent.max_concurrent_jobs == 8


@pytest.mark.asyncio
async def test_worker_processes_successful_job(
    db_session: AsyncSession, test_session_factory
) -> None:
    """End-to-end: worker executes a successful command and updates the run."""
    job = await _create_job(db_session, command='echo "integration test output"')
    run = await _create_run(db_session, job)
    await db_session.commit()

    worker = WorkerAgent(hostname="test-host-success")
    worker._session_factory = test_session_factory
    worker.agent_id = (await worker._register(db_session))
    await db_session.commit()

    message = JobMessage(
        run_id=str(run.id),
        job_id=str(job.id),
        job_name=job.name,
        command=job.command,
        parameters=None,
        attempt_number=1,
        timeout_seconds=job.timeout_seconds,
    )
    await worker._process_message(message)

    # Refresh the run from the DB using a new session
    async with test_session_factory() as fresh_session:
        result = await fresh_session.execute(
            select(JobRun).where(JobRun.id == run.id)
        )
        updated_run = result.scalar_one()
        assert updated_run.status == RunStatus.SUCCESS
        assert updated_run.exit_code == 0
        assert updated_run.started_at is not None
        assert updated_run.finished_at is not None
        assert updated_run.log_url is not None
        assert updated_run.agent_id == worker.agent_id
        assert updated_run.metrics is not None
        assert updated_run.metrics["duration_seconds"] >= 0


@pytest.mark.asyncio
async def test_worker_processes_failed_job(
    db_session: AsyncSession, test_session_factory
) -> None:
    """A failing command should set status to FAILED with error info."""
    job = await _create_job(db_session, command="exit 1")
    run = await _create_run(db_session, job)
    await db_session.commit()

    worker = WorkerAgent(hostname="test-host-fail")
    worker._session_factory = test_session_factory
    worker.agent_id = (await worker._register(db_session))
    await db_session.commit()

    message = JobMessage(
        run_id=str(run.id),
        job_id=str(job.id),
        job_name=job.name,
        command=job.command,
        parameters=None,
        attempt_number=1,
        timeout_seconds=30,
    )
    await worker._process_message(message)

    async with test_session_factory() as fresh_session:
        result = await fresh_session.execute(
            select(JobRun).where(JobRun.id == run.id)
        )
        updated_run = result.scalar_one()
        assert updated_run.status == RunStatus.FAILED
        assert updated_run.exit_code == 1
        assert updated_run.error_message is not None


@pytest.mark.asyncio
async def test_worker_processes_timed_out_job(
    db_session: AsyncSession, test_session_factory
) -> None:
    """A command exceeding the timeout should be killed and marked TIMED_OUT."""
    job = await _create_job(
        db_session, command="sleep 60", timeout_seconds=1
    )
    run = await _create_run(db_session, job)
    await db_session.commit()

    worker = WorkerAgent(hostname="test-host-timeout")
    worker._session_factory = test_session_factory
    worker.agent_id = (await worker._register(db_session))
    await db_session.commit()

    message = JobMessage(
        run_id=str(run.id),
        job_id=str(job.id),
        job_name=job.name,
        command=job.command,
        parameters=None,
        attempt_number=1,
        timeout_seconds=1,
    )
    await worker._process_message(message)

    async with test_session_factory() as fresh_session:
        result = await fresh_session.execute(
            select(JobRun).where(JobRun.id == run.id)
        )
        updated_run = result.scalar_one()
        assert updated_run.status == RunStatus.TIMED_OUT
        assert "timeout" in (updated_run.error_message or "").lower()


@pytest.mark.asyncio
async def test_worker_triggers_retry_on_failure(
    db_session: AsyncSession, test_session_factory
) -> None:
    """A failed job with max_retries > 0 should create a retry run."""
    job = await _create_job(db_session, command="exit 1", max_retries=2)
    run = await _create_run(db_session, job, attempt_number=1)
    await db_session.commit()

    worker = WorkerAgent(hostname="test-host-retry")
    worker._session_factory = test_session_factory
    worker.agent_id = (await worker._register(db_session))
    await db_session.commit()

    message = JobMessage(
        run_id=str(run.id),
        job_id=str(job.id),
        job_name=job.name,
        command=job.command,
        parameters=None,
        attempt_number=1,
        timeout_seconds=30,
    )
    await worker._process_message(message)

    # Check that a retry run was created
    async with test_session_factory() as fresh_session:
        result = await fresh_session.execute(
            select(JobRun)
            .where(JobRun.job_id == job.id, JobRun.attempt_number == 2)
        )
        retry_run = result.scalar_one_or_none()
        assert retry_run is not None
        assert retry_run.status == RunStatus.PENDING
        assert retry_run.triggered_by == "retry"


@pytest.mark.asyncio
async def test_worker_no_retry_when_exhausted(
    db_session: AsyncSession, test_session_factory
) -> None:
    """When max_retries is exhausted, no retry run should be created."""
    job = await _create_job(db_session, command="exit 1", max_retries=1)
    run = await _create_run(db_session, job, attempt_number=2)
    await db_session.commit()

    worker = WorkerAgent(hostname="test-host-noretry")
    worker._session_factory = test_session_factory
    worker.agent_id = (await worker._register(db_session))
    await db_session.commit()

    message = JobMessage(
        run_id=str(run.id),
        job_id=str(job.id),
        job_name=job.name,
        command=job.command,
        parameters=None,
        attempt_number=2,
        timeout_seconds=30,
    )
    await worker._process_message(message)

    async with test_session_factory() as fresh_session:
        result = await fresh_session.execute(
            select(JobRun)
            .where(JobRun.job_id == job.id, JobRun.attempt_number == 3)
        )
        retry_run = result.scalar_one_or_none()
        assert retry_run is None


@pytest.mark.asyncio
async def test_worker_handles_no_command(
    db_session: AsyncSession, test_session_factory
) -> None:
    """A job with no command should complete with exit code 0."""
    job = await _create_job(db_session, command=None)
    # Fix: command is None
    job.command = None
    await db_session.flush()

    run = await _create_run(db_session, job)
    await db_session.commit()

    worker = WorkerAgent(hostname="test-host-nocmd")
    worker._session_factory = test_session_factory
    worker.agent_id = (await worker._register(db_session))
    await db_session.commit()

    message = JobMessage(
        run_id=str(run.id),
        job_id=str(job.id),
        job_name=job.name,
        command=None,
        parameters=None,
        attempt_number=1,
        timeout_seconds=30,
    )
    await worker._process_message(message)

    async with test_session_factory() as fresh_session:
        result = await fresh_session.execute(
            select(JobRun).where(JobRun.id == run.id)
        )
        updated_run = result.scalar_one()
        assert updated_run.status == RunStatus.SUCCESS
        assert updated_run.exit_code == 0
