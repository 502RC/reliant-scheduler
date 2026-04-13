"""Credential management API endpoints."""

import math
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from reliant_scheduler.core.database import get_db
from reliant_scheduler.core.credential_templates import get_template, list_templates
from reliant_scheduler.models.credential import Credential
from reliant_scheduler.models.connection import Connection
from reliant_scheduler.schemas.credential import (
    CredentialCreate,
    CredentialUpdate,
    CredentialResponse,
    CredentialTemplateResponse,
    CredentialTemplateFieldResponse,
)
from reliant_scheduler.services import keyvault

router = APIRouter(prefix="/api/credentials", tags=["credentials"])


def _build_response(credential: Credential, usage_count: int = 0) -> dict:
    """Build a CredentialResponse dict from a Credential model. Never includes secrets."""
    return {
        "id": credential.id,
        "name": credential.name,
        "credential_type": credential.credential_type,
        "description": credential.description,
        "fields": credential.fields,
        "secret_fields": list((credential.secret_refs or {}).keys()),
        "usage_count": usage_count,
        "created_at": credential.created_at,
        "updated_at": credential.updated_at,
    }


@router.get("/templates", response_model=list[CredentialTemplateResponse])
async def list_credential_templates() -> list[dict]:
    """List all available credential type templates."""
    return [t.to_dict() for t in list_templates()]


@router.get("/templates/{credential_type}", response_model=CredentialTemplateResponse)
async def get_credential_template(credential_type: str) -> dict:
    """Get field definitions for a specific credential type."""
    template = get_template(credential_type)
    if not template:
        raise HTTPException(status_code=404, detail=f"Unknown credential type: {credential_type}")
    return template.to_dict()


@router.get("", response_model=dict)
async def list_credentials(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    credential_type: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    query = select(Credential)
    count_query = select(func.count(Credential.id))

    if credential_type:
        query = query.where(Credential.credential_type == credential_type)
        count_query = count_query.where(Credential.credential_type == credential_type)

    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(
        query.order_by(Credential.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    credentials = result.scalars().all()

    # Get usage counts for each credential
    items = []
    for cred in credentials:
        usage = (await db.execute(
            select(func.count(Connection.id)).where(Connection.credential_id == cred.id)
        )).scalar() or 0
        items.append(_build_response(cred, usage))

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size) if total else 0,
    }


@router.get("/{credential_id}", response_model=CredentialResponse)
async def get_credential(
    credential_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(Credential).where(Credential.id == credential_id))
    credential = result.scalar_one_or_none()
    if not credential:
        raise HTTPException(status_code=404, detail="Credential not found")

    usage = (await db.execute(
        select(func.count(Connection.id)).where(Connection.credential_id == credential.id)
    )).scalar() or 0

    return _build_response(credential, usage)


@router.post("", response_model=CredentialResponse, status_code=201)
async def create_credential(
    body: CredentialCreate,
    db: AsyncSession = Depends(get_db),
) -> dict:
    template = get_template(body.credential_type)
    if not template and body.credential_type != "custom":
        raise HTTPException(status_code=400, detail=f"Unknown credential type: {body.credential_type}")

    # Separate secret fields from non-secret fields
    secret_field_names = set(template.secret_field_names()) if template else set()
    non_secret_fields: dict = {}
    secret_values: dict = {}

    for key, value in body.fields.items():
        if key in secret_field_names:
            secret_values[key] = str(value)
        else:
            non_secret_fields[key] = value

    # For custom type, treat any field with "secret" or "password" in the name as secret
    if body.credential_type == "custom":
        for key, value in list(non_secret_fields.items()):
            if any(s in key.lower() for s in ("secret", "password", "token", "key", "private")):
                secret_values[key] = str(value)
                del non_secret_fields[key]

    # Create the credential record first to get the ID
    credential = Credential(
        name=body.name,
        credential_type=body.credential_type,
        description=body.description,
        fields=non_secret_fields if non_secret_fields else None,
        secret_refs={},
        created_by=None,  # TODO: get from auth context
    )
    db.add(credential)
    await db.flush()  # Get the ID without committing

    # Store each secret in Key Vault
    secret_refs: dict[str, str] = {}
    for field_name, value in secret_values.items():
        kv_name = keyvault.generate_secret_name(credential.id, field_name)
        await keyvault.set_secret(kv_name, value)
        secret_refs[field_name] = kv_name

    credential.secret_refs = secret_refs if secret_refs else None
    await db.commit()
    await db.refresh(credential)

    return _build_response(credential, 0)


@router.patch("/{credential_id}", response_model=CredentialResponse)
async def update_credential(
    credential_id: uuid.UUID,
    body: CredentialUpdate,
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(Credential).where(Credential.id == credential_id))
    credential = result.scalar_one_or_none()
    if not credential:
        raise HTTPException(status_code=404, detail="Credential not found")

    if body.name is not None:
        credential.name = body.name
    if body.description is not None:
        credential.description = body.description

    if body.fields is not None:
        template = get_template(credential.credential_type)
        secret_field_names = set(template.secret_field_names()) if template else set()

        # For custom type, infer secret fields
        if credential.credential_type == "custom":
            secret_field_names = {
                k for k in body.fields
                if any(s in k.lower() for s in ("secret", "password", "token", "key", "private"))
            }

        current_fields = credential.fields or {}
        current_refs = credential.secret_refs or {}

        for key, value in body.fields.items():
            if key in secret_field_names:
                # Update secret in Key Vault
                kv_name = current_refs.get(key) or keyvault.generate_secret_name(credential.id, key)
                await keyvault.set_secret(kv_name, str(value))
                current_refs[key] = kv_name
            else:
                current_fields[key] = value

        credential.fields = current_fields if current_fields else None
        credential.secret_refs = current_refs if current_refs else None

    await db.commit()
    await db.refresh(credential)

    usage = (await db.execute(
        select(func.count(Connection.id)).where(Connection.credential_id == credential.id)
    )).scalar() or 0

    return _build_response(credential, usage)


@router.delete("/{credential_id}", status_code=204)
async def delete_credential(
    credential_id: uuid.UUID,
    force: bool = Query(False),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(select(Credential).where(Credential.id == credential_id))
    credential = result.scalar_one_or_none()
    if not credential:
        raise HTTPException(status_code=404, detail="Credential not found")

    # Check usage
    usage_result = await db.execute(
        select(Connection.name).where(Connection.credential_id == credential.id)
    )
    connections_using = [row[0] for row in usage_result.all()]

    if connections_using and not force:
        raise HTTPException(
            status_code=409,
            detail={
                "message": f"Credential is used by {len(connections_using)} connection(s)",
                "connections": connections_using,
            },
        )

    # Delete secrets from Key Vault
    if credential.secret_refs:
        for kv_name in credential.secret_refs.values():
            try:
                await keyvault.delete_secret(kv_name)
            except Exception:
                pass  # Best-effort cleanup

    # Clear credential_id on any connections using this credential
    if connections_using:
        await db.execute(
            Connection.__table__.update()
            .where(Connection.credential_id == credential.id)
            .values(credential_id=None)
        )

    await db.delete(credential)
    await db.commit()


@router.get("/{credential_id}/usage", response_model=list[dict])
async def credential_usage(
    credential_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """List connections using this credential."""
    result = await db.execute(
        select(Connection.id, Connection.name, Connection.connection_type)
        .where(Connection.credential_id == credential_id)
    )
    return [
        {"id": str(row.id), "name": row.name, "connection_type": row.connection_type}
        for row in result.all()
    ]
