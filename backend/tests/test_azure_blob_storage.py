"""Integration tests for Azure Blob Storage service.

Uses Azurite emulator running in a container for real blob operations.
Tests job log upload/download, artifact storage, and container management.
"""

import os
import uuid

import pytest

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.azure,
]

# Azurite well-known connection string (standard for local dev/test)
AZURITE_CONNECTION_STRING = (
    "DefaultEndpointsProtocol=http;"
    "AccountName=devstoreaccount1;"
    "AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;"
    "BlobEndpoint=http://127.0.0.1:{port}/devstoreaccount1"
)


@pytest.fixture(scope="module")
def azurite_port():
    """Start Azurite blob service in a container and return the mapped port."""
    try:
        import docker
    except ImportError:
        pytest.skip("docker package not installed")

    host = os.environ.get("DOCKER_HOST", "")
    client = docker.DockerClient(base_url=host) if host else docker.from_env()

    container = client.containers.run(
        "mcr.microsoft.com/azure-storage/azurite",
        command="azurite-blob --blobHost 0.0.0.0 --blobPort 10000",
        ports={"10000/tcp": None},
        detach=True,
        remove=True,
    )
    try:
        container.reload()
        port = container.ports["10000/tcp"][0]["HostPort"]
        # Wait for readiness
        import time
        for _ in range(30):
            try:
                import urllib.request
                urllib.request.urlopen(f"http://127.0.0.1:{port}/devstoreaccount1", timeout=1)
                break
            except Exception:
                time.sleep(0.5)
        yield int(port)
    finally:
        container.stop(timeout=5)


@pytest.fixture
def blob_connection_string(azurite_port: int) -> str:
    return AZURITE_CONNECTION_STRING.format(port=azurite_port)


async def test_create_container_and_upload_blob(blob_connection_string: str) -> None:
    """Test creating a container and uploading a blob (job log)."""
    from azure.storage.blob.aio import BlobServiceClient

    container_name = f"test-logs-{uuid.uuid4().hex[:8]}"
    async with BlobServiceClient.from_connection_string(blob_connection_string) as service:
        container_client = service.get_container_client(container_name)
        await container_client.create_container()

        # Upload a job log
        log_content = b"2026-04-09T12:00:00Z INFO Job started\n2026-04-09T12:01:00Z INFO Job completed\n"
        blob_client = container_client.get_blob_client("runs/run-001/stdout.log")
        await blob_client.upload_blob(log_content)

        # Download and verify
        download = await blob_client.download_blob()
        data = await download.readall()
        assert data == log_content

        # Cleanup
        await container_client.delete_container()


async def test_upload_and_list_artifacts(blob_connection_string: str) -> None:
    """Test uploading multiple artifacts and listing them."""
    from azure.storage.blob.aio import BlobServiceClient

    container_name = f"test-artifacts-{uuid.uuid4().hex[:8]}"
    async with BlobServiceClient.from_connection_string(blob_connection_string) as service:
        container_client = service.get_container_client(container_name)
        await container_client.create_container()

        # Upload multiple artifacts
        artifacts = {
            "output/report.csv": b"col1,col2\nval1,val2",
            "output/summary.json": b'{"status": "success", "rows": 42}',
            "output/metrics.txt": b"execution_time=12.5s",
        }
        for name, content in artifacts.items():
            blob_client = container_client.get_blob_client(name)
            await blob_client.upload_blob(content)

        # List blobs under prefix
        blob_names = []
        async for blob in container_client.list_blobs(name_starts_with="output/"):
            blob_names.append(blob.name)
        assert sorted(blob_names) == sorted(artifacts.keys())

        # Cleanup
        await container_client.delete_container()


async def test_overwrite_blob(blob_connection_string: str) -> None:
    """Test overwriting an existing blob."""
    from azure.storage.blob.aio import BlobServiceClient

    container_name = f"test-overwrite-{uuid.uuid4().hex[:8]}"
    async with BlobServiceClient.from_connection_string(blob_connection_string) as service:
        container_client = service.get_container_client(container_name)
        await container_client.create_container()

        blob_client = container_client.get_blob_client("test.txt")
        await blob_client.upload_blob(b"version 1")

        # Overwrite
        await blob_client.upload_blob(b"version 2", overwrite=True)

        download = await blob_client.download_blob()
        data = await download.readall()
        assert data == b"version 2"

        await container_client.delete_container()


async def test_delete_blob(blob_connection_string: str) -> None:
    """Test deleting a blob."""
    from azure.storage.blob.aio import BlobServiceClient

    container_name = f"test-delete-{uuid.uuid4().hex[:8]}"
    async with BlobServiceClient.from_connection_string(blob_connection_string) as service:
        container_client = service.get_container_client(container_name)
        await container_client.create_container()

        blob_client = container_client.get_blob_client("ephemeral.txt")
        await blob_client.upload_blob(b"temporary data")
        await blob_client.delete_blob()

        # Verify it's gone
        from azure.core.exceptions import ResourceNotFoundError
        with pytest.raises(ResourceNotFoundError):
            await blob_client.download_blob()

        await container_client.delete_container()
