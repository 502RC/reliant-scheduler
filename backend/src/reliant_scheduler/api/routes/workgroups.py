"""Workgroup management API endpoints."""

import math
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from reliant_scheduler.core.database import get_db
from reliant_scheduler.api.auth import get_current_user
from reliant_scheduler.api.permissions import require_role
from reliant_scheduler.models.user import (
    User,
    UserRole,
    Workgroup,
    WorkgroupMember,
    WorkgroupRole,
)
from reliant_scheduler.schemas.user import (
    WorkgroupCreate,
    WorkgroupUpdate,
    WorkgroupResponse,
    WorkgroupMemberAdd,
    WorkgroupMemberResponse,
)

router = APIRouter(prefix="/api/workgroups", tags=["workgroups"])


@router.get("", response_model=dict)
async def list_workgroups(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    count_query = select(func.count(Workgroup.id))
    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(
        select(Workgroup)
        .order_by(Workgroup.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    workgroups = result.scalars().all()
    return {
        "items": [WorkgroupResponse.model_validate(w).model_dump() for w in workgroups],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size) if total else 0,
    }


@router.get("/{workgroup_id}", response_model=WorkgroupResponse)
async def get_workgroup(
    workgroup_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> Workgroup:
    result = await db.execute(select(Workgroup).where(Workgroup.id == workgroup_id))
    wg = result.scalar_one_or_none()
    if not wg:
        raise HTTPException(status_code=404, detail="Workgroup not found")
    return wg


@router.post("", response_model=WorkgroupResponse, status_code=201)
async def create_workgroup(
    body: WorkgroupCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role(UserRole.ADMINISTRATOR)),
) -> Workgroup:
    wg = Workgroup(**body.model_dump())
    db.add(wg)
    await db.commit()
    await db.refresh(wg)
    return wg


@router.patch("/{workgroup_id}", response_model=WorkgroupResponse)
async def update_workgroup(
    workgroup_id: uuid.UUID,
    body: WorkgroupUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role(UserRole.ADMINISTRATOR)),
) -> Workgroup:
    result = await db.execute(select(Workgroup).where(Workgroup.id == workgroup_id))
    wg = result.scalar_one_or_none()
    if not wg:
        raise HTTPException(status_code=404, detail="Workgroup not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(wg, field, value)
    await db.commit()
    await db.refresh(wg)
    return wg


@router.delete("/{workgroup_id}", status_code=204)
async def delete_workgroup(
    workgroup_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role(UserRole.ADMINISTRATOR)),
) -> None:
    result = await db.execute(select(Workgroup).where(Workgroup.id == workgroup_id))
    wg = result.scalar_one_or_none()
    if not wg:
        raise HTTPException(status_code=404, detail="Workgroup not found")
    await db.delete(wg)
    await db.commit()


# ------------------------------------------------------------------
# Workgroup member management
# ------------------------------------------------------------------


@router.get("/{workgroup_id}/members", response_model=list[WorkgroupMemberResponse])
async def list_workgroup_members(
    workgroup_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[WorkgroupMember]:
    # Verify workgroup exists
    result = await db.execute(select(Workgroup).where(Workgroup.id == workgroup_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Workgroup not found")

    result = await db.execute(
        select(WorkgroupMember).where(WorkgroupMember.workgroup_id == workgroup_id)
    )
    return list(result.scalars().all())


@router.post("/{workgroup_id}/members", response_model=WorkgroupMemberResponse, status_code=201)
async def add_workgroup_member(
    workgroup_id: uuid.UUID,
    body: WorkgroupMemberAdd,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role(UserRole.ADMINISTRATOR)),
) -> WorkgroupMember:
    # Verify workgroup exists
    result = await db.execute(select(Workgroup).where(Workgroup.id == workgroup_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Workgroup not found")

    # Verify user exists
    result = await db.execute(select(User).where(User.id == body.user_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="User not found")

    # Validate role
    try:
        WorkgroupRole(body.role)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid workgroup role: {body.role}")

    # Check for existing membership
    result = await db.execute(
        select(WorkgroupMember).where(
            WorkgroupMember.user_id == body.user_id,
            WorkgroupMember.workgroup_id == workgroup_id,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="User is already a member of this workgroup")

    member = WorkgroupMember(
        user_id=body.user_id,
        workgroup_id=workgroup_id,
        role=body.role,
    )
    db.add(member)
    await db.commit()
    await db.refresh(member)
    return member


@router.delete("/{workgroup_id}/members/{user_id}", status_code=204)
async def remove_workgroup_member(
    workgroup_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role(UserRole.ADMINISTRATOR)),
) -> None:
    result = await db.execute(
        select(WorkgroupMember).where(
            WorkgroupMember.user_id == user_id,
            WorkgroupMember.workgroup_id == workgroup_id,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Membership not found")
    await db.delete(member)
    await db.commit()
