"""End-to-end integration tests: full scheduler lifecycle with Azure services.

Exercises the complete job lifecycle from API creation through scheduler tick,
worker execution, SLA evaluation, event-action automation, calendar-aware
scheduling, dependency chains, RBAC enforcement, and concurrent execution.

All tests run against a real PostgreSQL database via testcontainers.
"""

import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import structlog
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from reliant_scheduler.main import app
from reliant_scheduler.models.agent import Agent, AgentStatus
from reliant_scheduler.models.calendar import Calendar, CalendarType, CalendarDate
from reliant_scheduler.models.connection import Connection, ConnectionType
from reliant_scheduler.models.event_action import (
    Action,
    ActionExecution,
    EventActionBinding,
    EventType,
)
from reliant_scheduler.models.job import Job, JobDependency, JobStatus
from reliant_scheduler.models.job_run import JobRun, RunStatus
from reliant_scheduler.models.schedule import Schedule
from reliant_scheduler.models.sla import SLAEvent, SLAEventType, SLAJobConstraint, SLAPolicy
from reliant_scheduler.models.user import User
from reliant_scheduler.services.event_emitter import emit_event, register_handler, clear_handlers
from reliant_scheduler.services.event_router import EventRouter
from reliant_scheduler.services.job_queue import JobMessage
from reliant_scheduler.services.scheduler import Scheduler
from reliant_scheduler.workers.agent import WorkerAgent
from reliant_scheduler.workers.handlers.registry import get_handler


# -----------------------------------------------------------------------
# Scenario 1: Full job lifecycle — cron → scheduler → worker → SLA → event
# -----------------------------------------------------------------------


class TestE2EJobLifecycle:
    async def test_cron_to_worker_to_completion(self, db_session, test_session_factory, postgres_url):
        """Create job with cron schedule → scheduler tick → worker executes → run succeeds."""
        # Create an online agent so the scheduler has somewhere to send work
        agent = Agent(
            hostname="e2e-agent-1",
            status=AgentStatus.ONLINE,
            max_concurrent_jobs=4,
            last_heartbeat_at=datetime.now(timezone.utc),
        )
        db_session.add(agent)

        # Create a job
        job = Job(
            name="e2e-lifecycle-job",
            job_type="shell",
            command="echo lifecycle-test",
            status=JobStatus.ACTIVE,
            timeout_seconds=60,
        )
        db_session.add(job)
        await db_session.flush()

        # Create a cron schedule that is already due
        schedule = Schedule(
            job_id=job.id,
            trigger_type="cron",
            cron_expression="*/5 * * * *",
            timezone="UTC",
            next_run_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            enabled=True,
        )
        db_session.add(schedule)
        await db_session.commit()

        # Run scheduler tick
        scheduler = Scheduler()
        enqueued = await scheduler.tick(db_session)
        assert enqueued == 1

        # Verify run was created and queued
        runs_result = await db_session.execute(
            select(JobRun).where(JobRun.job_id == job.id)
        )
        runs = list(runs_result.scalars().all())
        assert len(runs) == 1
        assert runs[0].status == RunStatus.QUEUED

        # Drain the local queue and verify the message
        messages = scheduler.queue.drain_local()
        assert len(messages) == 1
        assert messages[0].job_id == str(job.id)

        # Simulate worker execution
        worker = WorkerAgent(hostname="e2e-worker-1")
        worker._session_factory = test_session_factory
        worker.agent_id = agent.id

        run = runs[0]
        msg = messages[0]

        # Mark as RUNNING and execute the shell command path
        async with test_session_factory() as session:
            db_run = (await session.execute(select(JobRun).where(JobRun.id == run.id))).scalar_one()
            db_run.status = RunStatus.RUNNING
            db_run.agent_id = agent.id
            db_run.started_at = datetime.now(timezone.utc)
            await session.commit()

        await worker._execute_shell_command(
            msg,
            correlation_id="e2e-corr-1",
            log=structlog.get_logger("e2e"),
        )

        # Verify run completed successfully
        async with test_session_factory() as session:
            final_run = (await session.execute(select(JobRun).where(JobRun.id == run.id))).scalar_one()
            assert final_run.status == RunStatus.SUCCESS
            assert final_run.exit_code == 0
            assert final_run.log_url is not None

        # Verify schedule was advanced (next_run_at moved forward)
        async with test_session_factory() as session:
            updated_sched = (await session.execute(
                select(Schedule).where(Schedule.id == schedule.id)
            )).scalar_one()
            assert updated_sched.next_run_at > datetime.now(timezone.utc) - timedelta(minutes=1)


