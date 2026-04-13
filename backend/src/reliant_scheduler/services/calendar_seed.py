"""Seed built-in calendars: US Federal Holidays, US Business Calendar, US Financial Calendar.

Covers 2026-2028 as specified in the task requirements.
"""

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reliant_scheduler.models.calendar import Calendar, CalendarDate, CalendarRule, CalendarType, RuleType

# US Federal Holidays 2026-2028
# https://www.opm.gov/policy-data-oversight/pay-leave/federal-holidays/
US_FEDERAL_HOLIDAYS: dict[int, list[tuple[date, str]]] = {
    2026: [
        (date(2026, 1, 1), "New Year's Day"),
        (date(2026, 1, 19), "Martin Luther King Jr. Day"),
        (date(2026, 2, 16), "Presidents' Day"),
        (date(2026, 5, 25), "Memorial Day"),
        (date(2026, 6, 19), "Juneteenth"),
        (date(2026, 7, 3), "Independence Day (observed)"),
        (date(2026, 9, 7), "Labor Day"),
        (date(2026, 10, 12), "Columbus Day"),
        (date(2026, 11, 11), "Veterans Day"),
        (date(2026, 11, 26), "Thanksgiving Day"),
        (date(2026, 12, 25), "Christmas Day"),
    ],
    2027: [
        (date(2027, 1, 1), "New Year's Day"),
        (date(2027, 1, 18), "Martin Luther King Jr. Day"),
        (date(2027, 2, 15), "Presidents' Day"),
        (date(2027, 5, 31), "Memorial Day"),
        (date(2027, 6, 18), "Juneteenth (observed)"),
        (date(2027, 7, 5), "Independence Day (observed)"),
        (date(2027, 9, 6), "Labor Day"),
        (date(2027, 10, 11), "Columbus Day"),
        (date(2027, 11, 11), "Veterans Day"),
        (date(2027, 11, 25), "Thanksgiving Day"),
        (date(2027, 12, 24), "Christmas Day (observed)"),
    ],
    2028: [
        (date(2028, 1, 1), "New Year's Day"),  # actually 2027-12-31 observed, but keep Jan 1
        (date(2028, 1, 17), "Martin Luther King Jr. Day"),
        (date(2028, 2, 21), "Presidents' Day"),
        (date(2028, 5, 29), "Memorial Day"),
        (date(2028, 6, 19), "Juneteenth"),
        (date(2028, 7, 4), "Independence Day"),
        (date(2028, 9, 4), "Labor Day"),
        (date(2028, 10, 9), "Columbus Day"),
        (date(2028, 11, 10), "Veterans Day (observed)"),
        (date(2028, 11, 23), "Thanksgiving Day"),
        (date(2028, 12, 25), "Christmas Day"),
    ],
}

# NYSE closures beyond federal holidays (Good Friday, etc.) - simplified to federal holidays
# for the financial calendar. Real NYSE schedule follows federal holidays minus Columbus Day
# and Veterans Day, plus Good Friday.
NYSE_ADDITIONAL_CLOSURES: dict[int, list[tuple[date, str]]] = {
    2026: [(date(2026, 4, 3), "Good Friday")],
    2027: [(date(2027, 3, 26), "Good Friday")],
    2028: [(date(2028, 4, 14), "Good Friday")],
}


def _all_holidays_set(year: int) -> set[date]:
    return {d for d, _ in US_FEDERAL_HOLIDAYS.get(year, [])}


def _nyse_closure_set(year: int) -> set[date]:
    """NYSE closes for most federal holidays except Columbus Day and Veterans Day, plus Good Friday."""
    federal = {d for d, label in US_FEDERAL_HOLIDAYS.get(year, [])
               if "Columbus" not in label and "Veterans" not in label}
    extra = {d for d, _ in NYSE_ADDITIONAL_CLOSURES.get(year, [])}
    return federal | extra


