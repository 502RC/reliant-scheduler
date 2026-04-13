"""Worker agent runtime — consumes job messages and executes them.

The WorkerAgent registers itself, listens on Azure Service Bus (or
drains the local in-memory queue in dev mode), executes commands via
the executor module, uploads logs, publishes lifecycle events, and
reports results back to the database.

Run as a standalone process::

    python -m reliant_scheduler.workers.agent
"""

import asyncio
import signal
import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from reliant_scheduler.core.config import settings
from reliant_scheduler.core.logging import setup_logging
from reliant_scheduler.models.agent import Agent, AgentStatus
from reliant_scheduler.models.connection import Connection
from reliant_scheduler.models.job import Job
from reliant_scheduler.models.job_run import JobRun, RunStatus
from reliant_scheduler.services.job_queue import JobMessage, JobQueue
from reliant_scheduler.services.retry_handler import RetryHandler
from reliant_scheduler.workers.executor import execute_command
from reliant_scheduler.workers.event_publisher import publish_lifecycle_event
from reliant_scheduler.workers.handlers import get_handler
from reliant_scheduler.workers.output_manager import upload_log

logger = structlog.get_logger(__name__)

HEARTBEAT_INTERVAL_SECONDS = 240  # 4 minutes (< 5-minute timeout)
POLL_INTERVAL_SECONDS = 5  # Local-mode queue drain interval


