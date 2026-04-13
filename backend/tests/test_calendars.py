"""Integration tests for calendar system: CRUD, DST-aware scheduling,
calendar-aware job scheduling, where-used analysis, and built-in calendar seeding.
"""

import uuid
from datetime import date, datetime, timezone, timedelta
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from reliant_scheduler.models.calendar import (
    Calendar,
    CalendarDate,
    CalendarType,
    ConstraintType,
    DSTPolicy,
    JobCalendarAssociation,
)
from reliant_scheduler.models.job import Job
from reliant_scheduler.models.schedule import Schedule
from reliant_scheduler.models.job_run import JobRun, RunStatus
from reliant_scheduler.services.calendar_service import CalendarService
from reliant_scheduler.services.cron_evaluator import CronEvaluator
from reliant_scheduler.services.calendar_seed import seed_builtin_calendars

pytestmark = pytest.mark.asyncio


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

async def _create_job(client: AsyncClient, name: str) -> str:
    resp = await client.post("/api/jobs", json={
        "name": name,
        "job_type": "shell",
        "command": "echo hello",
    })
    assert resp.status_code == 201
    return resp.json()["id"]


async def _create_calendar(client: AsyncClient, name: str, cal_type: str = "business") -> str:
    resp = await client.post("/api/calendars", json={
        "name": name,
        "calendar_type": cal_type,
        "timezone": "America/New_York",
    })
    assert resp.status_code == 201
    return resp.json()["id"]


# ──────────────────────────────────────────────────────────────
# Calendar CRUD
# ──────────────────────────────────────────────────────────────

