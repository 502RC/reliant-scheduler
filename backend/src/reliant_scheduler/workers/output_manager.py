"""Job output manager — uploads execution logs to Azure Blob Storage.

Streams combined stdout/stderr to a blob at
``job-outputs/{job_id}/{run_id}/output.log`` and returns the blob URL
so the JobRun record can store it in ``log_url``.

Falls back to a local-file strategy when no Azure Storage connection
string is configured (development mode).
"""

import os
from datetime import datetime, timezone

import structlog

from reliant_scheduler.core.config import settings

logger = structlog.get_logger(__name__)

_LOCAL_LOG_DIR = "/tmp/reliant-scheduler-logs"


async def upload_log(
    job_id: str,
    run_id: str,
    output: str,
    *,
    status: str = "",
    correlation_id: str = "",
) -> str:
    """Upload job output and return the log URL.

    Args:
        job_id: Job identifier.
        run_id: Run identifier.
        output: Combined stdout/stderr text.
        status: Final run status (for blob metadata).
        correlation_id: For structured logging.

    Returns:
        URL or local path of the stored log.
    """
    log = logger.bind(
        correlation_id=correlation_id,
        job_id=job_id,
        run_id=run_id,
    )

    blob_path = f"job-outputs/{job_id}/{run_id}/output.log"

    if settings.azure_storage_connection_string:
        return await _upload_to_blob(blob_path, output, job_id, run_id, status, log)

    return await _write_local(blob_path, output, log)


async def _upload_to_blob(
    blob_path: str,
    output: str,
    job_id: str,
    run_id: str,
    status: str,
    log: structlog.stdlib.BoundLogger,
) -> str:
    """Upload to Azure Blob Storage."""
    from azure.storage.blob.aio import BlobServiceClient

    async with BlobServiceClient.from_connection_string(
        settings.azure_storage_connection_string
    ) as blob_service:
        container_client = blob_service.get_container_client(
            settings.azure_storage_container
        )
        # Ensure container exists
        try:
            await container_client.create_container()
        except Exception:
            pass  # Container already exists

        blob_client = container_client.get_blob_client(blob_path)
        metadata = {
            "job_id": job_id,
            "run_id": run_id,
            "status": status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await blob_client.upload_blob(
            output.encode("utf-8"),
            overwrite=True,
            metadata=metadata,
        )
        log_url = blob_client.url
        log.info("log_uploaded_blob", blob_path=blob_path)
        return log_url


async def _write_local(
    blob_path: str,
    output: str,
    log: structlog.stdlib.BoundLogger,
) -> str:
    """Write to local filesystem (dev fallback)."""
    local_path = os.path.join(_LOCAL_LOG_DIR, blob_path)
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    with open(local_path, "w") as f:
        f.write(output)
    log.info("log_written_local", path=local_path)
    return f"file://{local_path}"
