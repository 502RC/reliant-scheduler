"""Integration test for the scheduler tick cycle.

Creates a job with a cron schedule, runs the scheduler tick against a real
PostgreSQL database, and verifies that a JobRun is created and enqueued.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reliant_scheduler.models.agent import Agent, AgentStatus
from reliant_scheduler.models.job import Job, JobStatus
from reliant_scheduler.models.job_run import JobRun, RunStatus
from reliant_scheduler.models.schedule import Schedule, TriggerType
from reliant_scheduler.services.scheduler import Scheduler


pytestmark = pytest.mark.asyncio


async def test_scheduler_tick_creates_and_enqueues_run(db_session: AsyncSession) -> None:
    """Full scheduler tick: cron schedule due → pending run created → enqueued."""
    # Create an environment-free job
    job = Job(
        name="tick-test-job",
        job_type="shell",
        command="echo tick",
        status=JobStatus.ACTIVE,
    )
    db_session.add(job)
    await db_session.flush()

    # Create a cron schedule with next_run_at in the past (so it's "due")
    schedule = Schedule(
        job_id=job.id,
        trigger_type=TriggerType.CRON,
        cron_expression="* * * * *",
        timezone="UTC",
        enabled=True,
        next_run_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    db_session.add(schedule)

    # Register an online agent (scheduler logs a warning if none available)
    agent = Agent(
        hostname="tick-test-agent",
        status=AgentStatus.ONLINE,
        last_heartbeat_at=datetime.now(timezone.utc),
    )
    db_session.add(agent)
    await db_session.flush()

    # Run the scheduler tick
    scheduler = Scheduler()
    enqueued = await scheduler.tick(db_session)
    assert enqueued == 1

    # Verify a QUEUED run was created for this job
    result = await db_session.execute(
        select(JobRun).where(JobRun.job_id == job.id)
    )
    runs = list(result.scalars().all())
    assert len(runs) == 1
    assert runs[0].status == RunStatus.QUEUED
    assert runs[0].triggered_by == "schedule"
    assert runs[0].started_at is not None

    # Verify the schedule's next_run_at was advanced past the original due time
    await db_session.refresh(schedule)
    original_due = datetime.now(timezone.utc) - timedelta(minutes=1)
    assert schedule.next_run_at > original_due


async def test_scheduler_tick_respects_dependencies(db_session: AsyncSession) -> None:
    """A pending run should NOT be enqueued if its upstream dependency hasn't succeeded."""
    from reliant_scheduler.models.job import JobDependency

    upstream = Job(name="upstream-job", job_type="shell", command="echo up", status=JobStatus.ACTIVE)
    downstream = Job(name="downstream-job", job_type="shell", command="echo down", status=JobStatus.ACTIVE)
    db_session.add_all([upstream, downstream])
    await db_session.flush()

    # downstream depends on upstream
    dep = JobDependency(dependent_job_id=downstream.id, depends_on_job_id=upstream.id)
    db_session.add(dep)

    # Create a pending run for downstream (simulating a manual trigger)
    pending_run = JobRun(
        job_id=downstream.id,
        status=RunStatus.PENDING,
        triggered_by="manual",
    )
    db_session.add(pending_run)

    agent = Agent(
        hostname="dep-test-agent",
        status=AgentStatus.ONLINE,
        last_heartbeat_at=datetime.now(timezone.utc),
    )
    db_session.add(agent)
    await db_session.flush()

    scheduler = Scheduler()
    enqueued = await scheduler.tick(db_session)
    assert enqueued == 0  # blocked by unsatisfied dependency

    # Now create a successful run for the upstream job
    upstream_run = JobRun(
        job_id=upstream.id,
        status=RunStatus.SUCCESS,
        triggered_by="manual",
    )
    db_session.add(upstream_run)
    await db_session.flush()

    # Tick again — now the downstream run should be enqueued
    enqueued = await scheduler.tick(db_session)
    assert enqueued == 1

    await db_session.refresh(pending_run)
    assert pending_run.status == RunStatus.QUEUED


async def test_scheduler_tick_marks_stale_agents(db_session: AsyncSession) -> None:
    """Agents without a recent heartbeat should be marked offline."""
    stale_agent = Agent(
        hostname="stale-agent",
        status=AgentStatus.ONLINE,
        last_heartbeat_at=datetime.now(timezone.utc) - timedelta(minutes=10),
    )
    fresh_agent = Agent(
        hostname="fresh-agent",
        status=AgentStatus.ONLINE,
        last_heartbeat_at=datetime.now(timezone.utc),
    )
    db_session.add_all([stale_agent, fresh_agent])
    await db_session.flush()

    scheduler = Scheduler()
    await scheduler.tick(db_session)

    await db_session.refresh(stale_agent)
    await db_session.refresh(fresh_agent)
    assert stale_agent.status == AgentStatus.OFFLINE
    assert fresh_agent.status == AgentStatus.ONLINE


async def test_scheduler_handle_event_creates_runs(db_session: AsyncSession) -> None:
    """Event-triggered schedules should create pending runs for matching events."""
    job = Job(name="event-job", job_type="shell", command="echo event", status=JobStatus.ACTIVE)
    db_session.add(job)
    await db_session.flush()

    schedule = Schedule(
        job_id=job.id,
        trigger_type=TriggerType.EVENT,
        event_source="blob_storage",
        event_filter={"container": "uploads"},
        enabled=True,
    )
    db_session.add(schedule)
    await db_session.flush()

    scheduler = Scheduler()

    # Matching event
    created = await scheduler.handle_event(db_session, {"container": "uploads", "file": "data.csv"})
    assert created == 1

    # Non-matching event
    created = await scheduler.handle_event(db_session, {"container": "other"})
    assert created == 0

    result = await db_session.execute(select(JobRun).where(JobRun.job_id == job.id))
    runs = list(result.scalars().all())
    assert len(runs) == 1
    assert runs[0].triggered_by == "event"
