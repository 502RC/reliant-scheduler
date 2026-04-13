"""Cron schedule evaluation service.

Evaluates which scheduled jobs are due for execution based on their cron expressions.
Uses zoneinfo for DST-aware scheduling to correctly handle spring-forward and
fall-back transitions.
"""

from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

from croniter import croniter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reliant_scheduler.models.schedule import Schedule


class CronEvaluator:
    """Evaluates cron-based schedules and determines which jobs are due."""

    def get_next_run(self, cron_expression: str, tz: str, after: datetime | None = None) -> datetime:
        """Calculate the next run time for a cron expression, DST-aware.

        All times are stored as UTC internally. The cron expression is evaluated
        in the schedule's local timezone so that "0 30 2 * * *" means 2:30 AM
        local time, then the result is converted back to UTC for storage.

        DST edge cases:
        - Spring forward (e.g. 2:30 AM doesn't exist in US/Eastern on DST day):
          croniter will naturally produce the next valid time (3:00 AM local).
        - Fall back (e.g. 1:30 AM occurs twice): we evaluate in wall-clock time
          and deduplicate by tracking next_run_at in UTC, ensuring a job runs
          once per scheduling window.
        """
        zone = ZoneInfo(tz) if tz and tz != "UTC" else timezone.utc

        base_utc = after or datetime.now(timezone.utc)

        if zone == timezone.utc:
            cron = croniter(cron_expression, base_utc)
            return cron.get_next(datetime).replace(tzinfo=timezone.utc)

        # Convert base time to local for cron evaluation
        base_local = base_utc.astimezone(zone)
        cron = croniter(cron_expression, base_local)
        next_local = cron.get_next(datetime)

        # Ensure the local time has the correct zone attached
        if next_local.tzinfo is None:
            next_local = next_local.replace(tzinfo=zone)

        # Convert back to UTC for storage
        next_utc = next_local.astimezone(timezone.utc)
        return next_utc

    def is_in_dst_gap(self, dt_utc: datetime, tz: str) -> bool:
        """Check if a UTC time falls in a DST spring-forward gap when viewed in the given timezone.

        During spring-forward, certain local times don't exist (e.g. 2:00-2:59 AM US/Eastern
        on the second Sunday of March). This method checks whether the local representation
        of the given UTC time was "folded" by the timezone, indicating proximity to a gap.
        """
        if not tz or tz == "UTC":
            return False
        zone = ZoneInfo(tz)
        local_dt = dt_utc.astimezone(zone)
        # Check if converting back produces a different UTC offset, indicating gap proximity
        naive = local_dt.replace(tzinfo=None)
        reconstructed = naive.replace(tzinfo=zone)
        return reconstructed.utcoffset() != local_dt.utcoffset()

    async def get_due_schedules(self, session: AsyncSession, now: datetime | None = None) -> list[Schedule]:
        """Return all enabled schedules whose next_run_at is in the past."""
        now = now or datetime.now(timezone.utc)
        result = await session.execute(
            select(Schedule).where(
                Schedule.enabled.is_(True),
                Schedule.trigger_type == "cron",
                Schedule.next_run_at <= now,
            )
        )
        return list(result.scalars().all())

    async def advance_schedule(self, session: AsyncSession, schedule: Schedule) -> None:
        """Update next_run_at to the next occurrence after current next_run_at."""
        if schedule.cron_expression:
            schedule.next_run_at = self.get_next_run(
                schedule.cron_expression, schedule.timezone, schedule.next_run_at
            )
            session.add(schedule)
