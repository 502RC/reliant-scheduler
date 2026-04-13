"""User management API endpoints."""

import math
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from reliant_scheduler.core.database import get_db
from reliant_scheduler.api.auth import get_current_user
from reliant_scheduler.api.permissions import require_role
from reliant_scheduler.models.user import User, UserRole, UserStatus
from reliant_scheduler.schemas.user import UserCreate, UserUpdate, UserResponse

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=dict)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    role: str | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    query = select(User)
    count_query = select(func.count(User.id))
    if role:
        query = query.where(User.role == role)
        count_query = count_query.where(User.role == role)
    if status:
        query = query.where(User.status == status)
        count_query = count_query.where(User.status == status)

    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(
        query.order_by(User.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    users = result.scalars().all()
    return {
        "items": [UserResponse.model_validate(u).model_dump() for u in users],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size) if total else 0,
    }


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post("", response_model=UserResponse, status_code=201)
async def create_user(
    body: UserCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role(UserRole.ADMINISTRATOR)),
) -> User:
    # Validate role value
    try:
        UserRole(body.role)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid role: {body.role}")

    user = User(**body.model_dump())
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    body: UserUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role(UserRole.ADMINISTRATOR)),
) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = body.model_dump(exclude_unset=True)
    if "role" in update_data:
        try:
            UserRole(update_data["role"])
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid role: {update_data['role']}")
    if "status" in update_data:
        try:
            UserStatus(update_data["status"])
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {update_data['status']}")

    for field, value in update_data.items():
        setattr(user, field, value)
    await db.commit()
    await db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=204)
async def delete_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role(UserRole.ADMINISTRATOR)),
) -> None:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await db.delete(user)
    await db.commit()
