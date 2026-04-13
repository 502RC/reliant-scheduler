"""Event-driven trigger service via Azure Event Hubs.

Listens for events and triggers jobs that have event-based schedules.
"""

import json

import structlog

from reliant_scheduler.core.config import settings

logger = structlog.get_logger(__name__)


class EventTrigger:
    """Processes Event Hub events and matches them to job triggers."""

    def __init__(self) -> None:
        self._use_eventhub = bool(settings.azure_eventhub_connection_string)

    def matches_filter(self, event_data: dict, event_filter: dict | None) -> bool:
        """Check if an event matches a schedule's event filter."""
        if not event_filter:
            return True
        for key, expected in event_filter.items():
            actual = event_data.get(key)
            if isinstance(expected, list):
                if actual not in expected:
                    return False
            elif actual != expected:
                return False
        return True

    async def start_listening(self, on_event: object) -> None:
        """Start consuming events from Event Hubs. No-op if not configured."""
        if not self._use_eventhub:
            logger.info("event_hubs_disabled")
            return

        from azure.eventhub.aio import EventHubConsumerClient

        client = EventHubConsumerClient.from_connection_string(
            settings.azure_eventhub_connection_string,
            consumer_group="$Default",
            eventhub_name=settings.azure_eventhub_name,
        )

        async def on_event_batch(partition_context, events):  # type: ignore[no-untyped-def]
            for event in events:
                try:
                    data = json.loads(event.body_as_str())
                    logger.info(
                        "event_received",
                        partition=partition_context.partition_id,
                        event_data=data,
                    )
                    if callable(on_event):
                        await on_event(data)  # type: ignore[misc]
                except Exception:
                    logger.exception("event_processing_error")
            await partition_context.update_checkpoint()

        logger.info("event_hub_consumer_starting")
        await client.receive_batch(on_event_batch=on_event_batch, starting_position="-1")