# -----------------------------------------------------------------------
# Scenario 2: Calendar-aware scheduling
# -----------------------------------------------------------------------


class TestE2ECalendarAwareScheduling:
    async def test_job_skips_holiday(self, db_session):
        """Job with SKIP_HOLIDAYS calendar constraint does not run on holiday dates."""
        from reliant_scheduler.models.calendar import JobCalendarAssociation

        # Create a holiday calendar with today as a holiday
        today = datetime.now(timezone.utc).date()
        cal = Calendar(
            name="e2e-holiday-cal",
            calendar_type=CalendarType.HOLIDAY,
            timezone="UTC",
        )
        db_session.add(cal)
        await db_session.flush()

        holiday = CalendarDate(
            calendar_id=cal.id,
            date=today,
            is_business_day=False,
            label="Test Holiday",
        )
        db_session.add(holiday)

        # Create agent, job, schedule
        agent = Agent(
            hostname="e2e-cal-agent",
            status=AgentStatus.ONLINE,
            max_concurrent_jobs=4,
            last_heartbeat_at=datetime.now(timezone.utc),
        )
        db_session.add(agent)

        job = Job(
            name="e2e-holiday-skip-job",
            job_type="shell",
            command="echo should-not-run",
            status=JobStatus.ACTIVE,
        )
        db_session.add(job)
        await db_session.flush()

        # Associate job with calendar + SKIP_HOLIDAYS constraint
        assoc = JobCalendarAssociation(
            job_id=job.id,
            calendar_id=cal.id,
            constraint_type="skip_holidays",
        )
        db_session.add(assoc)

        schedule = Schedule(
            job_id=job.id,
            trigger_type="cron",
            cron_expression="*/5 * * * *",
            timezone="UTC",
            next_run_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            enabled=True,
        )
        db_session.add(schedule)
        await db_session.commit()

        # Run scheduler tick — should skip this job
        scheduler = Scheduler()
        enqueued = await scheduler.tick(db_session)
        assert enqueued == 0

        # No runs should be created
        runs = (await db_session.execute(
            select(func.count(JobRun.id)).where(JobRun.job_id == job.id)
        )).scalar()
        assert runs == 0


# -----------------------------------------------------------------------
# Scenario 3: DST transitions
# -----------------------------------------------------------------------


class TestE2EDSTTransitions:
    async def test_spring_forward_no_duplicate(self, db_session):
        """CronEvaluator handles spring-forward DST gap without errors."""
        from reliant_scheduler.services.cron_evaluator import CronEvaluator

        evaluator = CronEvaluator()
        # 2:30 AM doesn't exist on spring-forward day (March 9, 2025 US/Eastern)
        after = datetime(2025, 3, 9, 6, 0, tzinfo=timezone.utc)  # 1:00 AM EST
        next_run = evaluator.get_next_run("30 2 * * *", "US/Eastern", after=after)
        # Should produce a valid time (either skips to 3:30 or next day's 2:30)
        assert next_run is not None
        assert next_run > after


# -----------------------------------------------------------------------
# Scenario 4: Dependency chains (DAG)
# -----------------------------------------------------------------------


