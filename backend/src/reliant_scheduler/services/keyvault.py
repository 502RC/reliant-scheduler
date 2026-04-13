"""Azure Key Vault service — centralized secret storage.

Provides get/set/delete operations for secrets stored in Azure Key Vault.
Falls back to an in-memory store when no Key Vault URL is configured (dev mode).
"""

import uuid

import structlog

from reliant_scheduler.core.config import settings

logger = structlog.get_logger(__name__)

# In-memory fallback for dev mode (no Key Vault configured)
_dev_store: dict[str, str] = {}


def generate_secret_name(credential_id: uuid.UUID, field_name: str) -> str:
    """Generate a deterministic Key Vault secret name.

    Format: reliant-cred-{short_uuid}-{field_name}
    Key Vault secret names allow alphanumeric and hyphens, 1-127 chars.
    """
    short_id = str(credential_id).replace("-", "")[:12]
    safe_field = field_name.replace("_", "-")
    return f"reliant-cred-{short_id}-{safe_field}"


async def get_secret(secret_name: str) -> str:
    """Retrieve a secret value by name."""
    if not settings.azure_keyvault_url:
        value = _dev_store.get(secret_name)
        if value is None:
            raise KeyError(f"Secret '{secret_name}' not found in dev store")
        return value

    from azure.identity.aio import DefaultAzureCredential
    from azure.keyvault.secrets.aio import SecretClient

    credential = DefaultAzureCredential()
    try:
        client = SecretClient(vault_url=settings.azure_keyvault_url, credential=credential)
        try:
            secret = await client.get_secret(secret_name)
            return secret.value
        finally:
            await client.close()
    finally:
        await credential.close()


async def set_secret(secret_name: str, value: str) -> str:
    """Store a secret in Key Vault. Returns the secret name."""
    if not settings.azure_keyvault_url:
        _dev_store[secret_name] = value
        logger.warning("secret_stored_in_memory", secret_name=secret_name,
                       reason="azure_keyvault_url not configured — NOT SECURE")
        return secret_name

    from azure.identity.aio import DefaultAzureCredential
    from azure.keyvault.secrets.aio import SecretClient

    credential = DefaultAzureCredential()
    try:
        client = SecretClient(vault_url=settings.azure_keyvault_url, credential=credential)
        try:
            await client.set_secret(secret_name, value)
            logger.info("secret_stored", secret_name=secret_name)
            return secret_name
        finally:
            await client.close()
    finally:
        await credential.close()


async def delete_secret(secret_name: str) -> None:
    """Delete (soft-delete) a secret from Key Vault."""
    if not settings.azure_keyvault_url:
        _dev_store.pop(secret_name, None)
        return

    from azure.identity.aio import DefaultAzureCredential
    from azure.keyvault.secrets.aio import SecretClient

    credential = DefaultAzureCredential()
    try:
        client = SecretClient(vault_url=settings.azure_keyvault_url, credential=credential)
        try:
            await client.begin_delete_secret(secret_name)
            logger.info("secret_deleted", secret_name=secret_name)
        finally:
            await client.close()
    finally:
        await credential.close()
