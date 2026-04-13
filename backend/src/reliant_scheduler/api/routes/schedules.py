import math
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from reliant_scheduler.core.database import get_db
from reliant_scheduler.models.schedule import Schedule
from reliant_scheduler.schemas.schedule import ScheduleCreate, ScheduleUpdate, ScheduleResponse
from reliant_scheduler.services.cron_evaluator import CronEvaluator

router = APIRouter(prefix="/api/schedules", tags=["schedules"])


@router.get("", response_model=dict)
async def list_schedules(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    trigger_type: str | None = None,
    enabled: bool | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    query = select(Schedule)
    count_query = select(func.count(Schedule.id))
    if trigger_type:
        query = query.where(Schedule.trigger_type == trigger_type)
        count_query = count_query.where(Schedule.trigger_type == trigger_type)
    if enabled is not None:
        query = query.where(Schedule.enabled == enabled)
        count_query = count_query.where(Schedule.enabled == enabled)

    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(
        query.order_by(Schedule.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    schedules = result.scalars().all()
    return {
        "items": [ScheduleResponse.model_validate(s).model_dump() for s in schedules],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size) if total else 0,
    }


@router.get("/{schedule_id}", response_model=ScheduleResponse)
async def get_schedule(schedule_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Schedule:
    result = await db.execute(select(Schedule).where(Schedule.id == schedule_id))
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return schedule


@router.post("", response_model=ScheduleResponse, status_code=201)
async def create_schedule(body: ScheduleCreate, db: AsyncSession = Depends(get_db)) -> Schedule:
    data = body.model_dump()
    # Pre-compute next_run_at for cron schedules
    if body.trigger_type == "cron" and body.cron_expression:
        evaluator = CronEvaluator()
        data["next_run_at"] = evaluator.get_next_run(body.cron_expression, body.timezone)
    schedule = Schedule(**data)
    db.add(schedule)
    await db.commit()
    await db.refresh(schedule)
    return schedule


@router.patch("/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(
    schedule_id: uuid.UUID, body: ScheduleUpdate, db: AsyncSession = Depends(get_db)
) -> Schedule:
    result = await db.execute(select(Schedule).where(Schedule.id == schedule_id))
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(schedule, field, value)
    await db.commit()
    await db.refresh(schedule)
    return schedule


@router.delete("/{schedule_id}", status_code=204)
async def delete_schedule(schedule_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> None:
    result = await db.execute(select(Schedule).where(Schedule.id == schedule_id))
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    await db.delete(schedule)
    await db.commit()
