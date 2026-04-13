"""Core scheduling engine.

Orchestrates cron evaluation, dependency resolution, job queuing,
agent health checks, event triggers, retry handling, and calendar-aware
scheduling in a single tick loop.
"""

from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reliant_scheduler.models.job import Job, JobDependency
from reliant_scheduler.models.job_run import JobRun, RunStatus
from reliant_scheduler.models.schedule import Schedule
from reliant_scheduler.services.calendar_service import CalendarService
from reliant_scheduler.services.cron_evaluator import CronEvaluator
from reliant_scheduler.services.dag_resolver import DagResolver
from reliant_scheduler.services.event_trigger import EventTrigger
from reliant_scheduler.services.job_queue import JobQueue, JobMessage
from reliant_scheduler.services.agent_registry import AgentRegistry
from reliant_scheduler.services.retry_handler import RetryHandler
from reliant_scheduler.services.sla_service import SLAService
from reliant_scheduler.services.event_emitter import emit_event
from reliant_scheduler.api.routes.ws_events import publish_job_status_change

logger = structlog.get_logger(__name__)


class Scheduler:
    """Main scheduling engine. Call `tick()` periodically to process due jobs."""

    def __init__(self) -> None:
        self.cron = CronEvaluator()
        self.dag = DagResolver()
        self.queue = JobQueue()
        self.agents = AgentRegistry()
        self.retry = RetryHandler()
        self.event_trigger = EventTrigger()
        self.calendar = CalendarService()
        self.sla = SLAService()

    async def tick(self, session: AsyncSession) -> int:
        """Run one scheduling cycle. Returns the number of jobs enqueued.

        The entire tick is wrapped in error handling so that transient
        failures (DB hiccups, queue timeouts, etc.) are logged with full
        context and do not silently kill the scheduler loop.
        """
        try:
            return await self._tick_inner(session)
        except Exception:
            logger.exception("scheduler_tick_failed")
            raise

    async def _tick_inner(self, session: AsyncSession) -> int:
        now = datetime.now(timezone.utc)
        enqueued = 0

        # 1. Mark stale agents offline
        stale_count = await self.agents.mark_stale_agents(session)
        if stale_count:
            logger.info("stale_agents_marked_offline", count=stale_count)

        # 2. Evaluate cron schedules and create pending runs
        #    Check calendar constraints before creating a run.
        due_schedules = await self.cron.get_due_schedules(session, now)
        today = now.date()
        for schedule in due_schedules:
            # Calendar-aware: check if the job should run today
            should_run = await self.calendar.should_run_job(session, schedule.job_id, today)
            if not should_run:
                # Skip this run but advance the schedule so we don't re-evaluate
                await self.cron.advance_schedule(session, schedule)
                logger.info(
                    "run_skipped_calendar_constraint",
                    job_id=str(schedule.job_id),
                    date=str(today),
                )
                continue

            run = JobRun(
                job_id=schedule.job_id,
                status=RunStatus.PENDING,
                triggered_by="schedule",
            )
            session.add(run)
            await self.cron.advance_schedule(session, schedule)
            logger.info("pending_run_created", job_id=str(schedule.job_id), trigger="cron")

        await session.flush()

        # 3. Resolve DAG
        graph = await self.dag.build_graph(session)

        # 4. Fetch pending runs
        pending_result = await session.execute(
            select(JobRun)
            .where(JobRun.status == RunStatus.PENDING)
            .join(Job)
            .order_by(JobRun.created_at)
            .limit(100)
        )
        pending_runs = list(pending_result.scalars().all())

        available_agents = await self.agents.get_available_agents(session)
        if not available_agents and pending_runs:
            logger.warning("no_available_agents", pending_runs=len(pending_runs))
            for run in pending_runs:
                job_r = await session.execute(select(Job).where(Job.id == run.job_id))
                j = job_r.scalar_one_or_none()
                if j:
                    await emit_event("schedule.missed", {
                        "job_id": str(j.id),
                        "job_name": j.name,
                        "run_id": str(run.id),
                        "reason": "no_available_agents",
                    })

        # 5. Enqueue runs whose dependencies are satisfied
        for run in pending_runs:
            job_result = await session.execute(select(Job).where(Job.id == run.job_id))
            job = job_result.scalar_one_or_none()
            if not job:
                continue

            # Enforce dependency-based triggers: all upstream jobs must have a
            # successful latest run before this job can be enqueued.
            if not await self._dependencies_satisfied(session, job.id):
                logger.debug(
                    "dependencies_not_satisfied",
                    job_id=str(job.id),
                    job_name=job.name,
                )
                continue

            message = JobMessage(
                run_id=str(run.id),
                job_id=str(job.id),
                job_name=job.name,
                command=job.command,
                parameters=job.parameters,
                attempt_number=run.attempt_number,
                timeout_seconds=job.timeout_seconds,
                connection_id=str(job.connection_id) if job.connection_id else None,
                connection_type=None,
            )
            await self.queue.enqueue(message)
            previous_status = run.status
            run.status = RunStatus.QUEUED
            run.started_at = now
            session.add(run)
            enqueued += 1

            # Broadcast real-time status change to WebSocket clients
            await publish_job_status_change(
                job_id=str(job.id),
                job_name=job.name,
                run_id=str(run.id),
                previous_status=previous_status,
                status=RunStatus.QUEUED,
            )

            await emit_event("job.started", {
                "job_id": str(job.id),
                "job_name": job.name,
                "run_id": str(run.id),
                "attempt_number": run.attempt_number,
            })

        # 6. Evaluate SLA policies for risk/breach events
        sla_events = await self.sla.evaluate_all_policies(session)
        if sla_events:
            logger.info("sla_events_emitted", count=sla_events)

        await session.commit()
        if enqueued:
            logger.info("scheduler_tick_complete", enqueued=enqueued)
        return enqueued

    # ------------------------------------------------------------------
    # Dependency enforcement
    # ------------------------------------------------------------------

    async def _dependencies_satisfied(
        self, session: AsyncSession, job_id: "import('uuid').UUID"  # noqa: F821
    ) -> bool:
        """Return True if every upstream dependency of *job_id* has a successful latest run."""
        deps_result = await session.execute(
            select(JobDependency.depends_on_job_id).where(
                JobDependency.dependent_job_id == job_id
            )
        )
        upstream_ids = [row[0] for row in deps_result.all()]
        if not upstream_ids:
            return True

        for upstream_id in upstream_ids:
            latest_run_result = await session.execute(
                select(JobRun)
                .where(JobRun.job_id == upstream_id)
                .order_by(JobRun.created_at.desc())
                .limit(1)
            )
            latest_run = latest_run_result.scalar_one_or_none()
            if not latest_run or latest_run.status != RunStatus.SUCCESS:
                return False
        return True

    # ------------------------------------------------------------------
    # Event trigger integration
    # ------------------------------------------------------------------

    async def handle_event(self, session: AsyncSession, event_data: dict) -> int:
        """Process an incoming event and create runs for matching event-triggered schedules.

        Returns the number of runs created.
        """
        result = await session.execute(
            select(Schedule).where(
                Schedule.enabled.is_(True),
                Schedule.trigger_type == "event",
            )
        )
        event_schedules = list(result.scalars().all())

        created = 0
        for schedule in event_schedules:
            if not self.event_trigger.matches_filter(event_data, schedule.event_filter):
                continue
            run = JobRun(
                job_id=schedule.job_id,
                status=RunStatus.PENDING,
                triggered_by="event",
            )
            session.add(run)
            created += 1
            logger.info(
                "pending_run_created",
                job_id=str(schedule.job_id),
                trigger="event",
                event_source=schedule.event_source,
            )

        if created:
            await session.flush()
        return created
