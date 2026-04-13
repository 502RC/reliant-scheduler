"""Security policy management API endpoints."""

import math
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from reliant_scheduler.core.database import get_db
from reliant_scheduler.api.auth import get_current_user
from reliant_scheduler.api.permissions import require_role
from reliant_scheduler.models.user import User, UserRole, SecurityPolicy
from reliant_scheduler.schemas.user import SecurityPolicyCreate, SecurityPolicyResponse

router = APIRouter(prefix="/api/security-policies", tags=["security-policies"])

VALID_RESOURCE_TYPES = {"job", "schedule", "connection", "calendar", "environment"}
VALID_PERMISSIONS = {"read", "write", "execute", "admin"}
VALID_PRINCIPAL_TYPES = {"user", "workgroup"}


@router.get("", response_model=dict)
async def list_security_policies(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    resource_type: str | None = None,
    principal_type: str | None = None,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role(UserRole.ADMINISTRATOR)),
) -> dict:
    query = select(SecurityPolicy)
    count_query = select(func.count(SecurityPolicy.id))
    if resource_type:
        query = query.where(SecurityPolicy.resource_type == resource_type)
        count_query = count_query.where(SecurityPolicy.resource_type == resource_type)
    if principal_type:
        query = query.where(SecurityPolicy.principal_type == principal_type)
        count_query = count_query.where(SecurityPolicy.principal_type == principal_type)

    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(
        query.order_by(SecurityPolicy.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    policies = result.scalars().all()
    return {
        "items": [SecurityPolicyResponse.model_validate(p).model_dump() for p in policies],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size) if total else 0,
    }


@router.get("/{policy_id}", response_model=SecurityPolicyResponse)
async def get_security_policy(
    policy_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role(UserRole.ADMINISTRATOR)),
) -> SecurityPolicy:
    result = await db.execute(select(SecurityPolicy).where(SecurityPolicy.id == policy_id))
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="Security policy not found")
    return policy


@router.post("", response_model=SecurityPolicyResponse, status_code=201)
async def create_security_policy(
    body: SecurityPolicyCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role(UserRole.ADMINISTRATOR)),
) -> SecurityPolicy:
    if body.resource_type not in VALID_RESOURCE_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid resource_type: {body.resource_type}")
    if body.permission not in VALID_PERMISSIONS:
        raise HTTPException(status_code=400, detail=f"Invalid permission: {body.permission}")
    if body.principal_type not in VALID_PRINCIPAL_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid principal_type: {body.principal_type}")

    policy = SecurityPolicy(**body.model_dump())
    db.add(policy)
    await db.commit()
    await db.refresh(policy)
    return policy


@router.delete("/{policy_id}", status_code=204)
async def delete_security_policy(
    policy_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role(UserRole.ADMINISTRATOR)),
) -> None:
    result = await db.execute(select(SecurityPolicy).where(SecurityPolicy.id == policy_id))
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="Security policy not found")
    await db.delete(policy)
    await db.commit()
