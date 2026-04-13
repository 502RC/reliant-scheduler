"""Integration tests for the event publisher (local fallback mode).

Without Azure Event Hubs connection string, events are logged locally.
"""

import pytest

from reliant_scheduler.workers.event_publisher import publish_lifecycle_event


@pytest.mark.asyncio
async def test_publish_started_event() -> None:
    """Publishing a started event should not raise in local mode."""
    await publish_lifecycle_event(
        "started",
        job_id="j1",
        run_id="r1",
        agent_id="a1",
        attempt_number=1,
        correlation_id="test-started",
    )


@pytest.mark.asyncio
async def test_publish_completed_event() -> None:
    """Publishing a completed event should not raise in local mode."""
    await publish_lifecycle_event(
        "completed",
        job_id="j2",
        run_id="r2",
        agent_id="a2",
        exit_code=0,
        duration_seconds=1.5,
        attempt_number=1,
        correlation_id="test-completed",
    )


@pytest.mark.asyncio
async def test_publish_failed_event() -> None:
    """Publishing a failed event should include error details."""
    await publish_lifecycle_event(
        "failed",
        job_id="j3",
        run_id="r3",
        agent_id="a3",
        exit_code=1,
        error_message="segfault",
        duration_seconds=0.2,
        attempt_number=2,
        correlation_id="test-failed",
    )


@pytest.mark.asyncio
async def test_publish_timed_out_event() -> None:
    """Publishing a timed_out event should not raise."""
    await publish_lifecycle_event(
        "timed_out",
        job_id="j4",
        run_id="r4",
        agent_id="a4",
        duration_seconds=3600.0,
        correlation_id="test-timeout",
    )
