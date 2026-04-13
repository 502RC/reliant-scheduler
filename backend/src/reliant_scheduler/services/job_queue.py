"""Job queue manager backed by Azure Service Bus.

Enqueues job runs for worker agents to pick up and provides a local
in-memory fallback for development without Azure.
"""

import json
import uuid
from dataclasses import dataclass, asdict

import structlog

from reliant_scheduler.core.config import settings

logger = structlog.get_logger(__name__)


@dataclass
class JobMessage:
    run_id: str
    job_id: str
    job_name: str
    command: str | None
    parameters: dict | None
    attempt_number: int
    timeout_seconds: int
    connection_id: str | None = None
    connection_type: str | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str) -> "JobMessage":
        return cls(**json.loads(data))


class JobQueue:
    """Sends job execution messages to Azure Service Bus or in-memory queue."""

    def __init__(self) -> None:
        self._local_queue: list[JobMessage] = []
        self._use_servicebus = bool(settings.azure_servicebus_connection_string)

    async def enqueue(self, message: JobMessage) -> None:
        if self._use_servicebus:
            await self._send_to_servicebus(message)
        else:
            logger.info(
                "job_enqueued_local",
                run_id=message.run_id,
                job_name=message.job_name,
            )
            self._local_queue.append(message)

    async def _send_to_servicebus(self, message: JobMessage) -> None:
        from azure.servicebus.aio import ServiceBusClient

        async with ServiceBusClient.from_connection_string(
            settings.azure_servicebus_connection_string
        ) as client:
            sender = client.get_queue_sender(queue_name=settings.azure_servicebus_queue_name)
            async with sender:
                from azure.servicebus import ServiceBusMessage
                sb_message = ServiceBusMessage(message.to_json())
                await sender.send_messages(sb_message)
                logger.info("job_enqueued_servicebus", run_id=message.run_id)

    def drain_local(self) -> list[JobMessage]:
        """Drain the in-memory queue (for testing/dev)."""
        messages = list(self._local_queue)
        self._local_queue.clear()
        return messages
