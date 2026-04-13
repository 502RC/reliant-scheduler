"""Authentication endpoints: token exchange and current user profile."""

import uuid
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reliant_scheduler.core.config import settings
from reliant_scheduler.core.database import get_db
from reliant_scheduler.api.auth import get_current_user
from reliant_scheduler.models.user import User, UserRole, UserStatus, SecurityPolicy
from reliant_scheduler.schemas.user import (
    AuthMeResponse,
    AuthTokenRequest,
    AuthTokenResponse,
    UserResponse,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/token", response_model=AuthTokenResponse)
async def exchange_token(
    body: AuthTokenRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Exchange an Entra ID authorization code for an access token.

    In dev mode (no entra_client_id), returns a dev token.
    In prod, uses MSAL confidential client to exchange the code.
    """
    if not settings.entra_client_id:
        # Dev mode — return a mock token
        from reliant_scheduler.api.auth import DEV_USER_ID

        result = await db.execute(select(User).where(User.id == DEV_USER_ID))
        user = result.scalar_one_or_none()
        if not user:
            user = User(
                id=DEV_USER_ID,
                email="dev@reliant.local",
                display_name="Dev User",
                role=UserRole.SCHEDULER_ADMINISTRATOR,
                status=UserStatus.ACTIVE,
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)

        return {
            "access_token": "dev-token",
            "token_type": "bearer",
            "user": UserResponse.model_validate(user),
        }

    # Prod mode — exchange authorization code via MSAL
    try:
        import msal

        app = msal.ConfidentialClientApplication(
            settings.entra_client_id,
            authority=settings.entra_authority_url,
        )
        result = app.acquire_token_by_authorization_code(
            body.authorization_code,
            scopes=[f"api://{settings.entra_client_id}/.default"],
            redirect_uri=body.redirect_uri,
        )
    except Exception as exc:
        logger.error("msal_token_exchange_failed", error=str(exc))
        raise HTTPException(status_code=401, detail="Token exchange failed") from exc

    if "error" in result:
        raise HTTPException(status_code=401, detail=result.get("error_description", "Token exchange failed"))

    # Look up or create user from claims
    id_token_claims = result.get("id_token_claims", {})
    oid = id_token_claims.get("oid")
    if not oid:
        raise HTTPException(status_code=401, detail="Token missing oid claim")

    user_result = await db.execute(select(User).where(User.entra_object_id == oid))
    user = user_result.scalar_one_or_none()

    if user is None:
        email = id_token_claims.get("preferred_username", f"{oid}@entra.local")
        display_name = id_token_claims.get("name", email.split("@")[0])
        user = User(
            entra_object_id=oid,
            email=email,
            display_name=display_name,
            role=UserRole.INQUIRY,
            status=UserStatus.ACTIVE,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    return {
        "access_token": result["access_token"],
        "token_type": "bearer",
        "user": UserResponse.model_validate(user),
    }


@router.get("/me", response_model=AuthMeResponse)
async def get_me(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return the current user profile and effective permissions."""
    # Gather explicit policy permissions
    result = await db.execute(
        select(SecurityPolicy).where(
            SecurityPolicy.principal_type == "user",
            SecurityPolicy.principal_id == user.id,
        )
    )
    policies = result.scalars().all()
    permissions = [f"{p.permission}:{p.resource_type}" for p in policies]

    # Add role-implied permissions
    from reliant_scheduler.api.permissions import _ROLE_PERMISSIONS

    role_perms = _ROLE_PERMISSIONS.get(UserRole(user.role), set())
    for perm in role_perms:
        permissions.append(f"{perm}:*")

    return {
        "user": UserResponse.model_validate(user),
        "permissions": sorted(set(permissions)),
    }
