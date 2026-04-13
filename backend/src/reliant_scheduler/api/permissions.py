"""Permission enforcement for FastAPI routes.

Provides a ``require_permission`` dependency factory that checks
whether the current user has the requested permission on a given
resource type.  The check follows the role hierarchy first (admins
bypass policy checks), then falls back to security_policies rows.
"""

import uuid
from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reliant_scheduler.core.database import get_db
from reliant_scheduler.api.auth import get_current_user
from reliant_scheduler.models.user import (
    User,
    UserRole,
    SecurityPolicy,
    WorkgroupMember,
    role_level,
)

# Permission implied by role level — roles at or above this level
# automatically have the listed permissions on ALL resource types.
_ROLE_PERMISSIONS: dict[UserRole, set[str]] = {
    UserRole.SCHEDULER_ADMINISTRATOR: {"read", "write", "execute", "admin"},
    UserRole.ADMINISTRATOR: {"read", "write", "execute", "admin"},
    UserRole.SCHEDULER: {"read", "write", "execute"},
    UserRole.OPERATOR: {"read", "execute"},
    UserRole.USER: {"read", "write"},
    UserRole.INQUIRY: {"read"},
}


def _role_has_permission(role: UserRole, permission: str) -> bool:
    """Check if a role inherently grants a permission."""
    return permission in _ROLE_PERMISSIONS.get(role, set())


async def _check_security_policies(
    db: AsyncSession,
    user: User,
    resource_type: str,
    permission: str,
    resource_id: uuid.UUID | None = None,
) -> bool:
    """Check security_policies table for an explicit grant.

    Checks both user-direct policies and workgroup-based policies.
    A policy with resource_id=NULL grants access to all resources of that type.
    """
    # Direct user policies
    query = select(SecurityPolicy).where(
        SecurityPolicy.principal_type == "user",
        SecurityPolicy.principal_id == user.id,
        SecurityPolicy.resource_type == resource_type,
        SecurityPolicy.permission == permission,
    )
    if resource_id:
        # Match wildcard (NULL resource_id) or specific resource
        query = query.where(
            (SecurityPolicy.resource_id == resource_id) | (SecurityPolicy.resource_id.is_(None))
        )
    result = await db.execute(query)
    if result.scalar_one_or_none():
        return True

    # Workgroup-based policies — get all workgroups the user belongs to
    wg_result = await db.execute(
        select(WorkgroupMember.workgroup_id).where(WorkgroupMember.user_id == user.id)
    )
    workgroup_ids = [row[0] for row in wg_result.all()]

    if workgroup_ids:
        wg_query = select(SecurityPolicy).where(
            SecurityPolicy.principal_type == "workgroup",
            SecurityPolicy.principal_id.in_(workgroup_ids),
            SecurityPolicy.resource_type == resource_type,
            SecurityPolicy.permission == permission,
        )
        if resource_id:
            wg_query = wg_query.where(
                (SecurityPolicy.resource_id == resource_id) | (SecurityPolicy.resource_id.is_(None))
            )
        wg_result = await db.execute(wg_query)
        if wg_result.scalar_one_or_none():
            return True

    return False


def require_permission(
    resource_type: str,
    permission: str,
) -> Callable:
    """FastAPI dependency factory for permission enforcement.

    Usage::

        @router.post("/api/jobs", dependencies=[Depends(require_permission("job", "write"))])
        async def create_job(...): ...

    Or inject the user too::

        async def create_job(user: User = Depends(require_permission("job", "write"))): ...
    """

    async def _enforce(
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        # Role-based shortcut: if the role inherently has the permission, allow
        if _role_has_permission(UserRole(user.role), permission):
            return user

        # Fall back to security policies
        if await _check_security_policies(db, user, resource_type, permission):
            return user

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied: {permission} on {resource_type}",
        )

    return _enforce


def require_role(min_role: UserRole) -> Callable:
    """Require the current user to have at least the given role level."""

    async def _enforce(user: User = Depends(get_current_user)) -> User:
        if role_level(UserRole(user.role)) < role_level(min_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role {min_role.value} or higher",
            )
        return user

    return _enforce
