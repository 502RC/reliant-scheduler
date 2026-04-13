"""Shell command executor with timeout enforcement and streaming output capture.

Spawns a subprocess for the job command, streams stdout/stderr to a log file
in real-time, enforces the configured timeout, and returns structured results.
"""

import asyncio
import os
from dataclasses import dataclass
from datetime import datetime, timezone

import structlog

logger = structlog.get_logger(__name__)

_LOCAL_LOG_DIR = "/tmp/reliant-scheduler-logs"


@dataclass
class ExecutionResult:
    """Result of a job command execution."""

    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool
    started_at: datetime
    finished_at: datetime
    duration_seconds: float


async def execute_command(
    command: str,
    timeout_seconds: int,
    parameters: dict | None = None,
    *,
    correlation_id: str = "",
    job_id: str = "",
    run_id: str = "",
) -> ExecutionResult:
    """Execute a shell command with timeout enforcement and streaming output capture.

    Output is written to a log file incrementally so the SSE endpoint can
    stream it to the UI in real-time while the command is still running.
    """
    env = None
    if parameters:
        env = {**os.environ, **{k: str(v) for k, v in parameters.items()}}

    log = logger.bind(
        correlation_id=correlation_id,
        job_id=job_id,
        run_id=run_id,
    )
    log.info("executor_start", command=command, timeout_seconds=timeout_seconds)

    # Prepare the log file for streaming output
    log_path = os.path.join(_LOCAL_LOG_DIR, f"job-outputs/{job_id}/{run_id}/output.log")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)

    started_at = datetime.now(timezone.utc)
    timed_out = False
    all_stdout: list[str] = []
    all_stderr: list[str] = []

    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        async def stream_pipe(pipe: asyncio.StreamReader, label: str, collector: list[str]) -> None:
            """Read lines from a pipe and append to log file in real-time."""
            while True:
                line = await pipe.readline()
                if not line:
                    break
                decoded = line.decode("utf-8", errors="replace")
                collector.append(decoded)
                with open(log_path, "a") as f:
                    if label == "stderr":
                        f.write(f"[STDERR] {decoded}")
                    else:
                        f.write(decoded)

        try:
            # Create an empty log file immediately so the UI knows it exists
            with open(log_path, "w") as f:
                pass

            stdout_task = asyncio.create_task(stream_pipe(proc.stdout, "stdout", all_stdout))
            stderr_task = asyncio.create_task(stream_pipe(proc.stderr, "stderr", all_stderr))

            await asyncio.wait_for(
                asyncio.gather(stdout_task, stderr_task, proc.wait()),
                timeout=timeout_seconds,
            )
        except asyncio.TimeoutError:
            timed_out = True
            log.warning("executor_timeout", timeout_seconds=timeout_seconds)
            proc.kill()
            await proc.wait()

        finished_at = datetime.now(timezone.utc)
        exit_code = proc.returncode if proc.returncode is not None else -1

        stdout = "".join(all_stdout)
        stderr = "".join(all_stderr)
        duration = (finished_at - started_at).total_seconds()

        log.info(
            "executor_finished",
            exit_code=exit_code,
            timed_out=timed_out,
            duration_seconds=duration,
        )

        return ExecutionResult(
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            timed_out=timed_out,
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=duration,
        )

    except Exception:
        finished_at = datetime.now(timezone.utc)
        duration = (finished_at - started_at).total_seconds()
        log.exception("executor_error")
        return ExecutionResult(
            exit_code=-1,
            stdout="",
            stderr="Failed to start subprocess",
            timed_out=False,
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=duration,
        )