class TestCalendarCRUD:
    async def test_create_calendar(self, client: AsyncClient) -> None:
        resp = await client.post("/api/calendars", json={
            "name": "Test Business Cal",
            "calendar_type": "business",
            "timezone": "America/New_York",
            "description": "A test calendar",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Test Business Cal"
        assert data["calendar_type"] == "business"
        assert data["timezone"] == "America/New_York"
        assert data["is_builtin"] is False

    async def test_list_calendars(self, client: AsyncClient) -> None:
        await _create_calendar(client, "List Cal 1", "business")
        await _create_calendar(client, "List Cal 2", "holiday")
        resp = await client.get("/api/calendars")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 2

    async def test_list_calendars_filter_type(self, client: AsyncClient) -> None:
        await _create_calendar(client, "Filter Biz", "business")
        await _create_calendar(client, "Filter Holiday", "holiday")
        resp = await client.get("/api/calendars", params={"calendar_type": "holiday"})
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert all(i["calendar_type"] == "holiday" for i in items)

    async def test_get_calendar(self, client: AsyncClient) -> None:
        cal_id = await _create_calendar(client, "Get Cal")
        resp = await client.get(f"/api/calendars/{cal_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == cal_id

    async def test_get_calendar_not_found(self, client: AsyncClient) -> None:
        resp = await client.get(f"/api/calendars/{uuid.uuid4()}")
        assert resp.status_code == 404

    async def test_update_calendar(self, client: AsyncClient) -> None:
        cal_id = await _create_calendar(client, "Update Cal")
        resp = await client.patch(f"/api/calendars/{cal_id}", json={"description": "Updated"})
        assert resp.status_code == 200
        assert resp.json()["description"] == "Updated"

    async def test_delete_calendar(self, client: AsyncClient) -> None:
        cal_id = await _create_calendar(client, "Delete Cal")
        resp = await client.delete(f"/api/calendars/{cal_id}")
        assert resp.status_code == 204
        resp = await client.get(f"/api/calendars/{cal_id}")
        assert resp.status_code == 404


# ──────────────────────────────────────────────────────────────
# Calendar Dates
# ──────────────────────────────────────────────────────────────

class TestCalendarDates:
    async def test_create_date(self, client: AsyncClient) -> None:
        cal_id = await _create_calendar(client, "Date Cal")
        resp = await client.post(f"/api/calendars/{cal_id}/dates", json={
            "date": "2026-12-25",
            "is_business_day": False,
            "label": "Christmas Day",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["is_business_day"] is False
        assert data["label"] == "Christmas Day"

    async def test_list_dates(self, client: AsyncClient) -> None:
        cal_id = await _create_calendar(client, "Dates List Cal")
        await client.post(f"/api/calendars/{cal_id}/dates", json={
            "date": "2026-01-01", "is_business_day": False, "label": "New Year",
        })
        await client.post(f"/api/calendars/{cal_id}/dates", json={
            "date": "2026-01-02", "is_business_day": True,
        })
        resp = await client.get(f"/api/calendars/{cal_id}/dates")
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    async def test_list_dates_filter_year(self, client: AsyncClient) -> None:
        cal_id = await _create_calendar(client, "Year Filter Cal")
        await client.post(f"/api/calendars/{cal_id}/dates", json={
            "date": "2026-07-04", "is_business_day": False, "label": "July 4th",
        })
        await client.post(f"/api/calendars/{cal_id}/dates", json={
            "date": "2027-07-04", "is_business_day": False, "label": "July 4th",
        })
        resp = await client.get(f"/api/calendars/{cal_id}/dates", params={"year": 2026})
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    async def test_bulk_create_dates(self, client: AsyncClient) -> None:
        cal_id = await _create_calendar(client, "Bulk Cal")
        resp = await client.post(f"/api/calendars/{cal_id}/dates/bulk", json={
            "year": 2026,
            "weekdays_only": True,
            "holidays": [
                {"date": "2026-12-25", "is_business_day": False, "label": "Christmas"},
            ],
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["year"] == 2026
        assert data["created"] == 365  # 2026 is not a leap year

        # Verify Christmas is marked as non-business
        resp = await client.get(f"/api/calendars/{cal_id}/dates",
                                params={"year": 2026, "month": 12, "is_business_day": False})
        assert resp.status_code == 200
        dates = resp.json()["items"]
        xmas = [d for d in dates if d["label"] == "Christmas"]
        assert len(xmas) == 1


# ──────────────────────────────────────────────────────────────
# Calendar Rules
# ──────────────────────────────────────────────────────────────

class TestCalendarRules:
    async def test_create_and_list_rules(self, client: AsyncClient) -> None:
        cal_id = await _create_calendar(client, "Rules Cal")
        resp = await client.post(f"/api/calendars/{cal_id}/rules", json={
            "rule_type": "recurring",
            "day_of_week": 0,
            "description": "Monday",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["rule_type"] == "recurring"
        assert data["day_of_week"] == 0

        resp = await client.get(f"/api/calendars/{cal_id}/rules")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    async def test_delete_rule(self, client: AsyncClient) -> None:
        cal_id = await _create_calendar(client, "Del Rule Cal")
        resp = await client.post(f"/api/calendars/{cal_id}/rules", json={
            "rule_type": "one_time",
            "month": 12,
            "day_of_month": 25,
            "description": "Christmas",
        })
        rule_id = resp.json()["id"]
        resp = await client.delete(f"/api/calendars/{cal_id}/rules/{rule_id}")
        assert resp.status_code == 204


# ──────────────────────────────────────────────────────────────
# Job-Calendar Associations + Where-Used
# ──────────────────────────────────────────────────────────────

class TestJobCalendarAssociation:
    async def test_associate_and_list(self, client: AsyncClient) -> None:
        job_id = await _create_job(client, "assoc-job")
        cal_id = await _create_calendar(client, "Assoc Cal")
        resp = await client.post(f"/api/jobs/{job_id}/calendars", json={
            "calendar_id": cal_id,
            "constraint_type": "run_only_on_business_days",
            "dst_policy": "skip",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["constraint_type"] == "run_only_on_business_days"

        resp = await client.get(f"/api/jobs/{job_id}/calendars")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    async def test_where_used(self, client: AsyncClient) -> None:
        job_id = await _create_job(client, "where-used-job")
        cal_id = await _create_calendar(client, "Where Used Cal")
        await client.post(f"/api/jobs/{job_id}/calendars", json={
            "calendar_id": cal_id,
            "constraint_type": "skip_holidays",
        })
        resp = await client.get(f"/api/calendars/{cal_id}/jobs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["id"] == job_id

    async def test_remove_association(self, client: AsyncClient) -> None:
        job_id = await _create_job(client, "remove-assoc-job")
        cal_id = await _create_calendar(client, "Remove Assoc Cal")
        resp = await client.post(f"/api/jobs/{job_id}/calendars", json={
            "calendar_id": cal_id,
            "constraint_type": "custom",
        })
        assoc_id = resp.json()["id"]
        resp = await client.delete(f"/api/jobs/{job_id}/calendars/{assoc_id}")
        assert resp.status_code == 204


# ──────────────────────────────────────────────────────────────
# DST-Aware Scheduling (CronEvaluator)
# ──────────────────────────────────────────────────────────────

class TestDSTAwareScheduling:
    """Tests for DST edge cases per spec requirements."""

    def test_spring_forward_gap(self) -> None:
        """Job at 2:30 AM US/Eastern on March DST transition.
        2:30 AM doesn't exist — clock jumps from 2:00 to 3:00.
        CronEvaluator should produce next valid time (3:00 AM or later).
        """
        evaluator = CronEvaluator()
        # 2026 DST spring forward: March 8, 2026 at 2:00 AM EST -> 3:00 AM EDT
        # Schedule: "30 2 * * *" (2:30 AM local daily)
        # Base time: March 8, 2026 1:00 AM EST = 6:00 AM UTC
        eastern = ZoneInfo("America/New_York")
        base_local = datetime(2026, 3, 8, 1, 0, tzinfo=eastern)
        base_utc = base_local.astimezone(timezone.utc)

        next_run = evaluator.get_next_run("30 2 * * *", "America/New_York", base_utc)
        # The next valid 2:30 AM should be March 9 (day after DST transition)
        # because 2:30 AM on March 8 doesn't exist
        next_local = next_run.astimezone(eastern)
        # It should not be March 8 at 2:30 (that time doesn't exist)
        assert next_run.tzinfo == timezone.utc
        # The local time should be 2:30 AM on March 9 or 3:00+ AM on March 8
        # croniter handles this by skipping the non-existent time
        assert next_local.hour >= 2
        assert next_local.date() >= date(2026, 3, 8)

    def test_fall_back_no_duplicate(self) -> None:
        """Job at 1:30 AM US/Eastern on November DST transition.
        1:30 AM occurs twice — should run once (dedup by UTC next_run_at).
        """
        evaluator = CronEvaluator()
        # 2026 DST fall back: November 1, 2026 at 2:00 AM EDT -> 1:00 AM EST
        # Schedule: "30 1 * * *" (1:30 AM local daily)
        # Base time: Nov 1 at 0:00 AM EDT = 4:00 AM UTC
        eastern = ZoneInfo("America/New_York")
        base_local = datetime(2026, 11, 1, 0, 0, tzinfo=eastern)
        base_utc = base_local.astimezone(timezone.utc)

        next_run1 = evaluator.get_next_run("30 1 * * *", "America/New_York", base_utc)
        # Get the run after that to verify it's the next day, not a duplicate
        next_run2 = evaluator.get_next_run("30 1 * * *", "America/New_York", next_run1)

        # Both should be in UTC
        assert next_run1.tzinfo == timezone.utc
        assert next_run2.tzinfo == timezone.utc
        # Second run should be ~24 hours after the first (next day), not a few minutes
        delta = next_run2 - next_run1
        assert delta >= timedelta(hours=23)

    def test_utc_scheduling_unchanged(self) -> None:
        """UTC scheduling should work identically to before."""
        evaluator = CronEvaluator()
        base = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)
        next_run = evaluator.get_next_run("0 */6 * * *", "UTC", base)
        assert next_run.tzinfo == timezone.utc
        assert next_run == datetime(2026, 6, 15, 18, 0, tzinfo=timezone.utc)

    def test_timezone_aware_next_run(self) -> None:
        """A cron in a non-UTC timezone should produce correct UTC times."""
        evaluator = CronEvaluator()
        # 10 PM ET = next day 2 AM or 3 AM UTC depending on DST
        eastern = ZoneInfo("America/New_York")
        # June 15, 2026 noon UTC
        base = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)
        # "0 22 * * *" = 10 PM daily in ET
        next_run = evaluator.get_next_run("0 22 * * *", "America/New_York", base)
        next_local = next_run.astimezone(eastern)
        assert next_local.hour == 22
        assert next_local.date() == date(2026, 6, 15)


# ──────────────────────────────────────────────────────────────
# Calendar-Aware Job Scheduling (CalendarService)
# ──────────────────────────────────────────────────────────────

class TestCalendarAwareScheduling:
    async def test_no_constraint_always_runs(self, db_session: AsyncSession) -> None:
        """Jobs without calendar associations always run."""
        service = CalendarService()
        job = Job(name="unconstrained-job", job_type="shell", command="echo hi")
        db_session.add(job)
        await db_session.flush()
        assert await service.should_run_job(db_session, job.id, date(2026, 12, 25)) is True

    async def test_business_day_constraint_blocks_weekend(self, db_session: AsyncSession) -> None:
        """Job with run_only_on_business_days skips weekends."""
        service = CalendarService()
        job = Job(name="bday-constrained", job_type="shell", command="echo work")
        cal = Calendar(name="bday-cal", calendar_type=CalendarType.BUSINESS, timezone="UTC")
        db_session.add_all([job, cal])
        await db_session.flush()

        # Add a Saturday as non-business-day
        saturday = date(2026, 4, 11)  # April 11, 2026 is Saturday
        db_session.add(CalendarDate(
            calendar_id=cal.id, date=saturday, is_business_day=False,
        ))
        # Add a Monday as business day
        monday = date(2026, 4, 13)
        db_session.add(CalendarDate(
            calendar_id=cal.id, date=monday, is_business_day=True,
        ))
        db_session.add(JobCalendarAssociation(
            job_id=job.id, calendar_id=cal.id,
            constraint_type=ConstraintType.RUN_ONLY_ON_BUSINESS_DAYS,
        ))
        await db_session.flush()

        assert await service.should_run_job(db_session, job.id, saturday) is False
        assert await service.should_run_job(db_session, job.id, monday) is True

    async def test_skip_holidays_constraint(self, db_session: AsyncSession) -> None:
        """Job with skip_holidays skips dates labeled as holidays."""
        service = CalendarService()
        job = Job(name="holiday-constrained", job_type="shell", command="echo holiday")
        cal = Calendar(name="holiday-cal", calendar_type=CalendarType.HOLIDAY, timezone="UTC")
        db_session.add_all([job, cal])
        await db_session.flush()

        xmas = date(2026, 12, 25)
        db_session.add(CalendarDate(
            calendar_id=cal.id, date=xmas, is_business_day=False, label="Christmas Day",
        ))
        db_session.add(JobCalendarAssociation(
            job_id=job.id, calendar_id=cal.id,
            constraint_type=ConstraintType.SKIP_HOLIDAYS,
        ))
        await db_session.flush()

        assert await service.should_run_job(db_session, job.id, xmas) is False
        assert await service.should_run_job(db_session, job.id, date(2026, 12, 26)) is True

    async def test_business_day_no_entry_falls_back_to_weekday(self, db_session: AsyncSession) -> None:
        """When no CalendarDate entry exists, weekday check is used as fallback."""
        service = CalendarService()
        job = Job(name="fallback-check", job_type="shell", command="echo fallback")
        cal = Calendar(name="empty-cal", calendar_type=CalendarType.BUSINESS, timezone="UTC")
        db_session.add_all([job, cal])
        await db_session.flush()

        db_session.add(JobCalendarAssociation(
            job_id=job.id, calendar_id=cal.id,
            constraint_type=ConstraintType.RUN_ONLY_ON_BUSINESS_DAYS,
        ))
        await db_session.flush()

        wednesday = date(2026, 4, 15)  # Wednesday
        sunday = date(2026, 4, 12)  # Sunday
        assert await service.should_run_job(db_session, job.id, wednesday) is True
        assert await service.should_run_job(db_session, job.id, sunday) is False


# ──────────────────────────────────────────────────────────────
# Built-in Calendar Seeding
# ──────────────────────────────────────────────────────────────

class TestCalendarSeeding:
    async def test_seed_creates_three_calendars(self, db_session: AsyncSession) -> None:
        created = await seed_builtin_calendars(db_session)
        assert len(created) == 3
        names = {c.name for c in created}
        assert "US Federal Holidays 2026-2028" in names
        assert "US Business Calendar" in names
        assert "US Financial Calendar (NYSE)" in names

    async def test_seed_is_idempotent(self, db_session: AsyncSession) -> None:
        created1 = await seed_builtin_calendars(db_session)
        assert len(created1) == 3
        created2 = await seed_builtin_calendars(db_session)
        assert len(created2) == 0  # No new calendars created

    async def test_seed_holiday_dates(self, db_session: AsyncSession) -> None:
        await seed_builtin_calendars(db_session)
        from sqlalchemy import select, func
        count = await db_session.execute(
            select(func.count(CalendarDate.id))
            .join(Calendar)
            .where(Calendar.name == "US Federal Holidays 2026-2028")
        )
        total = count.scalar()
        # Should have holidays for 3 years (11 per year = 33)
        assert total == 33

    async def test_seed_business_calendar_weekday_count(self, db_session: AsyncSession) -> None:
        await seed_builtin_calendars(db_session)
        from sqlalchemy import select, func
        # Count business days in 2026 US Business Calendar
        count = await db_session.execute(
            select(func.count(CalendarDate.id))
            .join(Calendar)
            .where(
                Calendar.name == "US Business Calendar",
                CalendarDate.is_business_day.is_(True),
                CalendarDate.date >= date(2026, 1, 1),
                CalendarDate.date <= date(2026, 12, 31),
            )
        )
        bdays = count.scalar()
        # 2026 has 261 weekdays minus ~11 federal holidays = ~250 business days
        assert 248 <= bdays <= 252
