import uuid
import math
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from reliant_scheduler.core.database import get_db
from reliant_scheduler.models.job import Job
from reliant_scheduler.models.sla import SLAEvent, SLAJobConstraint, SLAPolicy
from reliant_scheduler.schemas.sla import (
    CriticalPathNode,
    CriticalPathResponse,
    SLAEventResponse,
    SLAJobConstraintCreate,
    SLAJobConstraintResponse,
    SLAPolicyCreate,
    SLAPolicyResponse,
    SLAPolicyUpdate,
    SLAStatusResponse,
)
from reliant_scheduler.services.sla_service import SLAService

router = APIRouter(prefix="/api/sla-policies", tags=["sla"])


# ---------------------------------------------------------------------------
# Policy CRUD
# ---------------------------------------------------------------------------


@router.get("", response_model=dict)
async def list_sla_policies(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> dict:
    count_query = select(func.count(SLAPolicy.id))
    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(
        select(SLAPolicy)
        .order_by(SLAPolicy.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    policies = result.scalars().all()
    return {
        "items": [SLAPolicyResponse.model_validate(p).model_dump() for p in policies],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size) if total else 0,
    }


@router.post("", response_model=SLAPolicyResponse, status_code=201)
async def create_sla_policy(
    body: SLAPolicyCreate, db: AsyncSession = Depends(get_db)
) -> SLAPolicy:
    policy = SLAPolicy(**body.model_dump())
    db.add(policy)
    await db.commit()
    await db.refresh(policy)
    return policy


@router.get("/{policy_id}", response_model=SLAPolicyResponse)
async def get_sla_policy(
    policy_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> SLAPolicy:
    result = await db.execute(select(SLAPolicy).where(SLAPolicy.id == policy_id))
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="SLA policy not found")
    return policy


@router.patch("/{policy_id}", response_model=SLAPolicyResponse)
async def update_sla_policy(
    policy_id: uuid.UUID,
    body: SLAPolicyUpdate,
    db: AsyncSession = Depends(get_db),
) -> SLAPolicy:
    result = await db.execute(select(SLAPolicy).where(SLAPolicy.id == policy_id))
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="SLA policy not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(policy, field, value)
    await db.commit()
    await db.refresh(policy)
    return policy


@router.delete("/{policy_id}", status_code=204)
async def delete_sla_policy(
    policy_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> None:
    result = await db.execute(select(SLAPolicy).where(SLAPolicy.id == policy_id))
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="SLA policy not found")
    await db.delete(policy)
    await db.commit()


# ---------------------------------------------------------------------------
# Job Constraints
# ---------------------------------------------------------------------------


@router.get("/{policy_id}/constraints", response_model=list[SLAJobConstraintResponse])
async def list_sla_constraints(
    policy_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> list[SLAJobConstraint]:
    # Verify policy exists
    policy_result = await db.execute(select(SLAPolicy).where(SLAPolicy.id == policy_id))
    if not policy_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="SLA policy not found")

    result = await db.execute(
        select(SLAJobConstraint).where(SLAJobConstraint.sla_policy_id == policy_id)
    )
    return list(result.scalars().all())


@router.post("/{policy_id}/constraints", response_model=SLAJobConstraintResponse, status_code=201)
async def add_sla_constraint(
    policy_id: uuid.UUID,
    body: SLAJobConstraintCreate,
    db: AsyncSession = Depends(get_db),
) -> SLAJobConstraint:
    # Verify policy exists
    policy_result = await db.execute(select(SLAPolicy).where(SLAPolicy.id == policy_id))
    if not policy_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="SLA policy not found")

    # Verify job exists
    job_result = await db.execute(select(Job).where(Job.id == body.job_id))
    if not job_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Job not found")

    constraint = SLAJobConstraint(
        sla_policy_id=policy_id,
        **body.model_dump(),
    )
    db.add(constraint)
    await db.commit()
    await db.refresh(constraint)
    return constraint


@router.delete("/{policy_id}/constraints/{constraint_id}", status_code=204)
async def remove_sla_constraint(
    policy_id: uuid.UUID,
    constraint_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(
        select(SLAJobConstraint).where(
            SLAJobConstraint.id == constraint_id,
            SLAJobConstraint.sla_policy_id == policy_id,
        )
    )
    constraint = result.scalar_one_or_none()
    if not constraint:
        raise HTTPException(status_code=404, detail="SLA constraint not found")
    await db.delete(constraint)
    await db.commit()


# ---------------------------------------------------------------------------
# Critical Path
# ---------------------------------------------------------------------------


@router.get("/{policy_id}/critical-path", response_model=CriticalPathResponse)
async def get_critical_path(
    policy_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> dict:
    # Verify policy exists
    policy_result = await db.execute(select(SLAPolicy).where(SLAPolicy.id == policy_id))
    if not policy_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="SLA policy not found")

    sla_service = SLAService()
    nodes, total_duration = await sla_service.compute_critical_path(db, policy_id)

    return {
        "sla_policy_id": policy_id,
        "path": [
            CriticalPathNode(
                job_id=n.job_id,
                job_name=n.job_name,
                estimated_duration_minutes=n.estimated_duration_minutes,
                dependencies=n.dependencies,
            ).model_dump()
            for n in nodes
        ],
        "total_duration_minutes": total_duration,
    }


# ---------------------------------------------------------------------------
# SLA Events
# ---------------------------------------------------------------------------


@router.get("/{policy_id}/events", response_model=dict)
async def list_sla_events(
    policy_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    event_type: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    # Verify policy exists
    policy_result = await db.execute(select(SLAPolicy).where(SLAPolicy.id == policy_id))
    if not policy_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="SLA policy not found")

    query = select(SLAEvent).where(SLAEvent.sla_policy_id == policy_id)
    count_query = select(func.count(SLAEvent.id)).where(SLAEvent.sla_policy_id == policy_id)

    if event_type:
        query = query.where(SLAEvent.event_type == event_type)
        count_query = count_query.where(SLAEvent.event_type == event_type)
    if start_date:
        query = query.where(SLAEvent.triggered_at >= start_date)
        count_query = count_query.where(SLAEvent.triggered_at >= start_date)
    if end_date:
        query = query.where(SLAEvent.triggered_at <= end_date)
        count_query = count_query.where(SLAEvent.triggered_at <= end_date)

    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(
        query.order_by(SLAEvent.triggered_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    events = result.scalars().all()
    return {
        "items": [SLAEventResponse.model_validate(e).model_dump() for e in events],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size) if total else 0,
    }


# ---------------------------------------------------------------------------
# SLA Status
# ---------------------------------------------------------------------------


@router.get("/{policy_id}/status", response_model=SLAStatusResponse)
async def get_sla_status(
    policy_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> dict:
    result = await db.execute(select(SLAPolicy).where(SLAPolicy.id == policy_id))
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="SLA policy not found")

    sla_service = SLAService()
    sla_status, estimated_completion, remaining = await sla_service.evaluate_sla_status(
        db, policy_id
    )

    return {
        "sla_policy_id": policy_id,
        "status": sla_status,
        "target_completion_time": policy.target_completion_time,
        "estimated_completion_time": estimated_completion,
        "remaining_duration_minutes": remaining,
        "risk_window_minutes": policy.risk_window_minutes,
        "breach_window_minutes": policy.breach_window_minutes,
    }
