import math
import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from reliant_scheduler.core.database import get_db
from reliant_scheduler.models.calendar import (
    Calendar,
    CalendarDate,
    CalendarRule,
    JobCalendarAssociation,
)
from reliant_scheduler.models.job import Job
from reliant_scheduler.schemas.calendar import (
    CalendarCreate,
    CalendarDateBulkCreate,
    CalendarDateCreate,
    CalendarDateResponse,
    CalendarResponse,
    CalendarRuleCreate,
    CalendarRuleResponse,
    CalendarUpdate,
    JobCalendarAssociationCreate,
    JobCalendarAssociationResponse,
)

router = APIRouter(prefix="/api/calendars", tags=["calendars"])


# ---- Calendar CRUD ----


@router.get("", response_model=dict)
async def list_calendars(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    calendar_type: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    query = select(Calendar)
    count_query = select(func.count(Calendar.id))
    if calendar_type:
        query = query.where(Calendar.calendar_type == calendar_type)
        count_query = count_query.where(Calendar.calendar_type == calendar_type)

    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(
        query.order_by(Calendar.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    calendars = result.scalars().all()
    return {
        "items": [CalendarResponse.model_validate(c).model_dump() for c in calendars],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size) if total else 0,
    }


@router.get("/{calendar_id}", response_model=CalendarResponse)
async def get_calendar(calendar_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Calendar:
    result = await db.execute(select(Calendar).where(Calendar.id == calendar_id))
    calendar = result.scalar_one_or_none()
    if not calendar:
        raise HTTPException(status_code=404, detail="Calendar not found")
    return calendar


@router.post("", response_model=CalendarResponse, status_code=201)
async def create_calendar(body: CalendarCreate, db: AsyncSession = Depends(get_db)) -> Calendar:
    calendar = Calendar(**body.model_dump())
    db.add(calendar)
    await db.commit()
    await db.refresh(calendar)
    return calendar


@router.patch("/{calendar_id}", response_model=CalendarResponse)
async def update_calendar(
    calendar_id: uuid.UUID, body: CalendarUpdate, db: AsyncSession = Depends(get_db)
) -> Calendar:
    result = await db.execute(select(Calendar).where(Calendar.id == calendar_id))
    calendar = result.scalar_one_or_none()
    if not calendar:
        raise HTTPException(status_code=404, detail="Calendar not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(calendar, field, value)
    await db.commit()
    await db.refresh(calendar)
    return calendar


@router.delete("/{calendar_id}", status_code=204)
async def delete_calendar(calendar_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> None:
    result = await db.execute(select(Calendar).where(Calendar.id == calendar_id))
    calendar = result.scalar_one_or_none()
    if not calendar:
        raise HTTPException(status_code=404, detail="Calendar not found")
    await db.delete(calendar)
    await db.commit()


# ---- Calendar Dates ----


@router.get("/{calendar_id}/dates", response_model=dict)
async def list_calendar_dates(
    calendar_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    year: int | None = None,
    month: int | None = None,
    is_business_day: bool | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    await _require_calendar(calendar_id, db)
    query = select(CalendarDate).where(CalendarDate.calendar_id == calendar_id)
    count_query = select(func.count(CalendarDate.id)).where(
        CalendarDate.calendar_id == calendar_id
    )
    if year is not None:
        start = date(year, 1, 1)
        end = date(year, 12, 31)
        query = query.where(CalendarDate.date >= start, CalendarDate.date <= end)
        count_query = count_query.where(CalendarDate.date >= start, CalendarDate.date <= end)
    if month is not None:
        if year is None:
            raise HTTPException(status_code=400, detail="year is required when filtering by month")
        start = date(year, month, 1)
        if month == 12:
            end = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end = date(year, month + 1, 1) - timedelta(days=1)
        query = query.where(CalendarDate.date >= start, CalendarDate.date <= end)
        count_query = count_query.where(CalendarDate.date >= start, CalendarDate.date <= end)
    if is_business_day is not None:
        query = query.where(CalendarDate.is_business_day == is_business_day)
        count_query = count_query.where(CalendarDate.is_business_day == is_business_day)

    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(
        query.order_by(CalendarDate.date).offset((page - 1) * page_size).limit(page_size)
    )
    dates = result.scalars().all()
    return {
        "items": [CalendarDateResponse.model_validate(d).model_dump() for d in dates],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size) if total else 0,
    }


@router.post("/{calendar_id}/dates", response_model=CalendarDateResponse, status_code=201)
async def create_calendar_date(
    calendar_id: uuid.UUID, body: CalendarDateCreate, db: AsyncSession = Depends(get_db)
) -> CalendarDate:
    await _require_calendar(calendar_id, db)
    cd = CalendarDate(calendar_id=calendar_id, **body.model_dump())
    db.add(cd)
    await db.commit()
    await db.refresh(cd)
    return cd


@router.post("/{calendar_id}/dates/bulk", response_model=dict, status_code=201)
async def bulk_create_calendar_dates(
    calendar_id: uuid.UUID, body: CalendarDateBulkCreate, db: AsyncSession = Depends(get_db)
) -> dict:
    """Generate dates for an entire year. Optionally marks weekdays as business days."""
    await _require_calendar(calendar_id, db)

    # Build a set of holiday dates from the request for quick lookup
    holiday_map: dict[date, CalendarDateCreate] = {h.date: h for h in body.holidays}

    created = 0
    current = date(body.year, 1, 1)
    end = date(body.year, 12, 31)
    while current <= end:
        if current in holiday_map:
            h = holiday_map[current]
            cd = CalendarDate(
                calendar_id=calendar_id,
                date=current,
                is_business_day=h.is_business_day,
                label=h.label,
            )
        else:
            is_weekday = current.weekday() < 5  # Mon-Fri
            is_bday = is_weekday if body.weekdays_only else True
            cd = CalendarDate(
                calendar_id=calendar_id,
                date=current,
                is_business_day=is_bday,
            )
        db.add(cd)
        created += 1
        current += timedelta(days=1)

    await db.commit()
    return {"created": created, "year": body.year}


# ---- Calendar Rules ----


@router.get("/{calendar_id}/rules", response_model=list[CalendarRuleResponse])
async def list_calendar_rules(
    calendar_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> list[CalendarRule]:
    await _require_calendar(calendar_id, db)
    result = await db.execute(
        select(CalendarRule)
        .where(CalendarRule.calendar_id == calendar_id)
        .order_by(CalendarRule.created_at)
    )
    return list(result.scalars().all())


@router.post("/{calendar_id}/rules", response_model=CalendarRuleResponse, status_code=201)
async def create_calendar_rule(
    calendar_id: uuid.UUID, body: CalendarRuleCreate, db: AsyncSession = Depends(get_db)
) -> CalendarRule:
    await _require_calendar(calendar_id, db)
    rule = CalendarRule(calendar_id=calendar_id, **body.model_dump())
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule


@router.delete("/{calendar_id}/rules/{rule_id}", status_code=204)
async def delete_calendar_rule(
    calendar_id: uuid.UUID, rule_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> None:
    await _require_calendar(calendar_id, db)
    result = await db.execute(
        select(CalendarRule).where(
            CalendarRule.id == rule_id, CalendarRule.calendar_id == calendar_id
        )
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Calendar rule not found")
    await db.delete(rule)
    await db.commit()


# ---- Where-used: jobs associated with this calendar ----


@router.get("/{calendar_id}/jobs", response_model=dict)
async def list_calendar_jobs(
    calendar_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Impact analysis: list all jobs associated with this calendar."""
    await _require_calendar(calendar_id, db)
    query = (
        select(Job)
        .join(JobCalendarAssociation, JobCalendarAssociation.job_id == Job.id)
        .where(JobCalendarAssociation.calendar_id == calendar_id)
    )
    count_query = (
        select(func.count(Job.id))
        .join(JobCalendarAssociation, JobCalendarAssociation.job_id == Job.id)
        .where(JobCalendarAssociation.calendar_id == calendar_id)
    )
    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(
        query.order_by(Job.name).offset((page - 1) * page_size).limit(page_size)
    )
    jobs = result.scalars().all()
    from reliant_scheduler.schemas.job import JobResponse

    return {
        "items": [JobResponse.model_validate(j).model_dump() for j in jobs],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size) if total else 0,
    }


# ---- Job-Calendar association (on jobs router path, but included here) ----

job_calendar_router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@job_calendar_router.get("/{job_id}/calendars", response_model=list[JobCalendarAssociationResponse])
async def list_job_calendars(
    job_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> list[JobCalendarAssociation]:
    await _require_job(job_id, db)
    result = await db.execute(
        select(JobCalendarAssociation).where(JobCalendarAssociation.job_id == job_id)
    )
    return list(result.scalars().all())


@job_calendar_router.post(
    "/{job_id}/calendars", response_model=JobCalendarAssociationResponse, status_code=201
)
async def associate_calendar_with_job(
    job_id: uuid.UUID,
    body: JobCalendarAssociationCreate,
    db: AsyncSession = Depends(get_db),
) -> JobCalendarAssociation:
    await _require_job(job_id, db)
    await _require_calendar(body.calendar_id, db)
    assoc = JobCalendarAssociation(job_id=job_id, **body.model_dump())
    db.add(assoc)
    await db.commit()
    await db.refresh(assoc)
    return assoc


@job_calendar_router.delete("/{job_id}/calendars/{association_id}", status_code=204)
async def remove_calendar_from_job(
    job_id: uuid.UUID, association_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> None:
    result = await db.execute(
        select(JobCalendarAssociation).where(
            JobCalendarAssociation.id == association_id,
            JobCalendarAssociation.job_id == job_id,
        )
    )
    assoc = result.scalar_one_or_none()
    if not assoc:
        raise HTTPException(status_code=404, detail="Job-calendar association not found")
    await db.delete(assoc)
    await db.commit()


# ---- Helpers ----


async def _require_calendar(calendar_id: uuid.UUID, db: AsyncSession) -> Calendar:
    result = await db.execute(select(Calendar).where(Calendar.id == calendar_id))
    calendar = result.scalar_one_or_none()
    if not calendar:
        raise HTTPException(status_code=404, detail="Calendar not found")
    return calendar


async def _require_job(job_id: uuid.UUID, db: AsyncSession) -> Job:
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