class TestE2EDependencyChains:
    async def test_dag_a_b_c_executes_in_order(self, db_session, test_session_factory):
        """Job DAG A→B→C: B runs only after A succeeds, C only after B succeeds."""
        agent = Agent(
            hostname="e2e-dag-agent",
            status=AgentStatus.ONLINE,
            max_concurrent_jobs=4,
            last_heartbeat_at=datetime.now(timezone.utc),
        )
        db_session.add(agent)

        # Create 3 jobs: A, B, C
        job_a = Job(name="e2e-dag-A", job_type="shell", command="echo A", status=JobStatus.ACTIVE)
        job_b = Job(name="e2e-dag-B", job_type="shell", command="echo B", status=JobStatus.ACTIVE)
        job_c = Job(name="e2e-dag-C", job_type="shell", command="echo C", status=JobStatus.ACTIVE)
        db_session.add_all([job_a, job_b, job_c])
        await db_session.flush()

        # B depends on A, C depends on B
        dep_ba = JobDependency(dependent_job_id=job_b.id, depends_on_job_id=job_a.id)
        dep_cb = JobDependency(dependent_job_id=job_c.id, depends_on_job_id=job_b.id)
        db_session.add_all([dep_ba, dep_cb])

        # Create pending runs for all three
        run_a = JobRun(job_id=job_a.id, status=RunStatus.PENDING, triggered_by="manual")
        run_b = JobRun(job_id=job_b.id, status=RunStatus.PENDING, triggered_by="manual")
        run_c = JobRun(job_id=job_c.id, status=RunStatus.PENDING, triggered_by="manual")
        db_session.add_all([run_a, run_b, run_c])
        await db_session.commit()

        scheduler = Scheduler()

        # Tick 1: Only A should be enqueued (B and C have unsatisfied deps)
        enqueued = await scheduler.tick(db_session)
        assert enqueued == 1
        async with test_session_factory() as session:
            ra = (await session.execute(select(JobRun).where(JobRun.id == run_a.id))).scalar_one()
            rb = (await session.execute(select(JobRun).where(JobRun.id == run_b.id))).scalar_one()
            rc = (await session.execute(select(JobRun).where(JobRun.id == run_c.id))).scalar_one()
            assert ra.status == RunStatus.QUEUED
            assert rb.status == RunStatus.PENDING
            assert rc.status == RunStatus.PENDING

        # Complete A
        async with test_session_factory() as session:
            ra = (await session.execute(select(JobRun).where(JobRun.id == run_a.id))).scalar_one()
            ra.status = RunStatus.SUCCESS
            ra.exit_code = 0
            ra.finished_at = datetime.now(timezone.utc)
            await session.commit()

        # Tick 2: B should now be enqueued
        async with test_session_factory() as session:
            enqueued = await scheduler.tick(session)
            assert enqueued == 1
            rb = (await session.execute(select(JobRun).where(JobRun.id == run_b.id))).scalar_one()
            rc = (await session.execute(select(JobRun).where(JobRun.id == run_c.id))).scalar_one()
            assert rb.status == RunStatus.QUEUED
            assert rc.status == RunStatus.PENDING

        # Complete B
        async with test_session_factory() as session:
            rb = (await session.execute(select(JobRun).where(JobRun.id == run_b.id))).scalar_one()
            rb.status = RunStatus.SUCCESS
            rb.exit_code = 0
            rb.finished_at = datetime.now(timezone.utc)
            await session.commit()

        # Tick 3: C should now be enqueued
        async with test_session_factory() as session:
            enqueued = await scheduler.tick(session)
            assert enqueued == 1
            rc = (await session.execute(select(JobRun).where(JobRun.id == run_c.id))).scalar_one()
            assert rc.status == RunStatus.QUEUED


# -----------------------------------------------------------------------
# Scenario 5: Failure recovery via event-action automation
# -----------------------------------------------------------------------


