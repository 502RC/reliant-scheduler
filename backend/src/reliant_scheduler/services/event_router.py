"""Event router — matches events to bindings and dispatches actions.

Registered as a handler on the event emitter. When an event fires,
the router queries active bindings for the event type, evaluates
optional filters, and executes each bound action with retry.
"""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from reliant_scheduler.models.event_action import (
    ActionExecution,
    ActionExecutionStatus,
    EventActionBinding,
    EventType,
)
from reliant_scheduler.models.job import Job
from reliant_scheduler.models.job_run import JobRun, RunStatus
from reliant_scheduler.services.action_executor import execute_action, MAX_RECOVERY_DEPTH

logger = structlog.get_logger(__name__)

MAX_RETRY_ATTEMPTS = 3
RETRY_BASE_DELAY = 1.0  # seconds


class EventRouter:
    """Routes events to matching bindings and executes actions."""

    def __init__(self, session_factory: Any) -> None:
        """Initialize with a session factory for DB access.

        Parameters
        ----------
        session_factory:
            An async_sessionmaker that yields AsyncSession instances.
        """
        self._session_factory = session_factory

    async def handle_event(self, event_type_name: str, event_data: dict[str, Any]) -> None:
        """Process an emitted event: find matching bindings and execute actions."""
        async with self._session_factory() as session:
            await self._route_event(session, event_type_name, event_data)

    async def _route_event(
        self,
        session: AsyncSession,
        event_type_name: str,
        event_data: dict[str, Any],
    ) -> None:
        # Look up the event type
        result = await session.execute(
            select(EventType).where(EventType.name == event_type_name)
        )
        event_type = result.scalar_one_or_none()
        if not event_type:
            logger.debug("no_event_type_registered", event_type=event_type_name)
            return

        # Find enabled bindings for this event type
        bindings_result = await session.execute(
            select(EventActionBinding)
            .where(
                EventActionBinding.event_type_id == event_type.id,
                EventActionBinding.enabled.is_(True),
            )
            .options(selectinload(EventActionBinding.action))
        )
        bindings = list(bindings_result.scalars().all())

        if not bindings:
            return

        logger.info(
            "routing_event",
            event_type=event_type_name,
            binding_count=len(bindings),
        )

        # Execute actions in parallel via task group
        tasks = []
        for binding in bindings:
            if not self._matches_filter(event_data, binding.filter_json):
                continue
            tasks.append(
                self._execute_with_retry(session, binding, event_type_name, event_data)
            )

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
            await session.commit()

    def _matches_filter(self, event_data: dict, filter_json: dict | None) -> bool:
        """Check if event data matches an optional binding filter."""
        if not filter_json:
            return True
        for key, expected in filter_json.items():
            actual = event_data.get(key)
            if isinstance(expected, list):
                if actual not in expected:
                    return False
            elif actual != expected:
                return False
        return True

    async def _execute_with_retry(
        self,
        session: AsyncSession,
        binding: EventActionBinding,
        event_type_name: str,
        event_data: dict[str, Any],
    ) -> None:
        """Execute an action with exponential backoff retry."""
        action = binding.action
        if not action:
            return

        enriched_data = {**event_data, "event_type": event_type_name}

        for attempt in range(1, MAX_RETRY_ATTEMPTS + 1):
            success, error = await execute_action(
                action.type, action.config_json, enriched_data
            )

            if success:
                execution = ActionExecution(
                    event_action_binding_id=binding.id,
                    event_data_json=enriched_data,
                    status=ActionExecutionStatus.SENT,
                    attempt_number=attempt,
                )
                session.add(execution)

                # Handle recovery job creation if needed
                if action.type == "recovery_job":
                    await self._create_recovery_run(
                        session, action.config_json, enriched_data
                    )
                return

            if attempt < MAX_RETRY_ATTEMPTS:
                delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                logger.warning(
                    "action_retry",
                    action_id=str(action.id),
                    action_type=action.type,
                    attempt=attempt,
                    error=error,
                    next_delay=delay,
                )
                await asyncio.sleep(delay)

        # All retries exhausted — record failure
        execution = ActionExecution(
            event_action_binding_id=binding.id,
            event_data_json=enriched_data,
            status=ActionExecutionStatus.FAILED,
            error_message=error,
            attempt_number=MAX_RETRY_ATTEMPTS,
        )
        session.add(execution)
        logger.error(
            "action_permanently_failed",
            action_id=str(action.id),
            action_type=action.type,
            binding_id=str(binding.id),
            error=error,
        )

    async def _create_recovery_run(
        self,
        session: AsyncSession,
        config: dict[str, Any],
        event_data: dict[str, Any],
    ) -> None:
        """Create a job run for a recovery job action."""
        recovery_job_id = config.get("recovery_job_id")
        if not recovery_job_id:
            return

        current_depth = event_data.get("recovery_depth", 0)
        if current_depth >= MAX_RECOVERY_DEPTH:
            return

        try:
            job_uuid = uuid.UUID(recovery_job_id)
        except (ValueError, TypeError):
            logger.error("invalid_recovery_job_id", recovery_job_id=recovery_job_id)
            return

        # Verify the recovery job exists
        job_result = await session.execute(select(Job).where(Job.id == job_uuid))
        job = job_result.scalar_one_or_none()
        if not job:
            logger.error("recovery_job_not_found", recovery_job_id=recovery_job_id)
            return

        # Build parameters for the recovery run
        parameters = {}
        if config.get("pass_context", False):
            parameters = {
                "original_event": event_data,
                "recovery_depth": current_depth + 1,
            }
        else:
            parameters = {"recovery_depth": current_depth + 1}

        run = JobRun(
            job_id=job_uuid,
            status=RunStatus.PENDING,
            triggered_by="recovery",
            parameters=parameters,
        )
        session.add(run)
        logger.info(
            "recovery_run_created",
            job_id=recovery_job_id,
            job_name=job.name,
            depth=current_depth + 1,
        )
