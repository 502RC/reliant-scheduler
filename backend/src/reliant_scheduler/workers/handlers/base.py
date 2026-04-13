"""Base class for connection-aware job handlers."""

import abc
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class HandlerResult:
    """Unified result from any connection handler execution."""

    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    duration_seconds: float = 0.0
    row_count: int | None = None
    bytes_transferred: int | None = None


class BaseHandler(abc.ABC):
    """Abstract base for all connection type handlers.

    Subclasses implement ``execute`` which receives the connection config
    (retrieved from the database) and the job command/parameters.
    Credentials are fetched from Azure Key Vault at runtime and never
    cached beyond the execution scope.
    """

    @abc.abstractmethod
    async def execute(
        self,
        *,
        command: str | None,
        parameters: dict | None,
        connection_config: dict,
        timeout_seconds: int,
        correlation_id: str,
        job_id: str,
        run_id: str,
    ) -> HandlerResult:
        """Execute the job against the connection.

        Args:
            command: Job command or query to execute.
            parameters: Job parameters / env vars.
            connection_config: Merged connection fields (host, port, extra).
            timeout_seconds: Max wall-clock time.
            correlation_id: For tracing.
            job_id: Job identifier.
            run_id: Run identifier.
        """

    @abc.abstractmethod
    async def test_connection(self, connection_config: dict) -> dict:
        """Test connectivity without running a job.

        Returns a dict with keys: ``status`` (``ok`` | ``error``),
        ``latency_ms``, ``message``, ``capabilities``.
        """
