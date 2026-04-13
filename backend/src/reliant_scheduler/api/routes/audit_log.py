"""Audit log query API endpoint."""

import math
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from reliant_scheduler.core.database import get_db
from reliant_scheduler.api.auth import get_current_user
from reliant_scheduler.api.permissions import require_role
from reliant_scheduler.models.user import User, UserRole, AuditLog
from reliant_scheduler.schemas.user import AuditLogResponse

router = APIRouter(prefix="/api/audit-log", tags=["audit-log"])


@router.get("", response_model=dict)
async def query_audit_log(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user_id: uuid.UUID | None = None,
    resource_type: str | None = None,
    action: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role(UserRole.ADMINISTRATOR)),
) -> dict:
    """Query the audit trail with optional filters."""
    query = select(AuditLog)
    count_query = select(func.count(AuditLog.id))

    if user_id:
        query = query.where(AuditLog.user_id == user_id)
        count_query = count_query.where(AuditLog.user_id == user_id)
    if resource_type:
        query = query.where(AuditLog.resource_type == resource_type)
        count_query = count_query.where(AuditLog.resource_type == resource_type)
    if action:
        query = query.where(AuditLog.action == action)
        count_query = count_query.where(AuditLog.action == action)
    if start_date:
        query = query.where(AuditLog.timestamp >= start_date)
        count_query = count_query.where(AuditLog.timestamp >= start_date)
    if end_date:
        query = query.where(AuditLog.timestamp <= end_date)
        count_query = count_query.where(AuditLog.timestamp <= end_date)

    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(
        query.order_by(AuditLog.timestamp.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    entries = result.scalars().all()
    return {
        "items": [AuditLogResponse.model_validate(e).model_dump() for e in entries],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size) if total else 0,
    }
