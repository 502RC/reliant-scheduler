"""Calendar-aware scheduling service.

Checks calendar constraints before allowing job runs to be created.
Handles business-day checks, holiday skipping, and DST gap detection.
"""

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reliant_scheduler.models.calendar import (
    CalendarDate,
    ConstraintType,
    DSTPolicy,
    JobCalendarAssociation,
)

logger = structlog.get_logger(__name__)


class CalendarService:
    """Evaluates calendar constraints for job scheduling decisions."""

    async def should_run_job(
        self,
        session: AsyncSession,
        job_id: "import('uuid').UUID",  # noqa: F821
        run_date: date,
    ) -> bool:
        """Check all calendar associations for a job and return False if any constraint blocks execution."""
        result = await session.execute(
            select(JobCalendarAssociation).where(JobCalendarAssociation.job_id == job_id)
        )
        associations = list(result.scalars().all())

        if not associations:
            return True  # No calendar constraints = always run

        for assoc in associations:
            if not await self._check_constraint(session, assoc, run_date):
                logger.info(
                    "job_skipped_by_calendar",
                    job_id=str(job_id),
                    calendar_id=str(assoc.calendar_id),
                    constraint=assoc.constraint_type,
                    date=str(run_date),
                )
                return False

        return True

    async def _check_constraint(
        self,
        session: AsyncSession,
        assoc: JobCalendarAssociation,
        run_date: date,
    ) -> bool:
        """Return True if the constraint allows execution on the given date."""
        calendar_date = await self._get_calendar_date(session, assoc.calendar_id, run_date)

        if assoc.constraint_type == ConstraintType.RUN_ONLY_ON_BUSINESS_DAYS:
            if calendar_date is None:
                # No explicit entry — treat weekdays as business days
                return run_date.weekday() < 5
            return calendar_date.is_business_day

        if assoc.constraint_type == ConstraintType.SKIP_HOLIDAYS:
            if calendar_date is None:
                return True  # No entry = not a holiday
            # Skip if explicitly marked as non-business-day with a label (holiday)
            if not calendar_date.is_business_day and calendar_date.label:
                return False
            return True

        # CUSTOM constraints: defer to calendar_date.is_business_day if present
        if calendar_date is not None:
            return calendar_date.is_business_day
        return True

    async def _get_calendar_date(
        self,
        session: AsyncSession,
        calendar_id: "import('uuid').UUID",  # noqa: F821
        run_date: date,
    ) -> CalendarDate | None:
        result = await session.execute(
            select(CalendarDate).where(
                CalendarDate.calendar_id == calendar_id,
                CalendarDate.date == run_date,
            )
        )
        return result.scalar_one_or_none()

    async def get_dst_policy(
        self,
        session: AsyncSession,
        job_id: "import('uuid').UUID",  # noqa: F821
    ) -> DSTPolicy:
        """Return the DST policy for a job. Defaults to SKIP if no association specifies one."""
        result = await session.execute(
            select(JobCalendarAssociation.dst_policy).where(
                JobCalendarAssociation.job_id == job_id
            ).limit(1)
        )
        row = result.first()
        if row:
            return DSTPolicy(row[0])
        return DSTPolicy.SKIP