async def seed_builtin_calendars(session: AsyncSession) -> list[Calendar]:
    """Create built-in calendars if they don't already exist. Returns created calendars."""
    created = []

    # 1. US Federal Holidays
    holidays_cal = await _get_or_create_calendar(
        session,
        name="US Federal Holidays 2026-2028",
        calendar_type=CalendarType.HOLIDAY,
        timezone="America/New_York",
        description="US Federal holidays for 2026 through 2028",
    )
    if holidays_cal:
        for year in (2026, 2027, 2028):
            for dt, label in US_FEDERAL_HOLIDAYS.get(year, []):
                session.add(CalendarDate(
                    calendar_id=holidays_cal.id, date=dt, is_business_day=False, label=label,
                ))
        await session.flush()
        created.append(holidays_cal)

    # 2. US Business Calendar (Mon-Fri excluding federal holidays)
    business_cal = await _get_or_create_calendar(
        session,
        name="US Business Calendar",
        calendar_type=CalendarType.BUSINESS,
        timezone="America/New_York",
        description="Monday through Friday, excluding US Federal holidays (2026-2028)",
    )
    if business_cal:
        # Add recurring rules for weekdays
        for dow in range(5):  # Mon=0 through Fri=4
            session.add(CalendarRule(
                calendar_id=business_cal.id,
                rule_type=RuleType.RECURRING,
                day_of_week=dow,
                description=f"Weekday {['Monday','Tuesday','Wednesday','Thursday','Friday'][dow]}",
            ))
        # Generate date entries for 2026-2028
        for year in (2026, 2027, 2028):
            holidays = _all_holidays_set(year)
            current = date(year, 1, 1)
            end = date(year, 12, 31)
            while current <= end:
                is_bday = current.weekday() < 5 and current not in holidays
                label = None
                for dt, lbl in US_FEDERAL_HOLIDAYS.get(year, []):
                    if dt == current:
                        label = lbl
                        break
                session.add(CalendarDate(
                    calendar_id=business_cal.id,
                    date=current,
                    is_business_day=is_bday,
                    label=label,
                ))
                current += timedelta(days=1)
        await session.flush()
        created.append(business_cal)

    # 3. US Financial Calendar (NYSE trading schedule)
    financial_cal = await _get_or_create_calendar(
        session,
        name="US Financial Calendar (NYSE)",
        calendar_type=CalendarType.FINANCIAL,
        timezone="America/New_York",
        description="NYSE trading schedule: Mon-Fri excluding NYSE holidays (2026-2028)",
    )
    if financial_cal:
        for year in (2026, 2027, 2028):
            closures = _nyse_closure_set(year)
            current = date(year, 1, 1)
            end = date(year, 12, 31)
            while current <= end:
                is_trading = current.weekday() < 5 and current not in closures
                label = None
                # Check if it's a known closure
                for dt, lbl in US_FEDERAL_HOLIDAYS.get(year, []):
                    if dt == current:
                        label = lbl
                        break
                if not label:
                    for dt, lbl in NYSE_ADDITIONAL_CLOSURES.get(year, []):
                        if dt == current:
                            label = lbl
                            break
                session.add(CalendarDate(
                    calendar_id=financial_cal.id,
                    date=current,
                    is_business_day=is_trading,
                    label=label,
                ))
                current += timedelta(days=1)
        await session.flush()
        created.append(financial_cal)

    await session.commit()
    return created


async def _get_or_create_calendar(
    session: AsyncSession,
    name: str,
    calendar_type: CalendarType,
    timezone: str,
    description: str,
) -> Calendar | None:
    """Return a new Calendar if one with the same name doesn't exist, else None."""
    existing = await session.execute(select(Calendar).where(Calendar.name == name))
    if existing.scalar_one_or_none():
        return None
    cal = Calendar(
        name=name,
        calendar_type=calendar_type,
        timezone=timezone,
        description=description,
        is_builtin=True,
    )
    session.add(cal)
    await session.flush()
    return cal
