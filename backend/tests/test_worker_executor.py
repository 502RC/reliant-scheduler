"""Integration tests for the worker executor module.

Tests run real subprocesses — no mocks.
"""

import pytest

from reliant_scheduler.workers.executor import ExecutionResult, execute_command


@pytest.mark.asyncio
async def test_execute_successful_command() -> None:
    """A simple echo command should succeed with exit code 0."""
    result = await execute_command(
        command='echo "hello world"',
        timeout_seconds=10,
        correlation_id="test-success",
        job_id="j1",
        run_id="r1",
    )
    assert isinstance(result, ExecutionResult)
    assert result.exit_code == 0
    assert "hello world" in result.stdout
    assert result.timed_out is False
    assert result.duration_seconds >= 0
    assert result.started_at <= result.finished_at


@pytest.mark.asyncio
async def test_execute_failing_command() -> None:
    """A command that exits non-zero should capture the exit code."""
    result = await execute_command(
        command="exit 42",
        timeout_seconds=10,
        correlation_id="test-fail",
        job_id="j2",
        run_id="r2",
    )
    assert result.exit_code == 42
    assert result.timed_out is False


@pytest.mark.asyncio
async def test_execute_captures_stderr() -> None:
    """stderr output should be captured separately."""
    result = await execute_command(
        command='echo "out" && echo "err" >&2',
        timeout_seconds=10,
        correlation_id="test-stderr",
        job_id="j3",
        run_id="r3",
    )
    assert result.exit_code == 0
    assert "out" in result.stdout
    assert "err" in result.stderr


@pytest.mark.asyncio
async def test_execute_timeout() -> None:
    """A long-running command should be killed after the timeout."""
    result = await execute_command(
        command="sleep 60",
        timeout_seconds=1,
        correlation_id="test-timeout",
        job_id="j4",
        run_id="r4",
    )
    assert result.timed_out is True
    assert result.duration_seconds < 5  # Should complete quickly after kill


@pytest.mark.asyncio
async def test_execute_with_parameters() -> None:
    """Environment variables from parameters should be available to the command."""
    result = await execute_command(
        command='echo "val=$MY_PARAM"',
        timeout_seconds=10,
        parameters={"MY_PARAM": "hello123"},
        correlation_id="test-params",
        job_id="j5",
        run_id="r5",
    )
    assert result.exit_code == 0
    assert "val=hello123" in result.stdout


@pytest.mark.asyncio
async def test_execute_multiline_output() -> None:
    """Multi-line output should be fully captured."""
    result = await execute_command(
        command='printf "line1\\nline2\\nline3"',
        timeout_seconds=10,
    )
    assert result.exit_code == 0
    lines = result.stdout.strip().split("\n")
    assert len(lines) == 3
    assert lines[0] == "line1"
    assert lines[2] == "line3"