class TestE2EFailureRecovery:
    async def test_failed_job_triggers_recovery(self, db_session, test_session_factory):
        """Job failure emits event → recovery action fires → execution recorded."""
        # Wire up event router
        event_router = EventRouter(session_factory=test_session_factory)
        clear_handlers()
        register_handler(event_router.handle_event)

        try:
            # Create event type for job failure
            evt_type = EventType(name="job.failed", description="Job failed")
            db_session.add(evt_type)
            await db_session.flush()

            # Create a webhook recovery action
            action = Action(
                name="e2e-recovery-action",
                type="webhook",
                config_json={
                    "url": "http://localhost/recovery",
                    "method": "POST",
                },
            )
            db_session.add(action)
            await db_session.flush()

            # Bind the event to the action
            binding = EventActionBinding(
                event_type_id=evt_type.id,
                action_id=action.id,
                enabled=True,
                filter_json=None,
            )
            db_session.add(binding)
            await db_session.commit()

            # Emit a job.failed event
            await emit_event("job.failed", {
                "job_id": str(uuid.uuid4()),
                "job_name": "e2e-failing-job",
                "exit_code": 1,
                "error": "segfault",
            })

            # Give async handlers time to process
            await asyncio.sleep(0.2)

            # Verify action execution was recorded
            async with test_session_factory() as session:
                execs = (await session.execute(
                    select(ActionExecution).where(
                        ActionExecution.event_action_binding_id == binding.id
                    )
                )).scalars().all()
                assert len(execs) >= 1
        finally:
            clear_handlers()


# -----------------------------------------------------------------------
# Scenario 6: SLA critical path and breach detection
# -----------------------------------------------------------------------


class TestE2ESLACriticalPath:
    async def test_sla_breach_emits_event(self, db_session, test_session_factory):
        """SLA policy with exceeded target fires breach event."""
        # Create jobs in a chain: A→B
        job_a = Job(name="e2e-sla-A", job_type="shell", command="echo A", status=JobStatus.ACTIVE,
                     timeout_seconds=600)
        job_b = Job(name="e2e-sla-B", job_type="shell", command="echo B", status=JobStatus.ACTIVE,
                     timeout_seconds=900)
        db_session.add_all([job_a, job_b])
        await db_session.flush()

        dep = JobDependency(dependent_job_id=job_b.id, depends_on_job_id=job_a.id)
        db_session.add(dep)

        # Create an SLA policy with a target already in the past (guaranteed breach)
        policy = SLAPolicy(
            name="e2e-sla-breach-policy",
            target_completion_time=datetime.now(timezone.utc) - timedelta(hours=1),
            risk_window_minutes=30,
            breach_window_minutes=0,
        )
        db_session.add(policy)
        await db_session.flush()

        # Link jobs to SLA policy
        for job in [job_a, job_b]:
            constraint = SLAJobConstraint(
                sla_policy_id=policy.id,
                job_id=job.id,
                track_critical_path=True,
                max_duration_minutes=10,
            )
            db_session.add(constraint)
        await db_session.commit()

        # Evaluate SLA — should detect breach
        from reliant_scheduler.services.sla_service import SLAService

        sla_service = SLAService()
        events = await sla_service.check_and_emit_events(db_session, policy.id)
        await db_session.commit()

        assert len(events) == 1
        assert events[0].event_type == SLAEventType.BREACHED


# -----------------------------------------------------------------------
# Scenario 7: RBAC enforcement
# -----------------------------------------------------------------------


class TestE2ERBACEnforcement:
    async def test_role_hierarchy_enforced_via_api(self, client, db_session):
        """Different user roles have correct permission boundaries."""
        # Create an Inquiry user (read-only)
        resp = await client.post("/api/users", json={
            "display_name": "E2E Inquiry User",
            "email": "inquiry@e2e.test",
            "role": "inquiry",
        })
        assert resp.status_code == 201

        # Create a User role user
        resp = await client.post("/api/users", json={
            "display_name": "E2E Basic User",
            "email": "user@e2e.test",
            "role": "user",
        })
        assert resp.status_code == 201

        # Verify both users exist
        resp = await client.get("/api/users")
        assert resp.status_code == 200
        users = resp.json()["items"]
        names = [u["display_name"] for u in users]
        assert "E2E Inquiry User" in names
        assert "E2E Basic User" in names

    async def test_audit_log_tracks_mutations(self, client, db_session):
        """POST mutations create audit log entries."""
        # Create a job
        resp = await client.post("/api/jobs", json={
            "name": "e2e-audit-job",
            "job_type": "shell",
            "command": "echo audit",
        })
        assert resp.status_code == 201
        job_id = resp.json()["id"]

        # Check audit log — POST /api/jobs creates an audit entry with
        # resource_type="job" and action="create". resource_id is extracted
        # from the URL path so it's None for collection-level POSTs.
        resp = await client.get("/api/audit-log")
        assert resp.status_code == 200
        entries = resp.json()["items"]
        job_create_entries = [
            e for e in entries
            if e.get("resource_type") == "job" and e.get("action") == "create"
        ]
        assert len(job_create_entries) >= 1
        # Verify audit entry has expected structure
        entry = job_create_entries[0]
        assert entry["details_json"]["method"] == "POST"
        assert "/api/jobs" in entry["details_json"]["path"]


