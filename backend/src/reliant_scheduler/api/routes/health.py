"""Health check endpoints with dependency verification.

``/healthz`` is the comprehensive health endpoint.  It verifies
connectivity to PostgreSQL, Azure Service Bus, Blob Storage, Key Vault,
and Event Hubs.  Returns 200 only when all checks pass; 503 otherwise.

``/livez`` is a lightweight liveness probe for Kubernetes that always
returns 200 (the process is alive).

``/readyz`` mirrors ``/healthz`` for Kubernetes readiness gates.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import structlog
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from reliant_scheduler.core.config import settings
from reliant_scheduler.core.database import get_db
from reliant_scheduler.core.metrics import HEALTH_CHECK_STATUS

router = APIRouter(tags=["health"])
logger = structlog.get_logger(__name__)

HEALTH_CHECK_TIMEOUT = 5.0  # seconds


async def _check_postgres(db: AsyncSession) -> dict[str, Any]:
    """Verify PostgreSQL connectivity via a simple query."""
    start = time.perf_counter()
    try:
        await asyncio.wait_for(db.execute(text("SELECT 1")), timeout=HEALTH_CHECK_TIMEOUT)
        latency = round(time.perf_counter() - start, 4)
        HEALTH_CHECK_STATUS.labels(dependency="postgresql").set(1)
        return {"status": "healthy", "latency_seconds": latency}
    except asyncio.TimeoutError:
        HEALTH_CHECK_STATUS.labels(dependency="postgresql").set(0)
        logger.warning("health_check_timeout", dependency="postgresql")
        return {"status": "unhealthy", "error": "timeout"}
    except Exception as exc:
        HEALTH_CHECK_STATUS.labels(dependency="postgresql").set(0)
        logger.warning("health_check_failed", dependency="postgresql", error=str(exc))
        return {"status": "unhealthy", "error": str(exc)}


async def _check_service_bus() -> dict[str, Any]:
    """Verify Azure Service Bus namespace reachability using Managed Identity."""
    if not settings.azure_servicebus_namespace:
        HEALTH_CHECK_STATUS.labels(dependency="servicebus").set(1)
        return {"status": "skipped", "reason": "not configured"}
    start = time.perf_counter()
    try:
        from azure.identity.aio import DefaultAzureCredential
        from azure.servicebus.aio import ServiceBusClient

        credential = DefaultAzureCredential()
        try:
            fqns = f"{settings.azure_servicebus_namespace}.servicebus.windows.net"
            async with ServiceBusClient(fqns, credential=credential) as client:
                receiver = client.get_queue_receiver(
                    queue_name=settings.azure_servicebus_queue_name,
                    max_wait_time=1,
                )
                async with receiver:
                    pass  # connection success is enough
        finally:
            await credential.close()
        latency = round(time.perf_counter() - start, 4)
        HEALTH_CHECK_STATUS.labels(dependency="servicebus").set(1)
        return {"status": "healthy", "latency_seconds": latency}
    except Exception as exc:
        HEALTH_CHECK_STATUS.labels(dependency="servicebus").set(0)
        logger.warning("health_check_failed", dependency="servicebus", error=str(exc))
        return {"status": "unhealthy", "error": str(exc)}


async def _check_blob_storage() -> dict[str, Any]:
    """Verify Azure Blob Storage container access using Managed Identity."""
    if not settings.azure_storage_account_name:
        HEALTH_CHECK_STATUS.labels(dependency="blob_storage").set(1)
        return {"status": "skipped", "reason": "not configured"}
    start = time.perf_counter()
    try:
        from azure.identity.aio import DefaultAzureCredential
        from azure.storage.blob.aio import BlobServiceClient

        credential = DefaultAzureCredential()
        try:
            account_url = f"https://{settings.azure_storage_account_name}.blob.core.windows.net"
            async with BlobServiceClient(account_url, credential=credential) as client:
                container = client.get_container_client(settings.azure_storage_container)
                await asyncio.wait_for(
                    container.get_container_properties(), timeout=HEALTH_CHECK_TIMEOUT
                )
        finally:
            await credential.close()
        latency = round(time.perf_counter() - start, 4)
        HEALTH_CHECK_STATUS.labels(dependency="blob_storage").set(1)
        return {"status": "healthy", "latency_seconds": latency}
    except asyncio.TimeoutError:
        HEALTH_CHECK_STATUS.labels(dependency="blob_storage").set(0)
        logger.warning("health_check_timeout", dependency="blob_storage")
        return {"status": "unhealthy", "error": "timeout"}
    except Exception as exc:
        HEALTH_CHECK_STATUS.labels(dependency="blob_storage").set(0)
        logger.warning("health_check_failed", dependency="blob_storage", error=str(exc))
        return {"status": "unhealthy", "error": str(exc)}


async def _check_key_vault() -> dict[str, Any]:
    """Verify Azure Key Vault secret retrieval using Managed Identity."""
    if not settings.azure_keyvault_url:
        HEALTH_CHECK_STATUS.labels(dependency="keyvault").set(1)
        return {"status": "skipped", "reason": "not configured"}
    start = time.perf_counter()
    try:
        from azure.identity.aio import DefaultAzureCredential
        from azure.keyvault.secrets.aio import SecretClient

        credential = DefaultAzureCredential()
        try:
            client = SecretClient(vault_url=settings.azure_keyvault_url, credential=credential)
            try:
                # List secrets is sufficient to verify access; we don't need to fetch one
                list_coro = client.list_properties_of_secrets().__anext__()
                try:
                    await asyncio.wait_for(list_coro, timeout=HEALTH_CHECK_TIMEOUT)
                except StopAsyncIteration:
                    pass  # empty vault is fine
            finally:
                await client.close()
        finally:
            await credential.close()
        latency = round(time.perf_counter() - start, 4)
        HEALTH_CHECK_STATUS.labels(dependency="keyvault").set(1)
        return {"status": "healthy", "latency_seconds": latency}
    except asyncio.TimeoutError:
        HEALTH_CHECK_STATUS.labels(dependency="keyvault").set(0)
        logger.warning("health_check_timeout", dependency="keyvault")
        return {"status": "unhealthy", "error": "timeout"}
    except Exception as exc:
        HEALTH_CHECK_STATUS.labels(dependency="keyvault").set(0)
        logger.warning("health_check_failed", dependency="keyvault", error=str(exc))
        return {"status": "unhealthy", "error": str(exc)}


async def _check_event_hubs() -> dict[str, Any]:
    """Verify Event Hubs producer connectivity using Managed Identity."""
    if not settings.azure_eventhub_namespace:
        HEALTH_CHECK_STATUS.labels(dependency="eventhubs").set(1)
        return {"status": "skipped", "reason": "not configured"}
    start = time.perf_counter()
    try:
        from azure.identity.aio import DefaultAzureCredential
        from azure.eventhub.aio import EventHubProducerClient

        credential = DefaultAzureCredential()
        try:
            fqns = f"{settings.azure_eventhub_namespace}.servicebus.windows.net"
            producer = EventHubProducerClient(
                fully_qualified_namespace=fqns,
                eventhub_name=settings.azure_eventhub_name,
                credential=credential,
            )
            async with producer:
                info = await asyncio.wait_for(
                    producer.get_eventhub_properties(), timeout=HEALTH_CHECK_TIMEOUT
                )
                _ = info["name"]
        finally:
            await credential.close()
        latency = round(time.perf_counter() - start, 4)
        HEALTH_CHECK_STATUS.labels(dependency="eventhubs").set(1)
        return {"status": "healthy", "latency_seconds": latency}
    except asyncio.TimeoutError:
        HEALTH_CHECK_STATUS.labels(dependency="eventhubs").set(0)
        logger.warning("health_check_timeout", dependency="eventhubs")
        return {"status": "unhealthy", "error": "timeout"}
    except Exception as exc:
        HEALTH_CHECK_STATUS.labels(dependency="eventhubs").set(0)
        logger.warning("health_check_failed", dependency="eventhubs", error=str(exc))
        return {"status": "unhealthy", "error": str(exc)}


async def _run_all_checks(db: AsyncSession) -> dict[str, Any]:
    """Execute all dependency checks and return aggregate result."""
    checks = {
        "postgresql": await _check_postgres(db),
        "servicebus": await _check_service_bus(),
        "blob_storage": await _check_blob_storage(),
        "keyvault": await _check_key_vault(),
        "eventhubs": await _check_event_hubs(),
    }
    all_healthy = all(
        c["status"] in ("healthy", "skipped") for c in checks.values()
    )
    return {
        "status": "healthy" if all_healthy else "unhealthy",
        "checks": checks,
    }


@router.get("/healthz")
async def healthz(db: AsyncSession = Depends(get_db)) -> JSONResponse:
    """Comprehensive health check — verifies all backend dependencies."""
    result = await _run_all_checks(db)
    status_code = 200 if result["status"] == "healthy" else 503
    return JSONResponse(content=result, status_code=status_code)


@router.get("/livez")
async def livez() -> dict[str, str]:
    """Kubernetes liveness probe — always returns OK if the process is alive."""
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(db: AsyncSession = Depends(get_db)) -> JSONResponse:
    """Kubernetes readiness probe — mirrors /healthz."""
    result = await _run_all_checks(db)
    status_code = 200 if result["status"] == "healthy" else 503
    return JSONResponse(content=result, status_code=status_code)
