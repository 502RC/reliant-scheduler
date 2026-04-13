"""Publish job lifecycle events to Azure Event Hubs.

Emits structured events (started, completed, failed, timed_out) so
downstream APM and observability consumers can react in real time.

Falls back to structured log output when no Event Hubs connection
string is configured (development mode).
"""

import json
from datetime import datetime, timezone

import structlog

from reliant_scheduler.core.config import settings

logger = structlog.get_logger(__name__)


async def publish_lifecycle_event(
    event_type: str,
    job_id: str,
    run_id: str,
    *,
    agent_id: str = "",
    exit_code: int | None = None,
    error_message: str | None = None,
    duration_seconds: float | None = None,
    attempt_number: int = 1,
    correlation_id: str = "",
) -> None:
    """Publish a job lifecycle event.

    Args:
        event_type: One of "started", "completed", "failed", "timed_out".
        job_id: Job identifier.
        run_id: Run identifier.
        agent_id: Worker agent that processed the job.
        exit_code: Process exit code (if applicable).
        error_message: Error details (if applicable).
        duration_seconds: Execution wall-clock time.
        attempt_number: Which attempt this is.
        correlation_id: For tracing.
    """
    log = logger.bind(
        correlation_id=correlation_id,
        job_id=job_id,
        run_id=run_id,
        agent_id=agent_id,
    )

    event = {
        "event_type": f"job.{event_type}",
        "job_id": job_id,
        "run_id": run_id,
        "agent_id": agent_id,
        "exit_code": exit_code,
        "error_message": error_message,
        "duration_seconds": duration_seconds,
        "attempt_number": attempt_number,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Broadcast to WebSocket clients (in-process)
    try:
        from reliant_scheduler.api.routes.ws_events import publish_ws_event

        await publish_ws_event(
            event["event_type"],
            job_id,
            run_id,
            agent_id=agent_id,
            exit_code=exit_code,
            error_message=error_message,
            duration_seconds=duration_seconds,
            attempt_number=attempt_number,
            job_name="",
            previous_status=None,
            status=event_type,
        )
    except Exception:
        log.debug("ws_broadcast_skipped")

    if settings.azure_eventhub_connection_string:
        await _send_to_eventhub(event, log)
    else:
        log.info("lifecycle_event_local", event_type=event["event_type"])


async def _send_to_eventhub(
    event: dict,
    log: structlog.stdlib.BoundLogger,
) -> None:
    """Send event to Azure Event Hubs."""
    from azure.eventhub.aio import EventHubProducerClient
    from azure.eventhub import EventData

    producer = EventHubProducerClient.from_connection_string(
        conn_str=settings.azure_eventhub_connection_string,
        eventhub_name=settings.azure_eventhub_name,
    )
    async with producer:
        batch = await producer.create_batch()
        batch.add(EventData(json.dumps(event)))
        await producer.send_batch(batch)
        log.info("lifecycle_event_published", event_type=event["event_type"])
