"""APM data stream publisher for Azure Event Hubs.

Mirrors the Tidal APM Data Stream pattern: streams operational metrics,
job lifecycle summaries, SLA events, and agent status to a dedicated
Event Hubs topic for downstream analytics and dashboards.

Falls back to structured log output when the APM Event Hubs connection
string is not configured (development mode).
"""

import json
from datetime import datetime, timezone
from typing import Any

import structlog

from reliant_scheduler.core.config import settings

logger = structlog.get_logger(__name__)


async def publish_apm_event(
    dataset: str,
    payload: dict[str, Any],
    *,
    correlation_id: str = "",
) -> None:
    """Publish an APM telemetry event.

    Args:
        dataset: Category of the APM data (e.g. "job_metrics", "sla_event",
                 "agent_status", "scheduler_health").
        payload: Arbitrary key/value data for the dataset.
        correlation_id: Optional tracing ID.
    """
    event = {
        "schema_version": "1.0",
        "dataset": dataset,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "correlation_id": correlation_id,
        **payload,
    }

    if settings.azure_apm_eventhub_connection_string:
        await _send_to_eventhub(event)
    else:
        logger.info("apm_event_local", dataset=dataset, correlation_id=correlation_id)


async def _send_to_eventhub(event: dict[str, Any]) -> None:
    """Send APM event to the dedicated Event Hubs topic."""
    try:
        from azure.eventhub import EventData
        from azure.eventhub.aio import EventHubProducerClient

        producer = EventHubProducerClient.from_connection_string(
            conn_str=settings.azure_apm_eventhub_connection_string,
            eventhub_name=settings.azure_apm_eventhub_name,
        )
        async with producer:
            batch = await producer.create_batch()
            batch.add(EventData(json.dumps(event)))
            await producer.send_batch(batch)
            logger.info("apm_event_published", dataset=event["dataset"])
    except Exception:
        logger.exception("apm_event_publish_failed", dataset=event.get("dataset", "unknown"))


async def publish_job_metrics(
    job_id: str,
    run_id: str,
    status: str,
    duration_seconds: float | None = None,
    *,
    correlation_id: str = "",
) -> None:
    """Convenience helper for job execution metrics."""
    await publish_apm_event(
        dataset="job_metrics",
        payload={
            "job_id": job_id,
            "run_id": run_id,
            "status": status,
            "duration_seconds": duration_seconds,
        },
        correlation_id=correlation_id,
    )


async def publish_sla_event(
    job_id: str,
    sla_status: str,
    *,
    breach_window: str = "",
    correlation_id: str = "",
) -> None:
    """Convenience helper for SLA breach/risk events."""
    await publish_apm_event(
        dataset="sla_event",
        payload={
            "job_id": job_id,
            "sla_status": sla_status,
            "breach_window": breach_window,
        },
        correlation_id=correlation_id,
    )


async def publish_agent_status(
    agent_id: str,
    status: str,
    hostname: str = "",
) -> None:
    """Convenience helper for agent status changes."""
    await publish_apm_event(
        dataset="agent_status",
        payload={
            "agent_id": agent_id,
            "status": status,
            "hostname": hostname,
        },
    )