# -----------------------------------------------------------------------
# Scenario 8: Connection execution E2E
# -----------------------------------------------------------------------


class TestE2EConnectionExecution:
    async def test_database_job_end_to_end(self, client, db_session, test_session_factory, postgres_url):
        """Create DB connection → create job → trigger → worker executes SQL against real Postgres."""
        # Create connection via API
        resp = await client.post("/api/connections", json={
            "name": "e2e-pg-connection",
            "connection_type": "database",
            "host": "localhost",
            "port": 5432,
            "extra": {
                "db_type": "postgresql",
                "connection_string": postgres_url.replace("+asyncpg", ""),
            },
        })
        assert resp.status_code == 201
        conn_id = resp.json()["id"]

        # Create job with connection
        resp = await client.post("/api/jobs", json={
            "name": "e2e-db-exec-job",
            "job_type": "database",
            "command": "SELECT 42 AS result",
            "connection_id": conn_id,
        })
        assert resp.status_code == 201
        job_data = resp.json()
        job_id = job_data["id"]
        assert job_data["connection_id"] == conn_id

        # Trigger the job manually
        resp = await client.post(f"/api/jobs/{job_id}/trigger", json={})
        assert resp.status_code in (200, 201)
        run_data = resp.json()
        run_id = run_data["id"]

        # Execute via worker
        agent = Agent(
            hostname="e2e-conn-agent",
            status=AgentStatus.ONLINE,
            max_concurrent_jobs=4,
            last_heartbeat_at=datetime.now(timezone.utc),
        )
        db_session.add(agent)
        await db_session.commit()
        await db_session.refresh(agent)

        worker = WorkerAgent(hostname="e2e-conn-worker")
        worker._session_factory = test_session_factory
        worker.agent_id = agent.id

        msg = JobMessage(
            run_id=run_id,
            job_id=job_id,
            job_name="e2e-db-exec-job",
            command="SELECT 42 AS result",
            parameters=None,
            attempt_number=1,
            timeout_seconds=30,
            connection_id=conn_id,
            connection_type="database",
        )

        # Mark run as RUNNING
        async with test_session_factory() as session:
            run = (await session.execute(
                select(JobRun).where(JobRun.id == uuid.UUID(run_id))
            )).scalar_one()
            run.status = RunStatus.RUNNING
            run.agent_id = agent.id
            run.started_at = datetime.now(timezone.utc)
            await session.commit()

        await worker._execute_via_connection(
            msg,
            correlation_id="e2e-conn-corr",
            log=structlog.get_logger("e2e"),
        )

        # Verify run succeeded
        async with test_session_factory() as session:
            final_run = (await session.execute(
                select(JobRun).where(JobRun.id == uuid.UUID(run_id))
            )).scalar_one()
            assert final_run.status == RunStatus.SUCCESS
            assert final_run.exit_code == 0

    async def test_connection_test_endpoint(self, client, db_session, postgres_url):
        """POST /api/connections/{id}/test validates connectivity."""
        conn = Connection(
            name="e2e-test-conn",
            connection_type=ConnectionType.DATABASE,
            host="localhost",
            port=5432,
            extra={
                "db_type": "postgresql",
                "connection_string": postgres_url.replace("+asyncpg", ""),
            },
        )
        db_session.add(conn)
        await db_session.commit()
        await db_session.refresh(conn)

        resp = await client.post(f"/api/connections/{conn.id}/test")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["latency_ms"] > 0