class WorkerAgent:
    """Service Bus consumer that executes jobs and reports results."""

    def __init__(
        self,
        hostname: str | None = None,
        max_concurrent_jobs: int = 4,
        labels: dict | None = None,
    ) -> None:
        import socket

        self.hostname = hostname or socket.gethostname()
        self.max_concurrent_jobs = max_concurrent_jobs
        self.labels = labels
        self.agent_id: uuid.UUID | None = None
        self._shutdown = asyncio.Event()
        self._active_jobs: int = 0
        self._semaphore = asyncio.Semaphore(max_concurrent_jobs)
        self._retry_handler = RetryHandler()
        self._session_factory: async_sessionmaker | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Boot the worker: register, start heartbeat, consume messages."""
        setup_logging()
        log = logger.bind(hostname=self.hostname)
        log.info("worker_starting")

        engine = create_async_engine(settings.database_url, echo=False, pool_size=5)
        self._session_factory = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )

        # Register self
        async with self._session_factory() as session:
            self.agent_id = await self._register(session)
            await session.commit()

        log.info("worker_registered", agent_id=str(self.agent_id))

        # Install signal handlers for graceful shutdown
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, self._request_shutdown)

        # Run heartbeat and consumer concurrently
        heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        consumer_task = asyncio.create_task(self._consume_loop())

        try:
            await self._shutdown.wait()
        finally:
            log.info("worker_draining")
            consumer_task.cancel()
            heartbeat_task.cancel()
            # Wait for in-flight jobs to finish
            while self._active_jobs > 0:
                await asyncio.sleep(0.5)
            # Mark agent draining/offline
            async with self._session_factory() as session:
                await self._set_status(session, AgentStatus.OFFLINE)
                await session.commit()
            await engine.dispose()
            log.info("worker_stopped")

    def _request_shutdown(self) -> None:
        logger.info("shutdown_requested")
        self._shutdown.set()

    # ------------------------------------------------------------------
    # Agent registration and heartbeat
    # ------------------------------------------------------------------

    async def _register(self, session: AsyncSession) -> uuid.UUID:
        """Register or re-register this agent."""
        result = await session.execute(
            select(Agent).where(Agent.hostname == self.hostname)
        )
        agent = result.scalar_one_or_none()
        now = datetime.now(timezone.utc)

        if agent:
            agent.status = AgentStatus.ONLINE
            agent.last_heartbeat_at = now
            agent.max_concurrent_jobs = self.max_concurrent_jobs
            if self.labels is not None:
                agent.labels = self.labels
        else:
            agent = Agent(
                hostname=self.hostname,
                status=AgentStatus.ONLINE,
                labels=self.labels,
                max_concurrent_jobs=self.max_concurrent_jobs,
                last_heartbeat_at=now,
            )
            session.add(agent)

        await session.flush()
        return agent.id

    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeats to keep the agent ONLINE."""
        while not self._shutdown.is_set():
            try:
                await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)
                if self._session_factory:
                    async with self._session_factory() as session:
                        result = await session.execute(
                            select(Agent).where(Agent.id == self.agent_id)
                        )
                        agent = result.scalar_one_or_none()
                        if agent:
                            agent.last_heartbeat_at = datetime.now(timezone.utc)
                            agent.status = AgentStatus.ONLINE
                            await session.commit()
                            logger.info(
                                "heartbeat_sent",
                                agent_id=str(self.agent_id),
                            )
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("heartbeat_error")

    async def _set_status(
        self, session: AsyncSession, status: AgentStatus
    ) -> None:
        result = await session.execute(
            select(Agent).where(Agent.id == self.agent_id)
        )
        agent = result.scalar_one_or_none()
        if agent:
            agent.status = status

    # ------------------------------------------------------------------
    # Message consumption
    # ------------------------------------------------------------------

    async def _consume_loop(self) -> None:
        """Route to Service Bus consumer or local poll loop."""
        try:
            if settings.azure_servicebus_connection_string:
                await self._consume_servicebus()
            else:
                await self._consume_local()
        except asyncio.CancelledError:
            pass

    async def _consume_servicebus(self) -> None:
        """Receive messages from Azure Service Bus."""
        from azure.servicebus.aio import ServiceBusClient

        async with ServiceBusClient.from_connection_string(
            settings.azure_servicebus_connection_string
        ) as client:
            receiver = client.get_queue_receiver(
                queue_name=settings.azure_servicebus_queue_name,
            )
            async with receiver:
                while not self._shutdown.is_set():
                    messages = await receiver.receive_messages(
                        max_message_count=1, max_wait_time=5
                    )
                    for msg in messages:
                        try:
                            job_msg = JobMessage.from_json(str(msg))
                            await self._semaphore.acquire()
                            asyncio.create_task(
                                self._process_and_release(job_msg)
                            )
                            await receiver.complete_message(msg)
                        except Exception:
                            logger.exception(
                                "message_processing_error",
                                agent_id=str(self.agent_id),
                            )
                            try:
                                await receiver.dead_letter_message(
                                    msg, reason="ProcessingError"
                                )
                            except Exception:
                                logger.exception("dead_letter_error")

    async def _consume_local(self) -> None:
        """Poll the database for pending runs (dev/local mode)."""
        logger.info("local_poll_starting")
        while not self._shutdown.is_set():
          try:
            async with self._session_factory() as session:
                result = await session.execute(
                    select(JobRun)
                    .where(JobRun.status == RunStatus.PENDING)
                    .order_by(JobRun.created_at)
                    .limit(self.max_concurrent_jobs)
                )
                pending_runs = result.scalars().all()
                logger.info("local_poll_tick", pending_count=len(pending_runs))
                for run in pending_runs:
                    job_result = await session.execute(
                        select(Job).where(Job.id == run.job_id)
                    )
                    job = job_result.scalar_one_or_none()
                    if not job:
                        continue
                    msg = JobMessage(
                        job_id=str(job.id),
                        run_id=str(run.id),
                        job_name=job.name,
                        command=job.command or "",
                        parameters=run.parameters or job.parameters or {},
                        timeout_seconds=job.timeout_seconds,
                        connection_id=str(job.connection_id) if job.connection_id else None,
                        attempt_number=run.attempt_number,
                    )
                    run.status = RunStatus.QUEUED
                    await session.commit()
                    await self._semaphore.acquire()
                    asyncio.create_task(self._process_and_release(msg))
          except Exception as poll_err:
                logger.error("local_poll_error", error=str(poll_err))
          await asyncio.sleep(POLL_INTERVAL_SECONDS)

    async def _process_and_release(self, message: JobMessage) -> None:
        """Execute job and release semaphore when done."""
        try:
            self._active_jobs += 1
            await self._process_message(message)
        finally:
            self._active_jobs -= 1
            self._semaphore.release()

    # ------------------------------------------------------------------
    # Job execution
    # ------------------------------------------------------------------

    async def _process_message(self, message: JobMessage) -> None:
        """Execute a single job message end-to-end."""
        correlation_id = str(uuid.uuid4())
        log = logger.bind(
            correlation_id=correlation_id,
            job_id=message.job_id,
            run_id=message.run_id,
            agent_id=str(self.agent_id),
            attempt_number=message.attempt_number,
        )
        log.info("job_execution_start")

        assert self._session_factory is not None

        # Mark run as RUNNING
        async with self._session_factory() as session:
            run = await self._get_run(session, message.run_id)
            if not run:
                log.error("run_not_found")
                return

            run.status = RunStatus.RUNNING
            run.agent_id = self.agent_id
            run.started_at = datetime.now(timezone.utc)
            await session.commit()

        # Publish started event
        await publish_lifecycle_event(
            "started",
            message.job_id,
            message.run_id,
            agent_id=str(self.agent_id),
            attempt_number=message.attempt_number,
            correlation_id=correlation_id,
        )

        # Dispatch: connection-aware handler or shell command
        if message.connection_id:
            await self._execute_via_connection(message, correlation_id, log)
        else:
            await self._execute_shell_command(message, correlation_id, log)

    async def _execute_shell_command(
        self,
        message: JobMessage,
        correlation_id: str,
        log: structlog.stdlib.BoundLogger,
    ) -> None:
        """Execute a job as a local shell command (legacy path)."""
        if not message.command:
            log.warning("job_no_command")
            await self._finalize_run(
                message,
                exit_code=0,
                stdout="(no command configured)",
                stderr="",
                timed_out=False,
                duration=0.0,
                correlation_id=correlation_id,
            )
            return

        result = await execute_command(
            command=message.command,
            timeout_seconds=message.timeout_seconds,
            parameters=message.parameters,
            correlation_id=correlation_id,
            job_id=message.job_id,
            run_id=message.run_id,
        )

        await self._finalize_run(
            message,
            exit_code=result.exit_code,
            stdout=result.stdout,
            stderr=result.stderr,
            timed_out=result.timed_out,
            duration=result.duration_seconds,
            correlation_id=correlation_id,
        )

    async def _execute_via_connection(
        self,
        message: JobMessage,
        correlation_id: str,
        log: structlog.stdlib.BoundLogger,
    ) -> None:
        """Execute a job via a connection-aware handler."""
        assert self._session_factory is not None

        # Look up the connection to get its type and config
        async with self._session_factory() as session:
            result = await session.execute(
                select(Connection).where(Connection.id == uuid.UUID(message.connection_id))
            )
            connection = result.scalar_one_or_none()

        if not connection:
            log.error("connection_not_found", connection_id=message.connection_id)
            await self._finalize_run(
                message,
                exit_code=-1,
                stdout="",
                stderr=f"Connection {message.connection_id} not found",
                timed_out=False,
                duration=0.0,
                correlation_id=correlation_id,
            )
            return

        connection_type = connection.connection_type
        log.info(
            "dispatching_to_handler",
            connection_type=connection_type,
            connection_id=message.connection_id,
        )

        try:
            handler = get_handler(connection_type)
        except KeyError:
            log.error("no_handler_for_connection_type", connection_type=connection_type)
            await self._finalize_run(
                message,
                exit_code=-1,
                stdout="",
                stderr=f"No handler for connection type: {connection_type}",
                timed_out=False,
                duration=0.0,
                correlation_id=correlation_id,
            )
            return

        # Build connection config dict from the Connection model
        connection_config = {
            "host": connection.host,
            "port": connection.port,
            "connection_type": connection.connection_type,
            "extra": connection.extra or {},
        }

        # Resolve credentials from Key Vault if credential_id is set
        if connection.credential_id:
            from reliant_scheduler.services.credential_resolver import resolve_credential
            async with self._session_factory() as cred_session:
                connection_config["resolved_credentials"] = await resolve_credential(
                    connection.credential_id, cred_session
                )

        handler_result = await handler.execute(
            command=message.command,
            parameters=message.parameters,
            connection_config=connection_config,
            timeout_seconds=message.timeout_seconds,
            correlation_id=correlation_id,
            job_id=message.job_id,
            run_id=message.run_id,
        )

        await self._finalize_run(
            message,
            exit_code=handler_result.exit_code,
            stdout=handler_result.stdout,
            stderr=handler_result.stderr,
            timed_out=handler_result.timed_out,
            duration=handler_result.duration_seconds,
            correlation_id=correlation_id,
        )

    async def _finalize_run(
        self,
        message: JobMessage,
        *,
        exit_code: int,
        stdout: str,
        stderr: str,
        timed_out: bool,
        duration: float,
        correlation_id: str,
    ) -> None:
        """Upload logs, update run status, publish event, trigger retry if needed."""
        log = logger.bind(
            correlation_id=correlation_id,
            job_id=message.job_id,
            run_id=message.run_id,
        )

        # Determine final status
        if timed_out:
            final_status = RunStatus.TIMED_OUT
            event_type = "timed_out"
        elif exit_code == 0:
            final_status = RunStatus.SUCCESS
            event_type = "completed"
        else:
            final_status = RunStatus.FAILED
            event_type = "failed"

        # Upload logs to Blob Storage
        combined_output = stdout
        if stderr:
            combined_output += f"\n--- STDERR ---\n{stderr}"

        log_url = await upload_log(
            job_id=message.job_id,
            run_id=message.run_id,
            output=combined_output,
            status=final_status.value,
            correlation_id=correlation_id,
        )

        # Update run in database
        error_message = None
        if final_status == RunStatus.TIMED_OUT:
            error_message = f"Job exceeded timeout of {message.timeout_seconds}s"
        elif final_status == RunStatus.FAILED:
            error_message = stderr[:4000] if stderr else f"Exited with code {exit_code}"

        assert self._session_factory is not None

        async with self._session_factory() as session:
            run = await self._get_run(session, message.run_id)
            if run:
                run.status = final_status
                run.finished_at = datetime.now(timezone.utc)
                run.exit_code = exit_code
                run.error_message = error_message
                run.log_url = log_url
                run.metrics = {
                    "duration_seconds": duration,
                    "stdout_bytes": len(stdout.encode()),
                    "stderr_bytes": len(stderr.encode()),
                }

                # Handle retry on failure
                if final_status in (RunStatus.FAILED, RunStatus.TIMED_OUT):
                    retry_run = await self._retry_handler.handle_failure(session, run)
                    if retry_run:
                        log.info(
                            "retry_created",
                            retry_run_id=str(retry_run.id),
                            next_attempt=retry_run.attempt_number,
                        )

                await session.commit()

        # Publish lifecycle event
        await publish_lifecycle_event(
            event_type,
            message.job_id,
            message.run_id,
            agent_id=str(self.agent_id),
            exit_code=exit_code,
            error_message=error_message,
            duration_seconds=duration,
            attempt_number=message.attempt_number,
            correlation_id=correlation_id,
        )

        log.info(
            "job_execution_complete",
            status=final_status.value,
            exit_code=exit_code,
            duration_seconds=duration,
        )

    async def _get_run(
        self, session: AsyncSession, run_id: str
    ) -> JobRun | None:
        result = await session.execute(
            select(JobRun).where(JobRun.id == uuid.UUID(run_id))
        )
        return result.scalar_one_or_none()


# ------------------------------------------------------------------
# Entrypoint
# ------------------------------------------------------------------


async def _main() -> None:
    agent = WorkerAgent()
    await agent.start()


if __name__ == "__main__":
    asyncio.run(_main())
