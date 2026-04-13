"""Integration tests for Azure Key Vault secrets retrieval.

Tests the async Key Vault client pattern used for retrieving connection
strings and API keys. When running in CI without a real Key Vault, these
tests validate the client initialization and error handling patterns.

In production, DefaultAzureCredential is used. For testing, we validate
the SDK client construction and expected error handling.
"""

import pytest

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.azure,
]


async def test_keyvault_secret_client_construction() -> None:
    """Verify the async SecretClient can be instantiated with a vault URL."""
    from azure.keyvault.secrets.aio import SecretClient
    from azure.identity.aio import DefaultAzureCredential

    vault_url = "https://ghs-kv-reliant-prod-eus2-01.vault.azure.net/"
    credential = DefaultAzureCredential()

    # The client should construct without error even without network access
    client = SecretClient(vault_url=vault_url, credential=credential)
    assert client is not None
    assert client.vault_url == vault_url.rstrip("/")

    await credential.close()
    await client.close()


async def test_keyvault_credential_chain() -> None:
    """Verify DefaultAzureCredential can be created for the async path."""
    from azure.identity.aio import DefaultAzureCredential

    credential = DefaultAzureCredential()
    assert credential is not None
    await credential.close()


async def test_keyvault_secret_client_wrong_url_format() -> None:
    """Client construction with a bad vault URL should still succeed
    (errors surface on actual API calls, not construction)."""
    from azure.keyvault.secrets.aio import SecretClient
    from azure.identity.aio import DefaultAzureCredential

    credential = DefaultAzureCredential()
    client = SecretClient(vault_url="https://not-a-real-vault.vault.azure.net/", credential=credential)
    assert client is not None

    await credential.close()
    await client.close()