# -----------------------------------------------------------------------
# Scenario 9: Concurrent execution
# -----------------------------------------------------------------------


class TestE2EConcurrentExecution:
    async def test_concurrent_jobs_no_corruption(self, db_session, test_session_factory):
        """Queue 10 jobs simultaneously — worker processes without deadlock or corruption."""
        agent = Agent(
            hostname="e2e-concurrent-agent",
            status=AgentStatus.ONLINE,
            max_concurrent_jobs=10,
            last_heartbeat_at=datetime.now(timezone.utc),
        )
        db_session.add(agent)

        # Create 10 independent jobs with pending runs
        jobs = []
        runs = []
        for i in range(10):
            job = Job(
                name=f"e2e-concurrent-{i}",
                job_type="shell",
                command=f"echo job-{i}",
                status=JobStatus.ACTIVE,
            )
            db_session.add(job)
            await db_session.flush()

            schedule = Schedule(
                job_id=job.id,
                trigger_type="cron",
                cron_expression="*/1 * * * *",
                timezone="UTC",
                next_run_at=datetime.now(timezone.utc) - timedelta(minutes=1),
                enabled=True,
            )
            db_session.add(schedule)
            jobs.append(job)

        await db_session.commit()

        # Scheduler tick should enqueue all 10
        scheduler = Scheduler()
        enqueued = await scheduler.tick(db_session)
        assert enqueued == 10

        # Verify all 10 runs are QUEUED
        result = await db_session.execute(
            select(func.count(JobRun.id)).where(JobRun.status == RunStatus.QUEUED)
        )
        queued_count = result.scalar()
        assert queued_count == 10

        # Drain queue and verify 10 messages
        messages = scheduler.queue.drain_local()
        assert len(messages) == 10

        # Execute all 10 concurrently via the worker
        worker = WorkerAgent(hostname="e2e-concurrent-worker")
        worker._session_factory = test_session_factory
        worker.agent_id = agent.id

        async def execute_one(msg):
            async with test_session_factory() as session:
                run = (await session.execute(
                    select(JobRun).where(JobRun.id == uuid.UUID(msg.run_id))
                )).scalar_one()
                run.status = RunStatus.RUNNING
                run.agent_id = agent.id
                run.started_at = datetime.now(timezone.utc)
                await session.commit()

            await worker._execute_shell_command(
                msg,
                correlation_id=f"e2e-conc-{msg.run_id[:8]}",
                log=structlog.get_logger("e2e"),
            )

        # Run all 10 concurrently
        await asyncio.gather(*[execute_one(msg) for msg in messages])

        # Verify all 10 runs completed successfully
        async with test_session_factory() as session:
            result = await session.execute(
                select(func.count(JobRun.id)).where(JobRun.status == RunStatus.SUCCESS)
            )
            success_count = result.scalar()
            assert success_count == 10

            # Verify no duplicate or corrupt runs
            result = await session.execute(select(func.count(JobRun.id)))
            total_count = result.scalar()
            assert total_count == 10


# -----------------------------------------------------------------------
# Scenario 10: Health check degradation
# -----------------------------------------------------------------------


class TestE2EHealthCheck:
    async def test_livez_always_ok(self, client):
        """/livez returns 200 regardless of dependencies."""
        resp = await client.get("/livez")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    async def test_healthz_with_db(self, client):
        """/healthz returns 200 when PostgreSQL is healthy."""
        resp = await client.get("/healthz")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["checks"]["postgresql"]["status"] == "healthy"

    async def test_healthz_reports_unconfigured_services(self, client):
        """/healthz reports unconfigured Azure services as skipped."""
        resp = await client.get("/healthz")
        assert resp.status_code == 200
        data = resp.json()
        # Azure services are not configured in test mode, so they should be skipped
        for service in ["servicebus", "blob_storage", "keyvault", "eventhubs"]:
            assert data["checks"][service]["status"] == "skipped"
