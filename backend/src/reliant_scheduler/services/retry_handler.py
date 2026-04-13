"""Retry and failure handling for job runs."""

import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reliant_scheduler.models.job import Job
from reliant_scheduler.models.job_run import JobRun, RunStatus

logger = structlog.get_logger(__name__)


class RetryHandler:
    """Determines whether failed jobs should be retried and creates retry runs."""

    async def handle_failure(
        self, session: AsyncSession, run: JobRun
    ) -> JobRun | None:
        """Check if a failed run should be retried. Returns new run if retrying, else None."""
        job_result = await session.execute(select(Job).where(Job.id == run.job_id))
        job = job_result.scalar_one_or_none()
        if not job:
            return None

        if run.attempt_number >= job.max_retries + 1:
            logger.info(
                "retries_exhausted",
                job_name=job.name,
                run_id=str(run.id),
                attempt=run.attempt_number,
                max_attempts=job.max_retries + 1,
            )
            return None

        retry_run = JobRun(
            job_id=job.id,
            status=RunStatus.PENDING,
            triggered_by="retry",
            parameters=run.parameters,
            attempt_number=run.attempt_number + 1,
        )
        session.add(retry_run)
        await session.flush()

        logger.info(
            "retry_scheduled",
            job_name=job.name,
            attempt=retry_run.attempt_number,
            max_attempts=job.max_retries + 1,
            run_id=str(retry_run.id),
        )
        return retry_run

    async def handle_timeout(
        self, session: AsyncSession, run: JobRun
    ) -> None:
        """Mark a run as timed out."""
        run.status = RunStatus.TIMED_OUT
        run.finished_at = datetime.now(timezone.utc)
        run.error_message = f"Job exceeded timeout of {run.job.timeout_seconds if run.job else '?'}s"
        session.add(run)
