"""Credential resolver — fetches credential fields with secrets decrypted from Key Vault.

Used by handlers at job execution time. Secrets are fetched fresh on each
call and NEVER cached beyond the scope of the call.
"""

import asyncio
import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reliant_scheduler.models.credential import Credential
from reliant_scheduler.services import keyvault

logger = structlog.get_logger(__name__)


async def resolve_credential(credential_id: uuid.UUID, session: AsyncSession) -> dict:
    """Resolve a credential into a flat dict with all fields (secrets decrypted).

    Returns a dict like:
    {"username": "svc_reliant", "password": "actual-secret-value", "domain": "CUROHS"}

    Secrets are fetched from Key Vault and never cached.
    """
    result = await session.execute(
        select(Credential).where(Credential.id == credential_id)
    )
    credential = result.scalar_one_or_none()
    if not credential:
        raise ValueError(f"Credential {credential_id} not found")

    logger.info(
        "credential_resolved",
        credential_id=str(credential_id),
        credential_name=credential.name,
        credential_type=credential.credential_type,
        secret_fields=list((credential.secret_refs or {}).keys()),
    )

    # Start with non-secret fields
    resolved: dict = dict(credential.fields or {})

    # Fetch all secrets from Key Vault in parallel
    secret_refs = credential.secret_refs or {}
    if secret_refs:
        kv_names = list(secret_refs.values())
        field_names = list(secret_refs.keys())

        secret_values = await asyncio.gather(
            *(keyvault.get_secret(name) for name in kv_names),
            return_exceptions=True,
        )

        for field_name, value in zip(field_names, secret_values):
            if isinstance(value, Exception):
                logger.error(
                    "credential_secret_fetch_failed",
                    credential_id=str(credential_id),
                    field_name=field_name,
                    error=str(value),
                )
                raise RuntimeError(
                    f"Failed to fetch secret '{field_name}' for credential "
                    f"'{credential.name}': {value}"
                )
            resolved[field_name] = value

    # Include credential metadata for handler convenience
    resolved["_credential_type"] = credential.credential_type
    resolved["_credential_name"] = credential.name

    return resolved
